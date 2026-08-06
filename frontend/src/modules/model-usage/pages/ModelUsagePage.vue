<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Calendar, Download, InfoFilled, RefreshRight, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import {
  getModelUsageSummary,
  type ModelUsageGranularity,
  type ModelUsageRow,
  type ModelUsageSummary,
  type ModelUsageTrendPoint,
} from "@/shared/api/model-usage";
import { useTeamScopeStore } from "@/stores/team-scope";

const teamScopeStore = useTeamScopeStore();
function createInitialDateRange(): [Date, Date] {
  const end = new Date();
  const start = new Date(end);
  start.setDate(end.getDate() - 6);
  return [start, end];
}

const dateRange = ref<[Date, Date]>(createInitialDateRange());
const granularity = ref<ModelUsageGranularity>("day");
const isRefreshing = ref(false);
const rows = ref<ModelUsageRow[]>([]);
const trend = ref<ModelUsageTrendPoint[]>([]);
const summary = ref<ModelUsageSummary>({
  input_tokens: 0,
  output_tokens: 0,
  total_tokens: 0,
  estimated_cost: 0,
  chat_tokens: 0,
  evaluation_tokens: 0,
});
const lastUpdated = ref("—");
const selectedRow = ref<ModelUsageRow | null>(null);
const isDrawerOpen = ref(false);
const chartCanvas = ref<HTMLCanvasElement | null>(null);
const chartFrame = ref<HTMLElement | null>(null);
let resizeObserver: ResizeObserver | null = null;
let requestVersion = 0;

const visibleRows = computed(() => {
  const selectedTeamId = teamScopeStore.selectedTeamId;
  return selectedTeamId === null
    ? rows.value
    : rows.value.filter((row) => row.team_id === selectedTeamId);
});

const chartData = computed(() => ({
  labels: trend.value.map((item) => item.label),
  costs: trend.value.map((item) => item.estimated_cost),
  tokens: trend.value.map((item) => item.total_tokens / 100_000_000),
}));

function formatCost(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `¥ ${value.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatTokens(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)}亿`;
  if (value >= 10_000) return `${Math.round(value / 10_000)}万`;
  return value.toLocaleString("zh-CN");
}

function formatDateRange(value: Date[] | null) {
  if (!value?.length) return "未选择日期";
  return value.map(dateValue).join(" 至 ");
}

function dateValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

