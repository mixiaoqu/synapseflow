const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("../node_modules/typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/shared/lib/webSource.ts"), "utf8");
const output = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const context = { exports: {}, URL };
vm.runInNewContext(output, context);
const { getWebSource } = context.exports;

test("网页来源保留链接、标题和抓取时间，不冒充知识库文档", () => {
  const result = getWebSource({ metadata: {
    source_type: "web", url: "https://example.com/guide", title: "公开指南", fetched_at: "2026-08-28",
  } });
  assert.equal(result.url, "https://example.com/guide");
  assert.equal(result.title, "公开指南");
  assert.equal(result.fetchedAt, "2026-08-28");
  assert.equal(getWebSource({ metadata: { document_id: 1 } }), null);
});

test("不将脚本、相对地址或含凭据的地址渲染为链接", () => {
  for (const url of ["javascript:alert(1)", "data:text/html,hello", "/guide",
    "https://user:pass@example.com/", "https://example.com/\\n"]) {
    assert.equal(getWebSource({ metadata: { source_type: "web", url } }), null);
  }
});

test("来源链接使用新窗口隔离，聊天和日志复用相同 URL 校验", () => {
  for (const file of ["../src/widget/components/MessageItem.vue",
    "../src/modules/qa-logs/components/QaLogTraceDrawer.vue"]) {
    const content = fs.readFileSync(path.join(__dirname, file), "utf8");
    assert.match(content, /getWebSource/);
    assert.match(content, /rel="noopener noreferrer"/);
  }
});
