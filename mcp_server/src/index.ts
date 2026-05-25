import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { loadConfig } from "./config.js";
import { registerAnswerKnowledgeTool } from "./tools/answerKnowledge.js";
import { registerResolveScopeTool } from "./tools/resolveScope.js";
import { registerSearchKnowledgeTool } from "./tools/searchKnowledge.js";

async function main(): Promise<void> {
  const config = loadConfig();
  const server = new McpServer({
    name: "synapseflow-kb",
    version: "0.1.0",
  });

  registerResolveScopeTool(server, config);
  registerSearchKnowledgeTool(server, config);
  registerAnswerKnowledgeTool(server, config);

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.stack ?? error.message : String(error);
  process.stderr.write(`${message}\n`);
  process.exit(1);
});
