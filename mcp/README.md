# OpenIM MCP server

Read-only, source-cited access to the [Open Investment Model (OpenIM)](https://openinvestmentmodel.org/), the open reference model for institutional buy-side investment management.

The server searches and retrieves OpenIM Business Domains, Service Domains, Service Operations, canonical entities, relationships, glossary terms and generated model exports. Every response identifies the exact OpenIM release and links to the official versioned source. It does not provide investment advice, execute transactions or expose an implementation environment.

## Run

Node.js 20 or later is required.

```sh
npx -y @openinvestmentmodel/openim-mcp
```

Generic MCP client configuration:

```json
{
  "mcpServers": {
    "openim": {
      "command": "npx",
      "args": ["-y", "@openinvestmentmodel/openim-mcp"]
    }
  }
}
```

The server needs no API key and performs no network calls at runtime. Its catalogue is generated from the released OpenIM model when the package is built.

## Tools

- `openim_search`: search all model elements, optionally filtered by type.
- `openim_get`: retrieve one element by its OpenIM identifier.
- `openim_map_requirement`: find the model elements most relevant to a stated buy-side architecture requirement.
- `openim_list_exports`: list downloadable schemas, ontologies, graph files and other released artefacts.
- `openim_get_identity`: return the canonical OpenIM identity, version, scope and official sources.

The server also exposes `openim://identity` and `openim://catalog` as MCP resources.

## Development

From the `mcp/` directory in the OpenIM repository:

```sh
npm ci
npm run quality
```

The build derives `dist/model-index.json` from `../model`, `../metadata/openim.json` and `../exports`. It bundles the reachable stdio runtime into `dist/server.js`. The package version in `package.json` is injected into that bundle and generates `server.json`.

The quality command runs the source production audit, unit and MCP tests, bundle inventory, packed consumer test, identity scan and reproducible pack check. The packed consumer calls all five tools through the installed tarball and checks the model version and official source in every response.

The package carries OpenIM's MIT licence in `dist/LICENSE`. Bundled third-party packages are listed with their licence texts in `dist/THIRD_PARTY_NOTICES.txt`. Linked legal comments remain beside the entry point in `dist/server.js.LEGAL.txt`.

## Licence

MIT. OpenIM is a reference model, not a standard, investment product or production system.
