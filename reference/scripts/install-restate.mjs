#!/usr/bin/env node
/**
 * OpenIM-OWNED Restate installer (agentINVEST substrate, P-R1 decoupling).
 *
 * This is OpenIM's OWN install script — vendored from the pattern a sibling
 * project sharing the dev substrate uses, but OWNED and version-pinned by OpenIM.
 * A fresh OpenIM checkout installs its substrate binaries with THIS script and
 * NEVER reads the sibling project's source files. The OIM-100 floor depended
 * operationally on the sibling's `install-restate.mjs` / `run-restate-server.mjs`
 * at a hardcoded absolute checkout path OpenIM neither owned nor versioned; that
 * source-file dependency is removed here (the OIM-100 pre-mortem's P-R1, High/High).
 *
 * Version contract: RESTATE_VERSION below is OpenIM's OWN pin. It is kept at the
 * same value the sibling project pins so the *running* instance can be shared at
 * dev time (ADR-0054 default — one binary, one journal, no second cluster) — but
 * the pin is now OpenIM's to bump, not a coincidence of the sibling's.
 *
 * Binaries land in `reference/tools/` (gitignored). The Restate server is the
 * Linux-musl build run inside WSL2 on Windows (WSL2's NAT + localhost-forwarding
 * is the reach); native on Mac/Linux.
 *
 * TLS note: if your network re-signs TLS (corporate HTTPS interception), point
 * NODE_EXTRA_CA_CERTS at your organisation's TLS-interception CA bundle so the
 * download trusts the chain.
 */
import { createHash } from 'node:crypto';
import { createWriteStream } from 'node:fs';
import { chmod, mkdir, readdir, readFile, rename, rm, stat, writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

/** OpenIM's OWN Restate version pin (the P-R1 version contract). */
export const RESTATE_VERSION = '1.6.2';

const REPO = 'restatedev/restate';
const RELEASE_BASE = `https://github.com/${REPO}/releases/download/v${RESTATE_VERSION}`;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// reference/scripts/ -> reference/
const REFERENCE_ROOT = path.resolve(__dirname, '..');
const TOOLS_DIR = path.join(REFERENCE_ROOT, 'tools');

const COMPONENT_TO_BINARY = {
  'restate-server': 'restate-server',
  'restate-cli': 'restate',
  restatectl: 'restatectl',
};

function detectAssetTriple() {
  const arch = process.arch === 'arm64' ? 'aarch64' : 'x86_64';
  // On Windows we run the Linux-musl binary inside WSL2 (no native Windows
  // restate-server build); on Linux likewise musl; macOS native.
  if (process.platform === 'win32' || process.platform === 'linux') {
    return `${arch}-unknown-linux-musl`;
  }
  if (process.platform === 'darwin') {
    return `${arch}-apple-darwin`;
  }
  throw new Error(`unsupported platform: ${process.platform}/${process.arch}`);
}

async function fileExists(p) {
  try {
    await stat(p);
    return true;
  } catch {
    return false;
  }
}

async function sha256OfFile(p) {
  return createHash('sha256').update(await readFile(p)).digest('hex');
}

function classifyNetError(err, url) {
  const code = err?.cause?.code ?? err?.code ?? '';
  if (
    typeof code === 'string' &&
    (code.startsWith('CERT_') ||
      code === 'UNABLE_TO_VERIFY_LEAF_SIGNATURE' ||
      code === 'SELF_SIGNED_CERT_IN_CHAIN')
  ) {
    return new Error(
      `TLS verification failed for ${url} (${code}). ` +
        `If your network re-signs TLS (corporate HTTPS interception), ` +
        `point NODE_EXTRA_CA_CERTS at your organisation's TLS-interception CA bundle ` +
        `so Node trusts the re-signed chain.`,
    );
  }
  return err;
}

async function downloadTo(url, dest) {
  let res;
  try {
    res = await fetch(url, { redirect: 'follow' });
  } catch (err) {
    throw classifyNetError(err, url);
  }
  if (!res.ok || !res.body) {
    throw new Error(
      `download failed ${res.status} ${res.statusText} for ${url}` +
        (res.status === 404
          ? ` (the pinned release artefact may have been retired upstream; check https://github.com/restatedev/restate/releases)`
          : ''),
    );
  }
  try {
    await pipeline(Readable.fromWeb(res.body), createWriteStream(dest));
  } catch (err) {
    await rm(dest, { force: true }).catch(() => {});
    throw err;
  }
}

async function fetchText(url) {
  let res;
  try {
    res = await fetch(url, { redirect: 'follow' });
  } catch (err) {
    throw classifyNetError(err, url);
  }
  if (!res.ok) throw new Error(`download failed ${res.status} ${res.statusText} for ${url}`);
  return await res.text();
}

/** Translate a drive-lettered Windows path to its WSL2 /mnt/<letter>/ form. */
function toWslPath(winPath) {
  const norm = winPath.replace(/\\/g, '/');
  const m = norm.match(/^([A-Za-z]):(.*)$/);
  if (!m) return norm;
  return `/mnt/${m[1].toLowerCase()}${m[2]}`;
}

async function extractTarXz(archivePath, destDir) {
  await mkdir(destDir, { recursive: true });
  await new Promise((resolve, reject) => {
    let cmd;
    let args;
    if (process.platform === 'win32') {
      // The artefact is a Linux-musl tarball and the binary runs inside WSL2.
      // Extract INSIDE WSL2 so tar sees clean Linux paths (/mnt/<letter>/...) —
      // Windows host tar mis-parses drive-lettered paths as remote `host:path`
      // specs. The default WSL distro is discovered/overridden the same way the
      // launcher does.
      const distro = process.env.RESTATE_WSL_DISTRO ?? 'Ubuntu-24.04';
      cmd = 'wsl';
      args = [
        '-d',
        distro,
        '--',
        'tar',
        '-xJf',
        toWslPath(archivePath),
        '-C',
        toWslPath(destDir),
      ];
    } else {
      cmd = 'tar';
      args = ['-xJf', archivePath, '-C', destDir];
    }
    const p = spawn(cmd, args, { stdio: 'inherit', env: { ...process.env, WSL_UTF8: '1' } });
    p.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`tar exit ${code}`))));
    p.on('error', reject);
  });
}

