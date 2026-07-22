import assert from 'node:assert/strict';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const moduleDir = dirname(fileURLToPath(import.meta.url));

test('a clean MCP client can discover and call the read-only server', async () => {
  const client = new Client({ name: 'openim-test-client', version: '1.0.0' });
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [resolve(moduleDir, 'server.js')],
    stderr: 'pipe',
  });

  try {
    await client.connect(transport);
    const tools = await client.listTools();
    assert.deepEqual(
      tools.tools.map((tool) => tool.name).sort(),
      ['openim_get', 'openim_get_identity', 'openim_list_exports', 'openim_map_requirement', 'openim_search'],
    );
    assert.ok(tools.tools.every((tool) => tool.annotations?.readOnlyHint === true));

    const response = await client.callTool({
      name: 'openim_search',
      arguments: { query: 'capital call lifecycle', limit: 10 },
    });
    const structured = response.structuredContent as { modelVersion: string; results: Array<{ id: string }> };
    assert.equal(structured.modelVersion, '0.3.0');
    assert.ok(structured.results.some((item) => item.id === 'PM-07'));

    const resources = await client.listResources();
    assert.ok(resources.resources.some((resource) => resource.uri === 'openim://identity'));
    const identity = await client.readResource({ uri: 'openim://identity' });
    const identityContent = identity.contents[0];
    assert.ok(identityContent && 'text' in identityContent);
    assert.match(identityContent.text, /Open Investment Model/);
  } finally {
    await client.close();
  }
});
