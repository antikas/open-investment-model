#!/usr/bin/env node

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const pluginRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = resolve(pluginRoot, '..', '..');
const identity = JSON.parse(readFileSync(resolve(repoRoot, 'metadata/openim.json'), 'utf8'));
const mcpPackage = JSON.parse(readFileSync(resolve(repoRoot, 'mcp/package.json'), 'utf8'));
const checkOnly = process.argv.includes('--check');

const skillName = 'openim-research-and-architecture';
const skillRoot = resolve(pluginRoot, 'skills', skillName);
const packageSpec = `${mcpPackage.name}@${mcpPackage.version}`;
const sharedDescription = identity.description;

const pluginManifest = {
  name: 'openim',
  version: '0.1.0',
  description: sharedDescription,
  author: {
    name: identity.maintainer.name,
    url: identity.maintainer.url,
  },
  homepage: identity.officialUrl,
  repository: identity.sourceRepository,
  license: 'MIT',
  keywords: ['mcp', 'research', 'enterprise-architecture', ...identity.keywords],
  skills: './skills/',
  mcpServers: './.mcp.json',
  interface: {
    displayName: identity.name,
    shortDescription: 'Research and architecture with the open model.',
    longDescription: sharedDescription,
    developerName: identity.maintainer.name,
    category: 'Developer Tools',
    capabilities: ['Read', 'Research'],
    websiteURL: identity.officialUrl,
    defaultPrompt: [
      'Map this investment-management requirement to OpenIM.',
      'Find the OpenIM elements relevant to this architecture.',
      'List OpenIM exports with versioned official sources.',
    ],
  },
};

const mcpConfig = {
  mcpServers: {
    openim: {
      command: 'npx',
      args: ['-y', packageSpec],
    },
  },
};

const skillDescription =
  'Use the local read-only OpenIM MCP capability to research the institutional buy-side reference model, retrieve model elements and exports, or map business, data, and architecture requirements to versioned official sources.';

const skillMarkdown = `---
name: ${skillName}
description: ${skillDescription}
---

# OpenIM research and architecture

${sharedDescription}

Use the MCP tools supplied by this plugin. They query a released, local model index and return the exact model version and official source with every result.

## Required workflow

1. Call \`openim_get_identity\` first. Treat its version, scope, maturity, licence, and official URLs as authoritative for the answer.
2. Choose the narrowest retrieval tool for the task. Do not reconstruct model facts from memory.
3. Follow a search or requirement mapping with \`openim_get\` for each element used in a substantive recommendation.
4. Cite the returned \`sourceUrl\` or \`officialSource\`, and state the returned \`modelVersion\`.
5. Separate retrieved model content from your interpretation. State any gap rather than inventing an element or relationship.

## Tool selection

- Use \`openim_search\` to find business domains, service domains, service operations, entities, relationships, glossary terms, or exports.
- Use \`openim_get\` when an identifier is known or when full documented content and provenance are needed.
- Use \`openim_map_requirement\` for a plain-language business, data, or architecture requirement. Its matches are deterministic keyword-ranked candidates, not an architecture decision.
- Use \`openim_list_exports\` to locate released machine-readable artefacts and their versioned sources.
- Use \`openim_get_identity\` to establish canonical identity, release, model counts, licence, and maturity.

For an adjacent-standard question, search for the named standard, retrieve the matching material, and report only the relationship supported by the returned text. An identity-level \`alignsWith\` link is evidence of alignment context, not equivalence or endorsement.

## Answer contract

Include:

- the direct answer or proposed mapping;
- the OpenIM identifiers and titles supporting it;
- the released model version;
- official source links returned by the tools;
- limitations, unmatched requirements, and interpretation clearly labelled.

## Boundaries

- This is read-only reference-model retrieval. It does not provide investment advice, trading, transaction execution, or production control.
- Do not describe OpenIM as a standard, product, or production system. Use the maturity statement returned by \`openim_get_identity\`.
- Do not promote or bind a particular implementation or commercial product to the open model.
- Do not claim a hosted MCP endpoint. This plugin starts the pinned package locally over stdio.
- If the tools are unavailable, report that the model could not be queried. Do not substitute uncited memory.
`;

const openAiYaml = `interface:
  display_name: "OpenIM Research and Architecture"
  short_description: "Query the versioned open investment model"
  default_prompt: "Use $${skillName} to map this requirement to versioned OpenIM sources."

dependencies:
  tools:
    - type: "mcp"
      value: "openim"
      description: "Local read-only OpenIM model retrieval supplied by this plugin."

policy:
  allow_implicit_invocation: true
`;

const readme = `# OpenIM local plugin

This plugin gives coding and research agents read-only access to the Open Investment Model through the pinned \`${packageSpec}\` stdio package.

${sharedDescription}

## What it does

- discovers model elements from plain-language queries;
- retrieves full, versioned model content and official provenance;
- maps business, data, and architecture requirements to candidate OpenIM elements;
- lists released machine-readable exports;
- returns the canonical identity, release, licence, maturity, and model counts.

The skill requires exact official sources and separates retrieved model content from agent interpretation. It provides no investment advice, trading, write operations, or hosted-service claim.

## Install

Requirements: Node.js 20 or later and \`npx\`.

1. Obtain the public repository from ${identity.sourceRepository}.
2. Point the client's local-plugin installation at \`plugins/openim\`.
3. Reload the client and confirm that the \`openim\` MCP server exposes five read-only tools.
4. Invoke \`$${skillName}\` or ask an institutional investment-management architecture question.

Clients that support MCP but not plugins can use the generated \`.mcp.json\` command directly. The package is pinned so an installation cannot silently move to another release.

## Remove

Remove the local plugin entry or copied \`plugins/openim\` directory and reload the client. The plugin creates no account, credential, background service, or machine-level daemon.

## Source of truth

Run \`node plugins/openim/scripts/generate.mjs\` after changing \`metadata/openim.json\` or \`mcp/package.json\`. Run it with \`--check\` in verification. The plugin's shared identity description, official URLs, maintainer, keywords, and pinned package version are generated from those canonical sources.
`;

const outputs = new Map([
  [resolve(pluginRoot, '.codex-plugin/plugin.json'), `${JSON.stringify(pluginManifest, null, 2)}\n`],
  [resolve(pluginRoot, '.mcp.json'), `${JSON.stringify(mcpConfig, null, 2)}\n`],
  [resolve(skillRoot, 'SKILL.md'), skillMarkdown],
  [resolve(skillRoot, 'agents/openai.yaml'), openAiYaml],
  [resolve(pluginRoot, 'README.md'), readme],
]);

const drift = [];
for (const [path, expected] of outputs) {
  if (checkOnly) {
    let actual = null;
    try {
      actual = readFileSync(path, 'utf8').replaceAll('\r\n', '\n');
    } catch {
      // Report a missing generated file through the same drift path.
    }
    if (actual !== expected) drift.push(path);
  } else {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, expected, 'utf8');
  }
}

if (drift.length) {
  throw new Error(`Generated OpenIM plugin files are stale:\n${drift.map((path) => `  - ${path}`).join('\n')}`);
}

console.log(
  checkOnly
    ? `OpenIM plugin generation check PASS (${outputs.size} files, ${packageSpec}).`
    : `Generated OpenIM plugin (${outputs.size} files, ${packageSpec}).`,
);