async function findFileByName(rootDir, name) {
  const stack = [rootDir];
  while (stack.length > 0) {
    const dir = stack.pop();
    const entries = await readdir(dir, { withFileTypes: true });
    for (const e of entries) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) stack.push(p);
      else if (e.isFile() && e.name === name) return p;
    }
  }
  return null;
}

async function ensureComponent(triple, component) {
  const binaryName = COMPONENT_TO_BINARY[component];
  const binaryPath = path.join(TOOLS_DIR, binaryName);
  const versionMarker = path.join(TOOLS_DIR, `.${binaryName}.v${RESTATE_VERSION}`);

  if ((await fileExists(binaryPath)) && (await fileExists(versionMarker))) {
    process.stderr.write(`[restate-install] ${binaryName} v${RESTATE_VERSION} already present\n`);
    return;
  }

  const archive = `${component}-${triple}.tar.xz`;
  const url = `${RELEASE_BASE}/${archive}`;
  const shaUrl = `${url}.sha256`;
  const archivePath = path.join(TOOLS_DIR, archive);

  process.stderr.write(`[restate-install] downloading ${archive}\n`);
  await mkdir(TOOLS_DIR, { recursive: true });
  await downloadTo(url, archivePath);

  const shaLine = (await fetchText(shaUrl)).trim();
  const expectedSha = shaLine.split(/\s+/)[0];
  const actualSha = await sha256OfFile(archivePath);
  if (expectedSha.toLowerCase() !== actualSha.toLowerCase()) {
    await rm(archivePath, { force: true });
    throw new Error(`SHA256 mismatch for ${archive}: expected ${expectedSha} got ${actualSha}`);
  }
  process.stderr.write(`[restate-install] sha256 verified ${archive}\n`);

  const extractDir = path.join(TOOLS_DIR, `.extract-${component}`);
  await rm(extractDir, { recursive: true, force: true });
  await extractTarXz(archivePath, extractDir);

  const found = await findFileByName(extractDir, binaryName);
  if (!found) throw new Error(`binary ${binaryName} not found inside ${archive}`);
  await rename(found, binaryPath);
  try {
    await chmod(binaryPath, 0o755);
  } catch {
    /* NTFS keeps the bit via DrvFs */
  }

  await writeFile(versionMarker, `${RESTATE_VERSION}\n`, 'utf8');
  await rm(extractDir, { recursive: true, force: true });
  await rm(archivePath, { force: true });

  process.stderr.write(`[restate-install] installed ${binaryName} v${RESTATE_VERSION}\n`);
}

export async function ensureRestate() {
  const triple = detectAssetTriple();
  await mkdir(TOOLS_DIR, { recursive: true });
  for (const component of Object.keys(COMPONENT_TO_BINARY)) {
    await ensureComponent(triple, component);
  }
}

const invokedDirectly =
  process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) {
  ensureRestate().catch((err) => {
    process.stderr.write(`[restate-install] ERROR: ${err.message}\n`);
    process.exit(1);
  });
}
