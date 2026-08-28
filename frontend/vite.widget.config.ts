import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig, type Plugin } from "vite";

const STYLE_MARKER = "__AGENT_CHAT_SHADOW_CSS__";
const frontendRoot = fileURLToPath(new URL(".", import.meta.url));
const widgetVersion = String(process.env.AGENT_WIDGET_VERSION || "1.0.0").trim();

if (!/^\d+\.\d+\.\d+$/.test(widgetVersion)) {
  throw new Error("AGENT_WIDGET_VERSION must be an exact semantic version.");
}

function inlineShadowCss(): Plugin {
  return {
    name: "agent-chat-inline-shadow-css",
    enforce: "post",
    generateBundle(_, bundle) {
      const css = Object.values(bundle)
        .filter((item) => item.type === "asset" && item.fileName.endsWith(".css"))
        .map((item) => String(item.source))
        .join("\n");
      if (!css) throw new Error("Agent Widget build did not emit Shadow DOM CSS.");
      for (const [fileName, item] of Object.entries(bundle)) {
        if (item.type === "chunk") {
          item.code = item.code.replaceAll(JSON.stringify(STYLE_MARKER), JSON.stringify(css));
        } else if (fileName.endsWith(".css")) {
          delete bundle[fileName];
        }
      }
    },
  };
}

export default defineConfig({
  plugins: [vue(), inlineShadowCss()],
  publicDir: false,
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    target: "es2018",
    outDir: resolve(frontendRoot, `public/agent-static/widget/${widgetVersion}`),
    emptyOutDir: true,
    cssCodeSplit: false,
    assetsInlineLimit: 100_000,
    lib: {
      entry: resolve(frontendRoot, "src/widget/register.ts"),
      formats: ["es"],
      fileName: () => "index.js",
    },
  },
});
