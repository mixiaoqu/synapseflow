import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const readSource = (relativePath) =>
  fs.readFileSync(path.resolve(testDir, relativePath), "utf8");

const panelSource = readSource("../src/widget/components/ChatPanel.vue");
const runtimeSource = readSource("../src/widget/create-agent-chat.ts");
const widgetStylesSource = readSource("../src/widget/styles.css");

assert.match(panelSource, /resizeStart: \[event: PointerEvent\]/);
assert.match(panelSource, /class="widget-chat__resize-handle"/);
assert.match(panelSource, /aria-label="调整助手窗口大小"/);
assert.match(panelSource, /@pointerdown="handleResizePointerDown"/);
assert.match(
  panelSource,
  /@media \(max-width: 640px\)[^}]*\.widget-chat__resize-handle \{ display: none;/,
  "移动端应隐藏窗口缩放手柄",
);

assert.match(runtimeSource, /const PANEL_MIN_WIDTH = 340;/);
assert.match(runtimeSource, /const PANEL_MIN_HEIGHT = 420;/);
assert.match(runtimeSource, /onResizeStart: startResizing/);
assert.match(runtimeSource, /localStorage\.getItem\(PANEL_SIZE_STORAGE_KEY\)/);
assert.match(runtimeSource, /localStorage\.setItem\(PANEL_SIZE_STORAGE_KEY/);
assert.match(runtimeSource, /--agent-chat-width/);
assert.match(runtimeSource, /--agent-chat-height/);

assert.match(
  widgetStylesSource,
  /agent-chat-widget-host--resizing/,
  "缩放过程中应显示对应的光标状态",
);

console.log("Widget 窗口缩放契约检查通过");
