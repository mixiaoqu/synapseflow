<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { listContentRiskLogs } from "@/modules/content-risk/api";
import type {
  ContentRiskLogSummary,
  ContentRiskResolvedAction,
  ContentRiskScene,
} from "@/modules/content-risk/types";
import { getErrorMessage } from "@/shared/utils/error";

type SceneFilter = "all" | ContentRiskScene;
type ActionFilter = "all" | ContentRiskResolvedAction;
type BlockedFilter = "all" | "blocked" | "recorded";

const logs = ref<ContentRiskLogSummary[]>([]);
const total = ref(0);
const loading = ref(false);

const filters = reactive({
  scene: "all" as SceneFilter,
  action: "all" as ActionFilter,
  blocked: "all" as BlockedFilter,
});

const queryHits = computed(() => logs.value.filter((item) => item.scene === "query").length);
const answerHits = computed(() => logs.value.filter((item) => item.scene === "answer").length);
const blockedHits = computed(() => logs.value.filter((item) => item.blocked).length);
const highRiskHits = computed(() => logs.value.filter((item) => item.riskLevel === "high").length);

const summaryCards = computed(() => [
  {
    label: "最近判定数",
    value: String(total.value),
    unit: "次",
    tone: "slate",
    hint: "按当前筛选条件统计后端已记录的风控判定日志。",
  },
  {
    label: "提问侧命中",
    value: String(queryHits.value),
    unit: "次",
    tone: "rose",
    hint: "用户提问场景下命中的规则记录。",
  },
  {
    label: "回答侧命中",
    value: String(answerHits.value),
    unit: "次",
    tone: "amber",
    hint: "AI 回答场景下命中的规则记录。",
  },
  {
    label: "高风险命中",
    value: String(highRiskHits.value),
    unit: "次",
    tone: "emerald",
    hint: `其中 ${blockedHits.value} 次最终动作为拦截。`,
  },
]);

function sceneLabel(value: ContentRiskScene) {
  return value === "query" ? "用户提问" : "AI 回答";
}

function actionLabel(value: ContentRiskResolvedAction) {
  const labels: Record<ContentRiskResolvedAction, string> = {
    pass: "放行",
    block: "拦截",
    review: "人工复核",
    log: "仅记录",
  };
  return labels[value];
}

function actionTagType(value: ContentRiskResolvedAction) {
  if (value === "block") {
    return "danger";
  }
  if (value === "review") {
    return "warning";
  }
  return "info";
}

function riskLevelLabel(value: ContentRiskLogSummary["riskLevel"]) {
  if (value === "high") {
    return "高风险";
  }
  if (value === "medium") {
    return "中风险";
  }
  if (value === "low") {
    return "低风险";
  }
  return "未分级";
}

function riskLevelTagType(value: ContentRiskLogSummary["riskLevel"]) {
  if (value === "high") {
    return "danger";
  }
  if (value === "medium") {
    return "warning";
  }
  if (value === "low") {
    return "info";
  }
  return "info";
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function summaryCardClass(tone: string) {
  const classes: Record<string, string> = {
    slate: "bg-slate-50 text-slate-600",
    rose: "bg-rose-50 text-rose-600",
    amber: "bg-amber-50 text-amber-600",
    emerald: "bg-emerald-50 text-emerald-600",
  };
  return classes[tone] ?? classes.slate;
}

function buildLogParams() {
  return {
    limit: 50,
    scene: filters.scene === "all" ? undefined : filters.scene,
    action: filters.action === "all" ? undefined : filters.action,
    blocked:
      filters.blocked === "all"
        ? undefined
        : filters.blocked === "blocked",
  };
}

async function loadLogs() {
  if (loading.value) {
    return;
  }

  loading.value = true;
  try {
    const response = await listContentRiskLogs(buildLogParams());
    logs.value = response.items;
    total.value = response.total;
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "加载风控日志失败"));
  } finally {
    loading.value = false;
  }
}

function primaryRuleName(log: ContentRiskLogSummary) {
  return log.hits[0]?.ruleName ?? "-";
}

function primaryProductName(log: ContentRiskLogSummary) {
  return log.productName ?? log.projectName ?? log.projectAppName ?? "全局";
}

