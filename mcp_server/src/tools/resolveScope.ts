import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

import { AppConfig, hasDefaultScope, resolveScopeInput } from "../config.js";
import { resolveScope } from "../client.js";
import { scopeInputSchema } from "../schemas/scope.js";

export function registerResolveScopeTool(server: McpServer, config: AppConfig): void {
  const useFixedScope = hasDefaultScope(config);
  if (useFixedScope) {
    server.registerTool(
      "kb_scope_resolve",
      {
        title: "Resolve Knowledge Scope",
        description:
          "Resolve the active SynapseFlow knowledge scope using the configured default product, project, and app scope.",
        inputSchema: {},
      },
      async () => {
        const scope = resolveScopeInput(config, {});
        const output = await resolveScope(config, scope);
        return {
          content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }],
          structuredContent: output,
        };
      },
    );
    return;
  }

  server.registerTool(
    "kb_scope_resolve",
    {
      title: "Resolve Knowledge Scope",
      description: "Resolve the active product, project, and app scope for SynapseFlow knowledge access.",
      inputSchema: scopeInputSchema,
    },
    async ({ product_code, project_code, app_code }) => {
      const scope = resolveScopeInput(config, {
        productCode: product_code,
        projectCode: project_code,
        appCode: app_code,
      });
      const output = await resolveScope(config, scope);
      return {
        content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }],
        structuredContent: output,
      };
    },
  );
}
