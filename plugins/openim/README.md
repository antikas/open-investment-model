# OpenIM local plugin

This plugin gives coding and research agents read-only access to the Open Investment Model through the pinned `@openinvestmentmodel/openim-mcp@0.1.1` stdio package.

An open, MIT-licensed, vendor-neutral reference model for institutional investment management, comprising a service-domain decomposition of the buy-side firm and a canonical entity model.

## What it does

- discovers model elements from plain-language queries;
- retrieves full, versioned model content and official provenance;
- maps business, data, and architecture requirements to candidate OpenIM elements;
- lists released machine-readable exports;
- returns the canonical identity, release, licence, maturity, and model counts.

The skill requires exact official sources and separates retrieved model content from agent interpretation. It provides no investment advice, trading, write operations, or hosted-service claim.

## Install

Requirements: Node.js 20 or later and `npx`.

1. Obtain the public repository from https://github.com/antikas/open-investment-model.
2. Point the client's local-plugin installation at `plugins/openim`.
3. Reload the client and confirm that the `openim` MCP server exposes five read-only tools.
4. Invoke `$openim-research-and-architecture` or ask an institutional investment-management architecture question.

Clients that support MCP but not plugins can use the generated `.mcp.json` command directly. The package is pinned so an installation cannot silently move to another release.

## Remove

Remove the local plugin entry or copied `plugins/openim` directory and reload the client. The plugin creates no account, credential, background service, or machine-level daemon.

## Source of truth

Run `node plugins/openim/scripts/generate.mjs` after changing `metadata/openim.json` or `mcp/package.json`. Run it with `--check` in verification. The plugin's shared identity description, official URLs, maintainer, keywords, and pinned package version are generated from those canonical sources.
