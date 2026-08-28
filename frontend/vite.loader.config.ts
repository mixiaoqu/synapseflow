import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vite";

const frontendRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  publicDir: false,
  build: {
    target: "es2018",
    outDir: resolve(frontendRoot, "public/agent-static/loader/v1"),
    emptyOutDir: true,
    lib: {
      entry: resolve(frontendRoot, "src/agent-loader/loader.ts"),
      name: "EnterpriseAgentLoader",
      formats: ["iife"],
      fileName: () => "loader.js",
    },
  },
});
