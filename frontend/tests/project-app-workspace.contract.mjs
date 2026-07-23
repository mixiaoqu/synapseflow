import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const pageSource = fs.readFileSync(
  path.resolve(testDir, "../src/modules/projects/pages/ProjectAppListPage.vue"),
  "utf8",
);
const apiSource = fs.readFileSync(
  path.resolve(testDir, "../src/shared/api/agent-integrations.ts"),
  "utf8",
);

assert.match(
  apiSource,
  /export function replaceProjectAppToolGrants\(/,
  "shared API 应提供一次替换整组工具授权的命令",
);
assert.match(pageSource, /@click="openToolGrantManager"/, "主页面应提供管理授权入口");
assert.match(pageSource, /v-model="toolGrantKeyword"/, "授权管理应支持关键词搜索");
assert.match(pageSource, /v-model="toolGrantSelectedOnly"/, "授权管理应支持仅查看已授权工具");
assert.match(pageSource, /groupedAvailableTools/, "授权管理应按工具提供方分组");
assert.match(pageSource, /@click="handleSaveToolGrants"/, "授权变更应统一保存");
assert.doesNotMatch(pageSource, /handleToolGrantChange/, "页面不应继续逐项立即提交授权");

assert.match(pageSource, /v-model="sandboxDrawerVisible"/, "沙盒测试应迁移到按需打开的抽屉");
assert.match(
  pageSource,
  /\.project-app-workspace-page__sandbox-drawer-content\s*\{[^}]*width:\s*100%;[^}]*flex:\s*1;/,
  "沙盒内容应占满抽屉内部可用宽度",
);
assert.match(pageSource, /@click="openSandbox"/, "应用状态区应保留沙盒测试入口");
assert.doesNotMatch(
  pageSource,
  /<section class="project-app-workspace-page__sandbox">/,
  "沙盒不应继续作为常驻右栏",
);
assert.doesNotMatch(
  pageSource,
  /grid-template-columns:\s*minmax\(420px, 460px\)\s+minmax\(640px, 1fr\)/,
  "应用配置主体不应继续使用压缩配置区的双栏布局",
);

console.log("应用端配置工作区契约检查通过");
