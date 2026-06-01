import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

import { AppConfig, hasDefaultScope, resolveScopeInput } from "../config.js";
import { searchKnowledge } from "../client.js";
import { searchInputSchema } from "../schemas/search.js";

export function registerSearchKnowledgeTool(server: McpServer, config: AppConfig): void {
  const useFixedScope = hasDefaultScope(config);
  if (useFixedScope) {
    server.registerTool(
      "kb_search",
      {
        title: "Search Knowledge Base",
        description:
          "Search LangChain RAG knowledge content inside the configured default product, project, and app scope.",
        inputSchema: {
          query: searchInputSchema.query,
          top_k: searchInputSchema.top_k,
        },
      },
      async ({ query, top_k }) => {
        const scope = resolveScopeInput(config, {});
        const output = await searchKnowledge(config, scope, query, top_k);
        return {
          content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }],
          structuredContent: output,
        };
      },
    );
    return;
  }

  server.registerTool(
    "kb_search",
    {
      title: "Search Knowledge Base",
      description: "Search LangChain RAG knowledge content inside one configured product app scope.",
      inputSchema: searchInputSchema,
    },
    async ({ product_code, project_code, app_code, query, top_k }) => {
      const scope = resolveScopeInput(config, {
        productCode: product_code,
        projectCode: project_code,
        appCode: app_code,
      });
      const output = await searchKnowledge(config, scope, query, top_k);
      return {
        content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }],
        structuredContent: output,
      };
    },
  );
}
