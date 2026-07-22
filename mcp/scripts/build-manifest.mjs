#!/usr/bin/env node

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const mcpDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repoDir = resolve(mcpDir, '..');
const pkg = JSON.parse(readFileSync(resolve(mcpDir, 'package.json'), 'utf8'));
const identity = JSON.parse(readFileSync(resolve(repoDir, 'metadata/openim.json'), 'utf8'));

const manifest = {
  $schema: 'https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json',
  name: pkg.mcpName,
  title: identity.name,
  description: `Search and retrieve the ${identity.name} (${identity.alternateName}), the open, MIT-licensed reference model for institutional buy-side investment management.`,
  repository: {
    url: identity.sourceRepository,
    source: 'github',
    subfolder: 'mcp',
  },
  version: pkg.version,
  packages: [
    {
      registryType: 'npm',
      identifier: pkg.name,
      version: pkg.version,
      transport: { type: 'stdio' },
    },
  ],
};

writeFileSync(resolve(mcpDir, 'server.json'), `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`MCP manifest: ${manifest.name} v${manifest.version}`);
