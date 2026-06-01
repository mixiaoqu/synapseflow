import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

import { AppConfig, hasDefaultScope, resolveScopeInput } from "../config.js";
import { answerKnowledge } from "../client.js";
import { answerInputSchema } from "../schemas/answer.js";

export function registerAnswerKnowledgeTool(server: McpServer, config: AppConfig): void {
  const useFixedScope = hasDefaultScope(config);
  if (useFixedScope) {
    server.registerTool(
      "kb_answer",
      {
        title: "Answer With Knowledge Base",
        description:
          "Ask a question against LangChain RAG knowledge content inside the configured default product, project, and app scope.",
        inputSchema: { query: answerInputSchema.query },
      },
      async ({ query }) => {
        const scope = resolveScopeInput(config, {});
        const output = await answerKnowledge(config, scope, query);
        return {
          content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }],
          structuredContent: output,
        };
      },
    );
    return;
  }

  server.registerTool(
    "kb_answer",
    {
      title: "Answer With Knowledge Base",
      description: "Ask a question against LangChain RAG knowledge content inside one configured product app scope.",
      inputSchema: answerInputSchema,
    },
    async ({ product_code, project_code, app_code, query }) => {
      const scope = resolveScopeInput(config, {
        productCode: product_code,
        projectCode: project_code,
        appCode: app_code,
      });
      const output = await answerKnowledge(config, scope, query);
      return {
        content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }],
        structuredContent: output,
      };
    },
  );
}
