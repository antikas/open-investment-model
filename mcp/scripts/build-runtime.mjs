#!/usr/bin/env node

import { appendFileSync, chmodSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const mcpDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repoDir = resolve(mcpDir, '..');
const distDir = resolve(mcpDir, 'dist');
const packageJson = JSON.parse(readFileSync(resolve(mcpDir, 'package.json'), 'utf8'));

function packageForInput(input) {
  let candidate = dirname(resolve(mcpDir, input));
  while (candidate.startsWith(mcpDir)) {
    const manifestPath = resolve(candidate, 'package.json');
    try {
      const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
      if (manifest.name && manifest.version && candidate.includes('node_modules')) {
        return { root: candidate, manifest };
      }
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
    }
    const parent = dirname(candidate);
    if (parent === candidate) break;
    candidate = parent;
  }
  return null;
}

function legalFiles(root) {
  return readdirSync(root)
    .filter((name) => /^(?:licen[cs]e|copying|notice)(?:\..+)?$/i.test(name))
    .sort((a, b) => a.localeCompare(b));
}

mkdirSync(distDir, { recursive: true });
const privatePublicLicence = resolve(repoDir, 'ops/public-licence/LICENSE');
const licenceSource = existsSync(privatePublicLicence) ? privatePublicLicence : resolve(repoDir, 'LICENSE');
const licence = readFileSync(licenceSource, 'utf8');
if (!licence.startsWith('MIT License')) {
  throw new Error(`Refusing to package a non-MIT OpenIM licence from ${licenceSource}`);
}
writeFileSync(resolve(distDir, 'LICENSE'), licence.replaceAll('\r\n', '\n'));

const result = await build({
  absWorkingDir: mcpDir,
  entryPoints: ['src/server.ts'],
  outfile: 'dist/server.js',
  bundle: true,
  platform: 'node',
  format: 'esm',
  target: ['node20'],
  packages: 'bundle',
  metafile: true,
  legalComments: 'linked',
  define: { __OPENIM_MCP_VERSION__: JSON.stringify(packageJson.version) },
  logLevel: 'info',
});

const linkedLegalPath = resolve(distDir, 'server.js.LEGAL.txt');
if (!existsSync(linkedLegalPath)) {
  writeFileSync(linkedLegalPath, 'Bundled third-party licence texts are reproduced in THIRD_PARTY_NOTICES.txt.\n');
  appendFileSync(resolve(distDir, 'server.js'), '\n/*! Legal notices: server.js.LEGAL.txt */\n');
}

const thirdParties = new Map();
for (const input of Object.keys(result.metafile.inputs)) {
  const found = packageForInput(input);
  if (found) thirdParties.set(`${found.manifest.name}@${found.manifest.version}`, found);
}

const inventory = [...thirdParties]
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([key, { root, manifest }]) => {
    const notices = legalFiles(root);
    if (!notices.length) throw new Error(`Bundled package ${key} has no licence or notice file`);
    return {
      name: manifest.name,
      version: manifest.version,
      license: manifest.license ?? 'SEE INCLUDED NOTICE',
      files: notices,
    };
  });

const notice = [
  'THIRD-PARTY SOFTWARE NOTICES',
  '',
  'This file lists the third-party packages incorporated into the bundled OpenIM MCP runtime.',
  'The OpenIM package remains licensed under MIT. The notices below apply to their named components.',
  '',
];
for (const item of inventory) {
  const { root } = thirdParties.get(`${item.name}@${item.version}`);
  notice.push('='.repeat(78), `${item.name} ${item.version}`, `Declared licence: ${item.license}`, '');
  for (const filename of item.files) {
    notice.push(`--- ${filename} ---`, readFileSync(resolve(root, filename), 'utf8').trim(), '');
  }
}

writeFileSync(resolve(distDir, 'THIRD_PARTY_NOTICES.txt'), `${notice.join('\n').trim()}\n`);
writeFileSync(
  resolve(distDir, '.bundle-meta.json'),
  `${JSON.stringify({ packageVersion: packageJson.version, inventory, metafile: result.metafile }, null, 2)}\n`,
);
chmodSync(resolve(distDir, 'server.js'), 0o755);

const output = relative(mcpDir, resolve(distDir, 'server.js')).replaceAll('\\', '/');
console.log(`Bundled ${output} for package ${packageJson.version} with ${inventory.length} third-party packages.`);
