#!/usr/bin/env node

import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, relative, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const mcpDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repoDir = resolve(mcpDir, '..');
const npmCli = process.env.npm_execpath;
const packageJson = JSON.parse(readFileSync(resolve(mcpDir, 'package.json'), 'utf8'));
const identity = JSON.parse(readFileSync(resolve(repoDir, 'metadata/openim.json'), 'utf8'));
const expectedPackageFiles = [...new Set(['package.json', ...packageJson.files])].sort();

function execute(command, args, { cwd = mcpDir, env = process.env, accepted = [0] } = {}) {
  const result = spawnSync(command, args, { cwd, env, encoding: 'utf8', windowsHide: true });
  if (result.error) throw result.error;
  if (!accepted.includes(result.status)) {
    throw new Error(
      [`${command} ${args.join(' ')} exited ${result.status}`, result.stdout, result.stderr]
        .filter(Boolean)
        .join('\n'),
    );
  }
  return result;
}

function executeNpm(args, options = {}) {
  if (npmCli) return execute(process.execPath, [npmCli, ...args], options);
  return execute('npm', args, options);
}

function parseJsonOutput(output, label) {
  try {
    return JSON.parse(output);
  } catch (error) {
    throw new Error(`${label} did not return JSON: ${error.message}\n${output}`);
  }
}

function audit({ cwd = mcpDir, env = process.env, omitDev = false } = {}) {
  const args = ['audit'];
  if (omitDev) args.push('--omit=dev');
  args.push('--json');
  const result = executeNpm(args, { cwd, env, accepted: [0, 1] });
  const report = parseJsonOutput(result.stdout, 'npm audit');
  if (report.error) throw new Error(`npm audit failed: ${JSON.stringify(report.error)}`);
  return report;
}