async function loadUsage() {
  const [start, end] = dateRange.value;
  if (!start || !end) return;
  const currentVersion = ++requestVersion;
  isRefreshing.value = true;
  try {
    const response = await getModelUsageSummary({
      start_date: dateValue(start),
      end_date: dateValue(end),
      team_id: teamScopeStore.selectedTeamId,
      granularity: granularity.value,
    });
    if (currentVersion !== requestVersion) return;
    summary.value = response.summary;
    rows.value = response.rows;
    trend.value = response.trend;
    lastUpdated.value = new Intl.DateTimeFormat("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(response.updated_at)).replace(/\//g, "-");
    await nextTick();
    drawChart();
  } catch (error) {
    if (currentVersion !== requestVersion) return;
    ElMessage.error(error instanceof Error ? error.message : "成本数据加载失败");
  } finally {
    if (currentVersion === requestVersion) isRefreshing.value = false;
  }
}

function drawChart() {
  const canvas = chartCanvas.value;
  const frame = chartFrame.value;
  if (!canvas || !frame) return;
  const width = Math.max(frame.clientWidth, 620);
  const height = 270;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);

  const labels = chartData.value.labels;
  const costs = chartData.value.costs;
  const tokens = chartData.value.tokens;
  if (!labels.length) return;
  const padding = { top: 26, right: 46, bottom: 34, left: 58 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const maxCost = Math.max(...costs, 1) * 1.15;
  const maxTokens = Math.max(...tokens, 1) * 1.15;
  const x = (index: number) => padding.left + (labels.length === 1 ? chartWidth / 2 : (chartWidth * index) / (labels.length - 1));
  const yCost = (value: number) => padding.top + chartHeight - (value / maxCost) * chartHeight;
  const yToken = (value: number) => padding.top + chartHeight - (value / maxTokens) * chartHeight;

  context.font = "12px Segoe UI, PingFang SC, Microsoft YaHei, sans-serif";
  context.lineWidth = 1;
  context.strokeStyle = "#e5e9f0";
  context.fillStyle = "#64748b";
  context.textAlign = "right";
  for (let index = 0; index <= 4; index += 1) {
    const y = padding.top + (chartHeight * index) / 4;
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
    context.fillText(`${Math.round((maxCost * (4 - index)) / 4).toLocaleString("zh-CN")}`, padding.left - 10, y + 4);
  }
  context.textAlign = "center";
  labels.forEach((label, index) => context.fillText(label, x(index), height - 9));

  const drawLine = (values: number[], scale: (value: number) => number, color: string, dash: number[]) => {
    context.beginPath();
    context.setLineDash(dash);
    context.strokeStyle = color;
    context.lineWidth = 2;
    values.forEach((value, index) => (index === 0 ? context.moveTo(x(index), scale(value)) : context.lineTo(x(index), scale(value))));
    context.stroke();
    context.setLineDash([]);
    values.forEach((value, index) => {
      context.beginPath();
      context.fillStyle = "#ffffff";
      context.arc(x(index), scale(value), 4, 0, Math.PI * 2);
      context.fill();
      context.beginPath();
      context.fillStyle = color;
      context.arc(x(index), scale(value), 2.5, 0, Math.PI * 2);
      context.fill();
    });
  };
  drawLine(costs, yCost, "#2563eb", []);
  drawLine(tokens, yToken, "#60a5fa", [5, 5]);
}

function exportReport() {
  const header = ["项目应用", "团队", "总 Token", "真实问答 Token", "评估测试 Token", "估算成本（CNY）"];
  const body = visibleRows.value.map((row) => [
    row.application,
    row.team,
    row.total_tokens,
    row.chat_tokens,
    row.evaluation_tokens,
    row.estimated_cost,
  ]);
  const csv = [header, ...body]
    .map((line) => line.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    .join("\n");
  const url = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "ai-cost-center-report.csv";
  anchor.click();
  URL.revokeObjectURL(url);
  ElMessage.success("报表已导出");
}

function openRow(row: ModelUsageRow) {
  selectedRow.value = row;
  isDrawerOpen.value = true;
}

onMounted(async () => {
  await loadUsage();
  resizeObserver = new ResizeObserver(drawChart);
  if (chartFrame.value) resizeObserver.observe(chartFrame.value);
});

watch(
  [granularity, () => teamScopeStore.selectedTeamId, dateRange],
  () => void loadUsage(),
  { deep: true },
);

onBeforeUnmount(() => resizeObserver?.disconnect());
</script>

<template>
  <section class="usage-page">
    <div class="usage-toolbar">
      <div class="usage-toolbar__filters">
        <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" :clearable="false" :prefix-icon="Calendar" class="usage-date-picker" />
        <span class="usage-timezone">时区：Asia/Shanghai</span>
      </div>
      <div class="usage-toolbar__actions">
        <el-button :loading="isRefreshing" @click="loadUsage"><el-icon><RefreshRight /></el-icon>刷新</el-button>
        <el-button @click="exportReport"><el-icon><Download /></el-icon>导出</el-button>
      </div>
    </div>

    <section class="usage-metric-strip" aria-label="成本概览">
      <article class="usage-metric"><div class="usage-metric__label">估算成本（CNY） <el-icon><InfoFilled /></el-icon></div><strong class="usage-metric__value usage-metric__value--blue">{{ formatCost(summary.estimated_cost) }}</strong><span class="usage-metric__change">按当前筛选范围统计</span></article>
      <article class="usage-metric"><div class="usage-metric__label">总 Token <el-icon><InfoFilled /></el-icon></div><strong class="usage-metric__value">{{ formatTokens(summary.total_tokens) }}</strong><span class="usage-metric__change">输入 {{ formatTokens(summary.input_tokens) }} · 输出 {{ formatTokens(summary.output_tokens) }}</span></article>
      <article class="usage-metric"><div class="usage-metric__label">真实问答（Token） <el-icon><InfoFilled /></el-icon></div><strong class="usage-metric__value">{{ formatTokens(summary.chat_tokens) }}</strong><span class="usage-metric__change">来源：问答日志</span></article>
      <article class="usage-metric"><div class="usage-metric__label">评估测试（Token） <el-icon><InfoFilled /></el-icon></div><strong class="usage-metric__value">{{ formatTokens(summary.evaluation_tokens) }}</strong><span class="usage-metric__change">来源：评测 run</span></article>
    </section>

    <section class="usage-panel usage-trend-panel">
      <header class="usage-panel__header"><div><h2>成本与 Token 趋势</h2><p>数据范围：{{ formatDateRange(dateRange) }}</p></div><div class="usage-panel__controls"><div class="usage-legend"><span><i class="usage-legend__dot usage-legend__dot--cost" />估算成本（CNY）</span><span><i class="usage-legend__dot usage-legend__dot--token" />总 Token（亿）</span></div><el-radio-group v-model="granularity" size="small"><el-radio-button label="day">按日</el-radio-button><el-radio-button label="week">按周</el-radio-button><el-radio-button label="month">按月</el-radio-button></el-radio-group></div></header>
      <div ref="chartFrame" class="usage-chart-frame"><canvas ref="chartCanvas" aria-label="成本与 Token 趋势图" role="img" /><div class="usage-chart-axis usage-chart-axis--left">估算成本（CNY）</div><div class="usage-chart-axis usage-chart-axis--right">总 Token（亿）</div><div v-if="!trend.length" class="usage-chart-empty">当前时间范围暂无成本数据</div></div>
    </section>

    <section class="usage-panel usage-breakdown-panel">
      <header class="usage-panel__header usage-breakdown-panel__header"><div><h2>按项目应用分析</h2><p>{{ visibleRows.length }} 个应用 · 最近更新 {{ lastUpdated }}</p></div><el-button link type="primary" @click="exportReport">导出当前视图</el-button></header>
      <div class="usage-table-wrap"><table class="usage-table"><thead><tr><th>项目应用</th><th>团队</th><th>模型（按 Token 占比）</th><th>总 Token</th><th>真实问答（Token）</th><th>评估测试（Token）</th><th>估算成本（CNY）</th><th>数据覆盖</th><th aria-label="操作" /></tr></thead><tbody v-if="visibleRows.length"><tr v-for="row in visibleRows" :key="row.id" class="usage-table__row" @click="openRow(row)"><td><strong>{{ row.application }}</strong></td><td class="usage-table__muted">{{ row.team }}</td><td><div class="usage-model-shares"><span v-for="model in row.models.slice(0, 3)" :key="model.name" class="usage-model-chip" :class="`usage-model-chip--${model.tone}`">{{ model.name }} <b>{{ model.share }}%</b></span><span v-if="row.models.length > 3" class="usage-model-chip usage-model-chip--more">+{{ row.models.length - 3 }}</span></div></td><td>{{ formatTokens(row.total_tokens) }}</td><td>{{ formatTokens(row.chat_tokens) }}</td><td>{{ formatTokens(row.evaluation_tokens) }}</td><td>{{ formatCost(row.estimated_cost) }}</td><td><div class="usage-coverage" :class="`usage-coverage--${row.coverage_status}`"><span class="usage-coverage__dot" /><span class="usage-coverage__bar"><i :style="{ width: `${row.coverage}%` }" /></span><span>{{ row.coverage }}%</span></div></td><td><el-icon class="usage-table__arrow"><Search /></el-icon></td></tr></tbody><tbody v-else><tr><td colspan="9" class="usage-table__empty">当前团队在所选时间范围内暂无成本数据</td></tr></tbody></table></div>
    </section>

    <footer class="usage-disclaimer"><el-icon><InfoFilled /></el-icon><span>说明：估算成本基于当前模型单价计算，可能与最终账单存在差异；未配置单价的模型只统计 Token。</span></footer>

    <el-drawer v-model="isDrawerOpen" title="应用成本明细" size="420px"><template v-if="selectedRow"><div class="usage-drawer__intro"><div><span class="usage-drawer__eyebrow">项目应用</span><h3>{{ selectedRow.application }}</h3><p>{{ selectedRow.team }}</p></div><strong>{{ formatCost(selectedRow.estimated_cost) }}</strong></div><div class="usage-drawer__metrics"><div><span>总 Token</span><b>{{ formatTokens(selectedRow.total_tokens) }}</b></div><div><span>真实问答</span><b>{{ formatTokens(selectedRow.chat_tokens) }}</b></div><div><span>评估测试</span><b>{{ formatTokens(selectedRow.evaluation_tokens) }}</b></div></div><h4>模型使用占比</h4><div class="usage-drawer__models"><div v-for="model in selectedRow.models" :key="model.name"><div><span>{{ model.name }}</span><b>{{ model.share }}%</b></div><el-progress :percentage="model.share" :show-text="false" :color="model.tone === 'blue' ? '#2563eb' : model.tone === 'green' ? '#16a34a' : model.tone === 'purple' ? '#7c3aed' : '#64748b'" /></div></div><div class="usage-drawer__note"><el-icon><InfoFilled /></el-icon><span>模型明细来自问答日志和评测 run 的 Token 汇总。</span></div></template></el-drawer>
  </section>
</template>

<style scoped>
.usage-page { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.usage-toolbar, .usage-toolbar__filters, .usage-toolbar__actions { display: flex; align-items: center; gap: 10px; }
.usage-toolbar { justify-content: space-between; }
.usage-date-picker { width: 258px; }
.usage-timezone { color: var(--admin-text-muted); font-size: 13px; white-space: nowrap; }
.usage-metric-strip, .usage-panel { border: 1px solid var(--admin-border); border-radius: var(--admin-radius-lg); background: var(--admin-surface); box-shadow: var(--admin-shadow-panel); }
.usage-metric-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); overflow: hidden; }
.usage-metric { min-width: 0; padding: 18px 22px 17px; }
.usage-metric + .usage-metric { border-left: 1px solid var(--admin-border-soft); }
.usage-metric__label { display: flex; align-items: center; gap: 5px; color: var(--admin-text); font-size: 13px; font-weight: 600; }
.usage-metric__label .el-icon { color: var(--admin-text-subtle); font-size: 13px; }
.usage-metric__value { display: block; margin-top: 12px; color: var(--admin-text); font-size: 30px; font-weight: 650; letter-spacing: -.02em; line-height: 1; white-space: nowrap; }
.usage-metric__value--blue { color: var(--admin-primary); }
.usage-metric__change { display: block; margin-top: 10px; color: var(--admin-text-muted); font-size: 12px; }
.usage-panel { overflow: hidden; }
.usage-panel__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 17px 20px 13px; }
.usage-panel__header h2 { margin: 0; color: var(--admin-text); font-size: 16px; font-weight: 700; }
.usage-panel__header p { margin: 6px 0 0; color: var(--admin-text-muted); font-size: 12px; }
.usage-panel__controls { display: flex; align-items: center; gap: 20px; }
.usage-legend { display: flex; align-items: center; gap: 16px; color: var(--admin-text-secondary); font-size: 12px; }
.usage-legend span { display: inline-flex; align-items: center; gap: 6px; }
.usage-legend__dot { display: inline-block; width: 18px; height: 2px; border-radius: 99px; }
.usage-legend__dot--cost { background: var(--admin-primary); }
.usage-legend__dot--token { background: var(--admin-primary-light); border-top: 1px dashed var(--admin-primary-light); }
.usage-chart-frame { position: relative; overflow-x: auto; min-height: 276px; padding: 0 20px 6px; }
.usage-chart-frame canvas { display: block; min-width: 620px; }
.usage-chart-axis { position: absolute; top: 15px; color: var(--admin-text-muted); font-size: 11px; }
.usage-chart-axis--left { left: 20px; }
.usage-chart-axis--right { right: 22px; }
.usage-chart-empty { position: absolute; inset: 120px 0 auto; color: var(--admin-text-muted); text-align: center; font-size: 13px; }
.usage-breakdown-panel__header { align-items: center; border-bottom: 1px solid var(--admin-border-soft); background: var(--admin-surface-muted); }
.usage-table-wrap { overflow-x: auto; }
.usage-table { width: 100%; min-width: 1160px; border-collapse: collapse; color: var(--admin-text); font-size: 12px; }
.usage-table th { background: #fbfcfe; color: var(--admin-text-secondary); font-size: 11px; font-weight: 650; padding: 11px 12px; text-align: left; white-space: nowrap; }
.usage-table td { border-top: 1px solid var(--admin-border-soft); padding: 11px 12px; vertical-align: middle; white-space: nowrap; }
.usage-table__row { cursor: pointer; transition: background .15s ease; }
.usage-table__row:hover { background: var(--admin-primary-soft); }
.usage-table__row td:first-child { padding-left: 20px; }
.usage-table__row td:last-child { padding-right: 20px; }
.usage-table__muted { color: var(--admin-text-muted); }
.usage-model-shares { display: flex; align-items: center; gap: 5px; }
.usage-model-chip { display: inline-flex; align-items: center; gap: 3px; border: 1px solid; border-radius: 4px; padding: 3px 6px; font-size: 10px; }
.usage-model-chip b { font-weight: 650; }
.usage-model-chip--blue { border-color: #bfdbfe; background: #eff6ff; color: #2563eb; }
.usage-model-chip--green { border-color: #bbf7d0; background: #f0fdf4; color: #15803d; }
.usage-model-chip--purple { border-color: #ddd6fe; background: #f5f3ff; color: #6d28d9; }
.usage-model-chip--slate, .usage-model-chip--more { border-color: #cbd5e1; background: #f8fafc; color: #475569; }
.usage-coverage { display: flex; align-items: center; gap: 6px; color: var(--admin-text-secondary); font-size: 11px; }
.usage-coverage__dot { width: 7px; height: 7px; border-radius: 50%; background: #16a34a; }
.usage-coverage--partial .usage-coverage__dot { background: #f59e0b; }
.usage-coverage__bar { width: 42px; height: 4px; overflow: hidden; border-radius: 99px; background: #e2e8f0; }
.usage-coverage__bar i { display: block; height: 100%; border-radius: inherit; background: #16a34a; }
.usage-coverage--partial .usage-coverage__bar i { background: #f59e0b; }
.usage-table__empty { padding: 42px !important; color: var(--admin-text-muted); text-align: center; }
.usage-table__arrow { color: var(--admin-primary); font-size: 14px; }
.usage-disclaimer { display: flex; align-items: center; gap: 7px; padding: 0 4px 4px; color: var(--admin-text-subtle); font-size: 11px; }
.usage-disclaimer .el-icon { color: var(--admin-primary); }
.usage-drawer__intro { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--admin-border-soft); padding-bottom: 20px; }
.usage-drawer__eyebrow { color: var(--admin-primary); font-size: 11px; font-weight: 700; letter-spacing: .08em; }
.usage-drawer__intro h3 { margin: 6px 0 4px; color: var(--admin-text); font-size: 20px; }
.usage-drawer__intro p { margin: 0; color: var(--admin-text-muted); font-size: 12px; }
.usage-drawer__intro > strong { color: var(--admin-primary); font-size: 20px; }
.usage-drawer__metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding: 20px 0; }
.usage-drawer__metrics div { display: flex; flex-direction: column; gap: 6px; }
.usage-drawer__metrics span { color: var(--admin-text-muted); font-size: 11px; }
.usage-drawer__metrics b { color: var(--admin-text); font-size: 16px; }
.usage-drawer h4 { margin: 4px 0 14px; color: var(--admin-text); font-size: 14px; }
.usage-drawer__models { display: flex; flex-direction: column; gap: 16px; }
.usage-drawer__models div > div { display: flex; justify-content: space-between; margin-bottom: 6px; color: var(--admin-text-secondary); font-size: 12px; }
.usage-drawer__models b { color: var(--admin-text); }
.usage-drawer__note { display: flex; align-items: flex-start; gap: 7px; margin-top: 24px; border: 1px solid var(--admin-primary-border); border-radius: var(--admin-radius-md); background: var(--admin-primary-soft); color: var(--admin-text-secondary); font-size: 12px; line-height: 1.6; padding: 12px; }
.usage-drawer__note .el-icon { flex: 0 0 auto; color: var(--admin-primary); }
@media (max-width: 1100px) { .usage-toolbar { align-items: stretch; flex-direction: column; } .usage-toolbar__actions { justify-content: flex-end; } .usage-panel__controls { align-items: flex-end; flex-direction: column; gap: 10px; } }
@media (max-width: 760px) { .usage-metric-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); } .usage-metric:nth-child(3) { border-left: 0; border-top: 1px solid var(--admin-border-soft); } .usage-metric:nth-child(4) { border-top: 1px solid var(--admin-border-soft); } .usage-toolbar__filters { align-items: stretch; flex-direction: column; } .usage-date-picker { width: 100%; } .usage-panel__header { align-items: stretch; flex-direction: column; } .usage-panel__controls { align-items: flex-start; flex-direction: column; } }
</style>
