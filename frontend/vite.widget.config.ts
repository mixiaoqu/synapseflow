import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    outDir: "public/agent-chat",
    emptyOutDir: true,
    lib: {
      entry: fileURLToPath(new URL("./src/widget/main.ts", import.meta.url)),
      name: "AgentChat",
      formats: ["iife"],
      fileName: () => "agent-chat.js",
    },
    rollupOptions: {
      output: {
        exports: "named",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith(".css")) {
            return "agent-chat.css";
          }
          return "assets/[name]-[hash][extname]";
        },
        inlineDynamicImports: true,
      },
    },
  },
});
