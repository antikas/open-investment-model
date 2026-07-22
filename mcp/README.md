# OpenIM MCP server

Read-only, source-cited access to the [Open Investment Model (OpenIM)](https://openinvestmentmodel.org/), the open reference model for institutional buy-side investment management.

The server searches and retrieves OpenIM Business Domains, Service Domains, Service Operations, canonical entities, relationships, glossary terms and generated model exports. Every response identifies the exact OpenIM release and links to the official versioned source. It does not provide investment advice, execute transactions or expose an implementation environment.

## Run

Node.js 20 or later is required.

```sh
npx -y @antikas/openim-mcp
```

Generic MCP client configuration:

```json
{
  "mcpServers": {
    "openim": {
      "command": "npx",
      "args": ["-y", "@antikas/openim-mcp"]
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
npm install
npm test
```

The build derives `dist/model-index.json` from `../model`, `../metadata/openim.json` and `../exports`. `server.json` is regenerated from the same identity and package metadata.

## Licence

MIT. OpenIM is a reference model, not a standard, investment product or production system.