onMounted(() => {
  void loadLogs();
});
</script>

<template>
  <div class="space-y-6">
    <section class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 class="text-2xl font-semibold tracking-tight text-slate-900">数据总览</h1>
          <p class="mt-2 max-w-3xl text-sm leading-7 text-slate-500">
            查看内容风控中心的运行状态、提问与回答命中情况，以及最近的真实风控日志。
          </p>
        </div>
        <el-button :icon="Refresh" :loading="loading" @click="loadLogs">
          刷新
        </el-button>
      </div>

      <div class="mt-6 grid gap-4 xl:grid-cols-4 md:grid-cols-2">
        <div
          v-for="card in summaryCards"
          :key="card.label"
          class="rounded-2xl border border-slate-200 bg-white px-5 py-4"
        >
          <div class="flex items-start justify-between gap-3">
            <p class="text-xs font-medium text-slate-500">{{ card.label }}</p>
            <span class="rounded-full px-2.5 py-1 text-xs font-medium" :class="summaryCardClass(card.tone)">
              {{ card.unit }}
            </span>
          </div>
          <p class="mt-4 text-3xl font-semibold tracking-tight text-slate-900">{{ card.value }}</p>
          <p class="mt-2 text-xs leading-6 text-slate-400">{{ card.hint }}</p>
        </div>
      </div>
    </section>

    <section class="rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div>
          <h2 class="text-sm font-semibold text-slate-900">最近风控日志</h2>
          <p class="mt-1 text-xs text-slate-400">展示真实命中的风控判定，测试沙盒不会写入这里。</p>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <el-select v-model="filters.scene" class="w-36" @change="loadLogs">
            <el-option label="全部场景" value="all" />
            <el-option label="用户提问" value="query" />
            <el-option label="AI 回答" value="answer" />
          </el-select>
          <el-select v-model="filters.action" class="w-36" @change="loadLogs">
            <el-option label="全部动作" value="all" />
            <el-option label="拦截" value="block" />
            <el-option label="人工复核" value="review" />
            <el-option label="仅记录" value="log" />
          </el-select>
          <el-select v-model="filters.blocked" class="w-36" @change="loadLogs">
            <el-option label="全部结果" value="all" />
            <el-option label="已拦截" value="blocked" />
            <el-option label="仅记录" value="recorded" />
          </el-select>
        </div>
      </div>

      <el-table
        v-loading="loading"
        :data="logs"
        row-key="id"
        class="content-risk-overview-page__table"
      >
        <el-table-column label="时间" min-width="150">
          <template #default="{ row }">
            <span class="text-xs text-slate-400">{{ formatDateTime(row.createdAt) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="170">
          <template #default="{ row }">
            <span class="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
              {{ primaryProductName(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="场景" min-width="110">
          <template #default="{ row }">
            <span class="text-slate-600">{{ sceneLabel(row.scene) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="原始文本片段" min-width="320">
          <template #default="{ row }">
            <p class="max-w-xl truncate text-slate-500" :title="row.checkedText">{{ row.checkedText }}</p>
            <p v-if="row.matchedText" class="mt-1 text-xs text-slate-400">命中：{{ row.matchedText }}</p>
          </template>
        </el-table-column>
        <el-table-column label="命中规则" min-width="190">
          <template #default="{ row }">
            <div class="flex flex-wrap gap-1.5">
              <el-tag size="small" type="danger" effect="plain">
                {{ primaryRuleName(row) }}
              </el-tag>
              <el-tag v-if="row.hits.length > 1" size="small" type="info" effect="plain">
                +{{ row.hits.length - 1 }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="风险" min-width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="riskLevelTagType(row.riskLevel)" effect="plain">
              {{ riskLevelLabel(row.riskLevel) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最终动作" min-width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="actionTagType(row.action)" effect="plain">
              {{ actionLabel(row.action) }}
            </el-tag>
          </template>
        </el-table-column>
        <template #empty>
          <div class="py-10 text-sm text-slate-400">暂无风控日志</div>
        </template>
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.content-risk-overview-page__table {
  width: 100%;
}
</style>
