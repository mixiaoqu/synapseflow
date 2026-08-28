import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const pageSource = fs.readFileSync(
  path.resolve(testDir, "../src/modules/agent-integrations/pages/AgentIntegrationPage.vue"),
  "utf8",
);
const apiSource = fs.readFileSync(
  path.resolve(testDir, "../src/shared/api/agent-integrations.ts"),
  "utf8",
);

assert.match(apiSource, /export function batchPublishAgentTools\(/, "shared API 应提供批量发布命令");
assert.match(pageSource, /type="selection"/, "工具表格应支持多选");
assert.match(pageSource, /@click="publishSelectedTools"/, "页面应提供批量发布入口");
assert.match(pageSource, /<el-pagination/, "工具列表应提供分页控件");
assert.match(pageSource, /page:\s*toolPage\.value/, "工具列表应请求当前页");
assert.match(pageSource, /page_size:\s*toolPageSize\.value/, "工具列表应请求当前分页大小");
assert.match(pageSource, /toolTotal\.value\s*=\s*response\.total/, "页面应使用服务端总数");
assert.match(pageSource, /class="tool-table-area"/, "工具表格应位于可伸缩的内容区域");
assert.match(pageSource, /height="100%"/, "工具表格应在内容区域内滚动");
assert.match(pageSource, /\.agent-integration-page\s*\{[^}]*height:\s*calc\(100vh - 112px\)/s, "工具页应使用视口剩余高度");
assert.match(pageSource, /const toolPageSize = ref\(10\)/, "工具列表默认每页应显示 10 条");
assert.match(pageSource, /:page-sizes="\[10, 20, 50, 100\]"/, "工具列表分页选项应包含每页 10 条");
assert.doesNotMatch(pageSource, /class="tool-panel__provider"/, "工具面板不应重复展示 Provider 信息区");
assert.doesNotMatch(pageSource, /\{\{ selectedProvider\.base_url \}\}/, "工具面板不应重复展示 Provider 地址");

console.log("工具管理批量发布与分页契约检查通过");