function hashFile(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function walk(root) {
  const files = [];
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const path = resolve(root, entry.name);
    if (entry.isDirectory()) files.push(...walk(path));
    else files.push(path);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

function packOnce(destination) {
  mkdirSync(destination, { recursive: true });
  const result = executeNpm(['pack', '--ignore-scripts', '--json', '--pack-destination', destination]);
  const records = parseJsonOutput(result.stdout, 'npm pack');
  assert.equal(records.length, 1, 'npm pack must produce exactly one tarball');
  const record = records[0];
  const file = resolve(destination, record.filename);
  assert.ok(statSync(file).isFile(), `npm pack did not create ${file}`);
  return { file, record };
}

function anonymousNpmEnvironment(userConfig) {
  const env = { ...process.env, NPM_CONFIG_USERCONFIG: userConfig, NPM_CONFIG_ALWAYS_AUTH: 'false' };
  for (const key of ['NODE_AUTH_TOKEN', 'NPM_TOKEN', 'GITHUB_TOKEN']) delete env[key];
  return env;
}

function assertCleanPackageTree(root) {
  const forbiddenPaths = /(?:^|\/)(?:reference|\.ergon|\.claude|docs\/cycles|ops)(?:\/|$)/i;
  const siblingProductMarker = new RegExp(['agent', 'invest'].join(''), 'i');
  const forbiddenContent = [
    ['sibling product identity', siblingProductMarker],
    ['private Windows path', /(?:[a-z]:[\\/](?:users|src)[\\/])/i],
    ['private implementation path', /(?:^|[\s"'`])reference[\\/]/im],
    ['private tracker path', /(?:^|[\s"'`])\.ergon[\\/]/im],
  ];

  for (const path of walk(root)) {
    const rel = relative(root, path).replaceAll('\\', '/');
    assert.doesNotMatch(rel, forbiddenPaths, `private path packaged: ${rel}`);
    const content = readFileSync(path, 'utf8');
    for (const [label, pattern] of forbiddenContent) {
      assert.doesNotMatch(content, pattern, `${label} found in ${rel}`);
    }
  }
}

function assertProvenance(name, response) {
  assert.equal(response.isError, undefined, `${name} returned an MCP error`);
  const payload = response.structuredContent;
  assert.equal(payload?.modelVersion, identity.version, `${name} omitted the exact OpenIM model version`);
  assert.equal(payload?.officialSource, identity.officialUrl, `${name} omitted the canonical OpenIM source`);
  return payload;
}

async function checkPackedTools(serverPath) {
  const client = new Client({ name: 'openim-packed-consumer-gate', version: '1.0.0' });
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [serverPath],
    stderr: 'pipe',
  });

  try {
    await client.connect(transport);
    assert.equal(client.getServerVersion()?.version, packageJson.version, 'server version did not come from package.json');
    const listed = await client.listTools();
    assert.deepEqual(
      listed.tools.map((tool) => tool.name).sort(),
      ['openim_get', 'openim_get_identity', 'openim_list_exports', 'openim_map_requirement', 'openim_search'],
    );
    assert.ok(listed.tools.every((tool) => tool.annotations?.readOnlyHint === true));

    const search = assertProvenance(
      'openim_search',
      await client.callTool({ name: 'openim_search', arguments: { query: 'capital call lifecycle', limit: 10 } }),
    );
    assert.ok(search.results.some((item) => item.sourceUrl.includes(`/v${identity.version}/`)));

    const get = assertProvenance(
      'openim_get',
      await client.callTool({ name: 'openim_get', arguments: { id: 'E-01' } }),
    );
    assert.ok(get.item.sourceUrl.includes(`/v${identity.version}/`));

    const mapped = assertProvenance(
      'openim_map_requirement',
      await client.callTool({
        name: 'openim_map_requirement',
        arguments: { requirement: 'portfolio valuation and liquidity risk', limit: 10 },
      }),
    );
    assert.ok(mapped.matches.some((item) => item.sourceUrl.includes(`/v${identity.version}/`)));

    const exports = assertProvenance(
      'openim_list_exports',
      await client.callTool({ name: 'openim_list_exports', arguments: {} }),
    );
    assert.ok(exports.exports.some((item) => item.sourceUrl.includes(`/v${identity.version}/`)));

    const canonicalIdentity = assertProvenance(
      'openim_get_identity',
      await client.callTool({ name: 'openim_get_identity', arguments: {} }),
    );
    assert.equal(canonicalIdentity.generatedFrom, `v${identity.version}`);
    assert.equal(canonicalIdentity.identity.sourceRepository, identity.sourceRepository);
  } finally {
    await client.close();
  }
}

function checkBundle() {
  assert.deepEqual(packageJson.dependencies ?? {}, {}, 'the bundled package must have no production dependency graph');
  const buildRecord = JSON.parse(readFileSync(resolve(mcpDir, 'dist/.bundle-meta.json'), 'utf8'));
  assert.equal(buildRecord.packageVersion, packageJson.version, 'bundle version drifted from package.json');

  const javascriptOutputs = Object.keys(buildRecord.metafile.outputs).filter((path) => path.endsWith('.js'));
  assert.deepEqual(javascriptOutputs, ['dist/server.js'], 'the build must emit one reachable stdio runtime entry point');

  const inventoryNames = new Set(buildRecord.inventory.map((item) => item.name));
  const httpOnlyPackages = [
    '@hono/node-server',
    'body-parser',
    'cors',
    'eventsource',
    'eventsource-parser',
    'express',
    'express-rate-limit',
    'hono',
    'raw-body',
  ];
  assert.deepEqual(
    httpOnlyPackages.filter((name) => inventoryNames.has(name)),
    [],
    'unused consumer HTTP packages survived the stdio bundle',
  );

  const report = audit();
  const vulnerabilities = Object.keys(report.vulnerabilities ?? {});
  const reachableVulnerabilities = vulnerabilities.filter((name) => inventoryNames.has(name));
  assert.deepEqual(reachableVulnerabilities, [], 'the reachable bundle contains an audited vulnerability');
  assert.ok(statSync(resolve(mcpDir, 'dist/server.js.LEGAL.txt')).size > 0, 'linked legal comments are missing');
  assert.ok(statSync(resolve(mcpDir, 'dist/THIRD_PARTY_NOTICES.txt')).size > 0, 'third-party notices are missing');
  assert.match(readFileSync(resolve(mcpDir, 'dist/LICENSE'), 'utf8'), /^MIT License\r?$/m, 'OpenIM MIT licence is missing');

  console.log(
    `Bundle inventory PASS: ${buildRecord.inventory.length} packages, ${vulnerabilities.length} source audit findings, zero reachable audit findings, zero HTTP-only packages.`,
  );
  for (const item of buildRecord.inventory) console.log(`  ${item.name}@${item.version} (${item.license})`);
  if (vulnerabilities.length) {
    console.log(`  Non-runtime development findings reported separately by npm audit: ${vulnerabilities.join(', ')}`);
  }
}

async function checkConsumer() {
  const temp = mkdtempSync(resolve(tmpdir(), 'openim-mcp-consumer-'));
  try {
    const packDir = resolve(temp, 'pack');
    const { file, record } = packOnce(packDir);
    assert.deepEqual(
      record.files.map((item) => item.path).sort(),
      expectedPackageFiles,
      'published tarball contains unexpected or missing files',
    );

    const extracted = resolve(temp, 'extracted');
    mkdirSync(extracted);
    execute('tar', ['-xzf', file, '-C', extracted]);
    assertCleanPackageTree(resolve(extracted, 'package'));

    const consumer = resolve(temp, 'consumer');
    mkdirSync(consumer);
    const userConfig = resolve(temp, 'anonymous.npmrc');
    writeFileSync(userConfig, 'registry=https://registry.npmjs.org/\nalways-auth=false\n');
    writeFileSync(
      resolve(consumer, 'package.json'),
      `${JSON.stringify({ name: 'openim-mcp-anonymous-consumer', version: '1.0.0', private: true }, null, 2)}\n`,
    );
    const env = anonymousNpmEnvironment(userConfig);
    executeNpm(['install', '--ignore-scripts', '--no-audit', '--no-fund', file], { cwd: consumer, env });
    const report = audit({ cwd: consumer, env, omitDev: true });
    assert.equal(report.metadata.vulnerabilities.total, 0, 'anonymous consumer production audit is not clean');

    const serverPath = resolve(
      consumer,
      'node_modules',
      ...packageJson.name.split('/'),
      'dist',
      'server.js',
    );
    await checkPackedTools(serverPath);
    console.log(
      `Packed consumer PASS: ${basename(file)}, zero production audit findings, five provenance-bearing tools, no private identity/path.`,
    );
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
}

function checkReproducible() {
  const temp = mkdtempSync(resolve(tmpdir(), 'openim-mcp-repro-'));
  try {
    const packs = [];
    for (const name of ['first', 'second']) {
      executeNpm(['run', 'build']);
      packs.push(packOnce(resolve(temp, name)));
    }
    assert.deepEqual(packs[0].record.files, packs[1].record.files, 'clean packs do not contain identical file inventories');
    const firstHash = hashFile(packs[0].file);
    const secondHash = hashFile(packs[1].file);
    assert.equal(firstHash, secondHash, 'clean pack SHA-256 values differ');
    console.log(`Reproducible pack PASS: ${packs[0].record.files.length} files, SHA-256 ${firstHash}.`);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
}

const command = process.argv[2];
if (command === 'bundle') checkBundle();
else if (command === 'consumer') await checkConsumer();
else if (command === 'reproducible') checkReproducible();
else throw new Error('Usage: node scripts/quality-gates.mjs <bundle|consumer|reproducible>');
