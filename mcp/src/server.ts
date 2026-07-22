#!/usr/bin/env node

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import {
  ITEM_TYPES,
  getCatalogItem,
  loadCatalog,
  searchCatalog,
  type ItemType,
} from './catalog.js';

declare const __OPENIM_MCP_VERSION__: string;

const catalog = loadCatalog();
const server = new McpServer({
  name: 'io.github.antikas/openim',
  version: __OPENIM_MCP_VERSION__,
  title: 'Open Investment Model',
  description: 'Read-only, versioned and source-cited access to the Open Investment Model.',
  websiteUrl: catalog.identity.officialUrl,
});

function result(payload: Record<string, unknown>) {
  return {
    content: [{ type: 'text' as const, text: JSON.stringify(payload, null, 2) }],
    structuredContent: payload,
  };
}

server.registerTool(
  'openim_search',
  {
    title: 'Search OpenIM',
    description: 'Search the released OpenIM reference model. Results include the exact model version and official source links.',
    inputSchema: {
      query: z.string().min(2).describe('Plain-language query or an OpenIM identifier such as SD-07.3 or E-04.'),
      types: z.array(z.enum(ITEM_TYPES)).optional().describe('Optional model-element types to include.'),
      limit: z.number().int().min(1).max(20).default(10),
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  async ({ query, types, limit }) =>
    result({
      query,
      modelVersion: catalog.modelVersion,
      officialSource: catalog.identity.officialUrl,
      results: searchCatalog(catalog, query, types as ItemType[] | undefined, limit),
    }),
);

server.registerTool(
  'openim_get',
  {
    title: 'Get an OpenIM model element',
    description: 'Retrieve one released OpenIM model element by identifier, including its full documented content and provenance.',
    inputSchema: { id: z.string().min(2).describe('OpenIM identifier, for example BD-05, SD-05.3, E-04 or relation:POSITION_IN.') },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  async ({ id }) => {
    const item = getCatalogItem(catalog, id);
    return item
      ? result({ modelVersion: catalog.modelVersion, officialSource: catalog.identity.officialUrl, item })
      : result({
          error: 'not_found',
          id,
          modelVersion: catalog.modelVersion,
          officialSource: catalog.identity.officialUrl,
          suggestions: searchCatalog(catalog, id, undefined, 5),
        });
  },
);

server.registerTool(
  'openim_map_requirement',
  {
    title: 'Map a requirement to OpenIM',
    description: 'Map a stated institutional buy-side architecture requirement to relevant OpenIM domains, operations and entities. This is deterministic model retrieval, not investment advice.',
    inputSchema: {
      requirement: z.string().min(5).describe('The business, data or architecture requirement to map.'),
      limit: z.number().int().min(1).max(20).default(10),
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  async ({ requirement, limit }) =>
    result({
      requirement,
      interpretation: 'Keyword-ranked matches from the released OpenIM catalogue. Review the cited model text before making an architecture decision.',
      modelVersion: catalog.modelVersion,
      officialSource: catalog.identity.officialUrl,
      matches: searchCatalog(
        catalog,
        requirement,
        ['business-domain', 'service-domain', 'service-operation', 'entity', 'relationship'],
        limit,
      ),
    }),
);

server.registerTool(
  'openim_list_exports',
  {
    title: 'List OpenIM model exports',
    description: 'List the released machine-readable OpenIM schemas, ontologies, graph files and other model artefacts.',
    inputSchema: { query: z.string().optional().describe('Optional filename or format filter.') },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  async ({ query }) => {
    const exports = query
      ? searchCatalog(catalog, query, ['export'], 20)
      : catalog.items
          .filter((item) => item.type === 'export')
          .map(({ content: _content, ...item }) => ({ ...item, modelVersion: catalog.modelVersion }));
    return result({ modelVersion: catalog.modelVersion, officialSource: catalog.identity.officialUrl, exports });
  },
);

server.registerTool(
  'openim_get_identity',
  {
    title: 'Get the canonical OpenIM identity',
    description: 'Return OpenIM scope, release, maturity, licence and official sources.',
    inputSchema: {},
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  async () =>
    result({
      modelVersion: catalog.modelVersion,
      officialSource: catalog.identity.officialUrl,
      identity: catalog.identity,
      counts: catalog.counts,
      generatedFrom: catalog.generatedFrom,
    }),
);

server.registerResource(
  'openim-identity',
  'openim://identity',
  { title: 'OpenIM canonical identity', description: 'Canonical identity and release metadata for OpenIM.', mimeType: 'application/json' },
  async (uri) => ({
    contents: [{ uri: uri.href, mimeType: 'application/json', text: JSON.stringify(catalog.identity, null, 2) }],
  }),
);

server.registerResource(
  'openim-catalog',
  'openim://catalog',
  { title: 'OpenIM catalogue summary', description: 'Released OpenIM version and model-element counts.', mimeType: 'application/json' },
  async (uri) => ({
    contents: [
      {
        uri: uri.href,
        mimeType: 'application/json',
        text: JSON.stringify(
          {
            modelVersion: catalog.modelVersion,
            generatedFrom: catalog.generatedFrom,
            counts: catalog.counts,
            officialSource: catalog.identity.officialUrl,
          },
          null,
          2,
        ),
      },
    ],
  }),
);

const transport = new StdioServerTransport();
await server.connect(transport);
