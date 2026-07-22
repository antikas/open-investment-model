import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, relative, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const pluginRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = resolve(pluginRoot, '..', '..');
const identity = JSON.parse(readFileSync(resolve(repoRoot, 'metadata/openim.json'), 'utf8'));
const mcpPackage = JSON.parse(readFileSync(resolve(repoRoot, 'mcp/package.json'), 'utf8'));
const manifest = JSON.parse(readFileSync(resolve(pluginRoot, '.codex-plugin/plugin.json'), 'utf8'));
const mcpConfig = JSON.parse(readFileSync(resolve(pluginRoot, '.mcp.json'), 'utf8'));
const skillPath = resolve(
  pluginRoot,
  'skills/openim-research-and-architecture/SKILL.md',
);
const skill = readFileSync(skillPath, 'utf8').replaceAll('\r\n', '\n');
const serverSource = readFileSync(resolve(repoRoot, 'mcp/src/server.ts'), 'utf8');

function walk(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(root, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  });
}

test('shared identity and package fields come from their canonical sources', () => {
  assert.equal(manifest.description, identity.description);
  assert.equal(manifest.interface.longDescription, identity.description);
  assert.equal(manifest.homepage, identity.officialUrl);
  assert.equal(manifest.repository, identity.sourceRepository);
  assert.equal(manifest.author.name, identity.maintainer.name);
  assert.deepEqual(manifest.keywords.slice(3), identity.keywords);
  assert.ok(skill.includes(`\n${identity.description}\n`));

  assert.deepEqual(mcpConfig, {
    mcpServers: {
      openim: {
        command: 'npx',
        args: ['-y', `${mcpPackage.name}@${mcpPackage.version}`],
      },
    },
  });
});

test('the skill covers every tested MCP tool and requires provenance', () => {
  const registered = [...serverSource.matchAll(/server\.registerTool\(\s*\n\s*'([^']+)'/g)]
    .map((match) => match[1])
    .sort();
  assert.deepEqual(registered, [
    'openim_get',
    'openim_get_identity',
    'openim_list_exports',
    'openim_map_requirement',
    'openim_search',
  ]);
  for (const tool of registered) assert.match(skill, new RegExp(`\\b${tool}\\b`));
  for (const required of ['modelVersion', 'officialSource', 'sourceUrl']) {
    assert.match(skill, new RegExp(`\\b${required}\\b`));
  }
});

test('the public plugin is local, read-only, product-neutral, and complete', () => {
  const files = walk(pluginRoot);
  const marker = new RegExp(['agent', 'invest'].join(''), 'i');
  const remoteServer = /"(?:url|headers)"\s*:/i;
  const placeholder = /\bTODO\b|\[TODO:/i;

  for (const path of files) {
    if (relative(pluginRoot, path).replaceAll('\\', '/') === 'tests/plugin.test.mjs') continue;
    const content = readFileSync(path, 'utf8');
    assert.doesNotMatch(content, marker, `product binding in ${relative(pluginRoot, path)}`);
    assert.doesNotMatch(content, placeholder, `placeholder in ${relative(pluginRoot, path)}`);
  }

  assert.doesNotMatch(readFileSync(resolve(pluginRoot, '.mcp.json'), 'utf8'), remoteServer);
  assert.match(skill, /read-only/i);
  assert.match(skill, /does not provide investment advice/i);
  assert.match(skill, /Do not claim a hosted MCP endpoint/i);
});
