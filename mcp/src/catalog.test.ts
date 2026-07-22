import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { getCatalogItem, loadCatalog, searchCatalog } from './catalog.js';

const moduleDir = dirname(fileURLToPath(import.meta.url));
const catalog = loadCatalog(resolve(moduleDir, '../model-index.json'));

test('catalogue is complete and release-pinned', () => {
  assert.equal(catalog.modelVersion, catalog.identity.version);
  assert.equal(catalog.generatedFrom, `v${catalog.identity.version}`);
  assert.equal(catalog.counts['business-domain'], 17);
  assert.equal(catalog.counts['service-domain'], 171);
  assert.equal(catalog.counts.entity, 86);
  assert.ok(catalog.counts['service-operation'] > 500);
  assert.ok(catalog.counts.export > 5);
});

test('exact identifiers resolve with official provenance', () => {
  const entity = getCatalogItem(catalog, 'E-01');
  assert.equal(entity?.title, 'Legal Entity');
  assert.match(entity?.sourceUrl ?? '', /\/blob\/v0\.3\.0\/model\/entities\/core\/E-01-/);
  assert.match(entity?.officialUrl ?? '', /^https:\/\/openinvestmentmodel\.org\//);
});

test('plain-language searches find relevant model elements', () => {
  const capitalCall = searchCatalog(catalog, 'capital call lifecycle', undefined, 10);
  assert.ok(capitalCall.some((item) => item.id === 'PM-07'));
  const liquidity = searchCatalog(catalog, 'liquidity risk measurement', undefined, 10);
  assert.ok(liquidity.some((item) => item.id === 'SD-07.3' || item.id === 'E-19'));
});

test('catalogue remains independent of product implementations', () => {
  const serialized = JSON.stringify(catalog);
  assert.doesNotMatch(serialized, /agentinvest/i);
  assert.match(catalog.identity.description, /MIT-licensed/);
});

test('server manifest and package identity agree', () => {
  const packageJson = JSON.parse(readFileSync(resolve(moduleDir, '../../package.json'), 'utf8'));
  const manifest = JSON.parse(readFileSync(resolve(moduleDir, '../../server.json'), 'utf8'));
  assert.equal(packageJson.mcpName, manifest.name);
  assert.equal(packageJson.version, manifest.version);
  assert.equal(packageJson.name, manifest.packages[0].identifier);
  assert.equal(packageJson.version, manifest.packages[0].version);
  assert.equal(manifest.packages[0].transport.type, 'stdio');
});
