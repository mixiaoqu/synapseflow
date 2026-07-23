import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const composerSource = fs.readFileSync(
  path.resolve(testDir, "../src/widget/components/ChatComposer.vue"),
  "utf8",
);

assert.match(
  composerSource,
  /\.widget-composer \{[^}]*box-sizing: border-box;[^}]*min-height: 48px;[^}]*padding: 6px 10px;/,
  "助手输入区空态高度应保持紧凑",
);
assert.match(
  composerSource,
  /\.widget-composer textarea \{[^}]*min-height: 24px;[^}]*max-height: 96px;/,
  "助手文本框应限制为约一至四行高度",
);
assert.match(
  composerSource,
  /Math\.min\(textarea\.scrollHeight, 96\)/,
  "助手文本框自动增高上限应与样式一致",
);
assert.match(
  composerSource,
  /\.widget-composer button \{[^}]*height: 36px;/,
  "输入区操作按钮应与紧凑输入框匹配",
);

console.log("Widget 输入框尺寸契约检查通过");
