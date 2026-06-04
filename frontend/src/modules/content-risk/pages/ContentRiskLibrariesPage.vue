<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { Plus, Search, Setting } from "@element-plus/icons-vue";

import {
  createContentRiskLibrary,
  createContentRiskRule,
  listContentRiskLibraries,
  listContentRiskRules,
  testContentRiskText,
  updateContentRiskLibrary,
  updateContentRiskRule,
} from "@/modules/content-risk/api";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { getErrorMessage, isForbiddenError } from "@/shared/utils/error";
import type {
  ContentRiskAction,
  ContentRiskLevel,
  ContentRiskLibrarySummary,
  ContentRiskLibraryUpsertPayload,
  ContentRiskMatchMode,
  ContentRiskRuleSummary,
  ContentRiskRuleType,
  ContentRiskRuleUpsertPayload,
  ContentRiskScene,
  ContentRiskTestResult,
} from "@/modules/content-risk/types";

type LibraryStatusFilter = "all" | "enabled" | "disabled";
type RuleStatusFilter = "all" | "enabled" | "disabled";
type RuleSceneFilter = "all" | "query" | "answer";

const libraries = ref<ContentRiskLibrarySummary[]>([]);
const selectedLibrary = ref<ContentRiskLibrarySummary | null>(null);
const rules = ref<ContentRiskRuleSummary[]>([]);
const loadingLibraries = ref(false);
const loadingRules = ref(false);
const libraryLoadError = ref<unknown>(null);
const ruleLoadError = ref<unknown>(null);
const libraryDialogVisible = ref(false);
const ruleDialogVisible = ref(false);
const savingLibrary = ref(false);
const savingRule = ref(false);
const editingLibrary = ref<ContentRiskLibrarySummary | null>(null);
const editingRule = ref<ContentRiskRuleSummary | null>(null);
const sandboxVisible = ref(false);
const sandboxTesting = ref(false);
const sandboxText = ref("请问加你微信可以拿资料吗？我的 v 心是 admin123，速加！");
const sandboxScene = ref<ContentRiskScene>("query");
const sandboxResult = ref<ContentRiskTestResult | null>(null);

const libraryFilters = reactive({
  keyword: "",
  status: "all" as LibraryStatusFilter,
});

const ruleFilters = reactive({
  keyword: "",
  status: "all" as RuleStatusFilter,
  scene: "all" as RuleSceneFilter,
});

const libraryForm = reactive({
  name: "",
  description: "",
  enabled: true,
});

const ruleForm = reactive({
  name: "",
  description: "",
  rule_type: "keyword" as ContentRiskRuleType,
  match_mode: "contains" as ContentRiskMatchMode,
  pattern: "",
  risk_category: "",
  risk_level: "medium" as ContentRiskLevel,
  default_action: "block" as ContentRiskAction,
  applies_to_query: true,
  applies_to_answer: false,
  enabled: true,
});

const displayedLibraries = computed(() => {
  const keyword = libraryFilters.keyword.trim().toLowerCase();

  return libraries.value.filter((item) => {
    const matchesKeyword =
      keyword.length === 0 ||
      [item.name, item.description ?? ""].some((value) => value.toLowerCase().includes(keyword));
    const matchesStatus =
      libraryFilters.status === "all" ||
      (libraryFilters.status === "enabled" ? item.enabled : !item.enabled);
    return matchesKeyword && matchesStatus;
  });
});

const displayedRules = computed(() => {
  const keyword = ruleFilters.keyword.trim().toLowerCase();

  return rules.value.filter((item) => {
    const matchesKeyword =
      keyword.length === 0 ||
      [item.name, item.description ?? "", item.pattern, item.riskCategory].some((value) =>
        value.toLowerCase().includes(keyword),
      );
    const matchesStatus =
      ruleFilters.status === "all" ||
      (ruleFilters.status === "enabled" ? item.enabled : !item.enabled);
    const matchesScene =
      ruleFilters.scene === "all" ||
      (ruleFilters.scene === "query" ? item.appliesToQuery : item.appliesToAnswer);
    return matchesKeyword && matchesStatus && matchesScene;
  });
});

const enabledLibraryCount = computed(() => libraries.value.filter((item) => item.enabled).length);
const totalRuleCount = computed(() =>
  libraries.value.reduce((total, item) => total + item.ruleCount, 0),
);
const enabledRuleCount = computed(() => rules.value.filter((item) => item.enabled).length);
const sandboxSceneLabel = computed(() => (sandboxScene.value === "query" ? "用户提问" : "AI 回答"));
const libraryIsForbidden = computed(
  () => Boolean(libraryLoadError.value) && isForbiddenError(libraryLoadError.value),
);
const ruleIsForbidden = computed(
  () => Boolean(ruleLoadError.value) && isForbiddenError(ruleLoadError.value),
);
const hasLibraryFilters = computed(
  () => libraryFilters.keyword.trim().length > 0 || libraryFilters.status !== "all",
);
const hasRuleFilters = computed(
  () =>
    ruleFilters.keyword.trim().length > 0 ||
    ruleFilters.status !== "all" ||
    ruleFilters.scene !== "all",
);

function formatDateTime(value: string | null) {
  if (!value) {
    return "暂无记录";
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

function ruleTypeLabel(value: ContentRiskRuleType) {
  return value === "regex" ? "正则" : "关键词";
}

function matchModeLabel(value: ContentRiskMatchMode) {
  const labels: Record<ContentRiskMatchMode, string> = {
    contains: "包含",
    exact: "精确",
    regex: "正则",
  };
  return labels[value];
}

function levelTagType(value: ContentRiskLevel) {
  if (value === "high") {
    return "danger";
  }
  if (value === "medium") {
    return "warning";
  }
  return "info";
}

function levelLabel(value: ContentRiskLevel) {
  const labels: Record<ContentRiskLevel, string> = {
    low: "低风险",
    medium: "中风险",
    high: "高风险",
  };
  return labels[value];
}

function actionLabel(value: ContentRiskAction) {
  const labels: Record<ContentRiskAction, string> = {
    block: "拦截",
    review: "复核",
    log: "仅记录",
  };
  return labels[value];
}

function actionTagType(value: ContentRiskAction) {
  if (value === "block") {
    return "danger";
  }
  if (value === "review") {
    return "warning";
  }
  return "info";
}

function sandboxActionLabel(value: ContentRiskTestResult["action"]) {
  if (value === "pass") {
    return "放行";
  }
  return actionLabel(value);
}

function sandboxActionTone(value: ContentRiskTestResult["action"]) {
  if (value === "block") {
    return "danger";
  }
  if (value === "review") {
    return "warning";
  }
  if (value === "log") {
    return "info";
  }
  return "success";
}

function resetLibraryFilters() {
  libraryFilters.keyword = "";
  libraryFilters.status = "all";
}

function resetRuleFilters() {
  ruleFilters.keyword = "";
  ruleFilters.status = "all";
  ruleFilters.scene = "all";
}

function resetLibraryForm() {
  libraryForm.name = "";
  libraryForm.description = "";
  libraryForm.enabled = true;
}

function resetRuleForm() {
  ruleForm.name = "";
  ruleForm.description = "";
  ruleForm.rule_type = "keyword";
  ruleForm.match_mode = "contains";
  ruleForm.pattern = "";
  ruleForm.risk_category = "";
  ruleForm.risk_level = "medium";
  ruleForm.default_action = "block";
  ruleForm.applies_to_query = true;
  ruleForm.applies_to_answer = false;
  ruleForm.enabled = true;
}

async function loadLibraries() {
  if (loadingLibraries.value) {
    return;
  }

  loadingLibraries.value = true;
  libraryLoadError.value = null;

  try {
    libraries.value = await listContentRiskLibraries();
    if (selectedLibrary.value) {
      selectedLibrary.value =
        libraries.value.find((item) => item.id === selectedLibrary.value?.id) ?? selectedLibrary.value;
    }
  } catch (error) {
    libraryLoadError.value = error;
  } finally {
    loadingLibraries.value = false;
  }
}

async function loadRules(libraryId: number) {
  if (loadingRules.value) {
    return;
  }

  loadingRules.value = true;
  ruleLoadError.value = null;

  try {
    rules.value = await listContentRiskRules(libraryId);
  } catch (error) {
    ruleLoadError.value = error;
  } finally {
    loadingRules.value = false;
  }
}

function openCreateLibraryDialog() {
  editingLibrary.value = null;
  resetLibraryForm();
  libraryDialogVisible.value = true;
}

function openEditLibraryDialog(library: ContentRiskLibrarySummary) {
  editingLibrary.value = library;
  libraryForm.name = library.name;
  libraryForm.description = library.description ?? "";
  libraryForm.enabled = library.enabled;
  libraryDialogVisible.value = true;
}

function openCreateRuleDialog() {
  if (!selectedLibrary.value) {
    return;
  }

  editingRule.value = null;
  resetRuleForm();
  ruleDialogVisible.value = true;
}

function openEditRuleDialog(rule: ContentRiskRuleSummary) {
  editingRule.value = rule;
  ruleForm.name = rule.name;
  ruleForm.description = rule.description ?? "";
  ruleForm.rule_type = rule.ruleType;
  ruleForm.match_mode = rule.matchMode;
  ruleForm.pattern = rule.pattern;
  ruleForm.risk_category = rule.riskCategory;
  ruleForm.risk_level = rule.riskLevel;
  ruleForm.default_action = rule.defaultAction;
  ruleForm.applies_to_query = rule.appliesToQuery;
  ruleForm.applies_to_answer = rule.appliesToAnswer;
  ruleForm.enabled = rule.enabled;
  ruleDialogVisible.value = true;
}

async function submitLibraryForm() {
  if (savingLibrary.value) {
    return;
  }

  if (!libraryForm.name.trim()) {
    ElMessage.warning("请填写规则库名称。");
    return;
  }

  savingLibrary.value = true;

  try {
    const payload: ContentRiskLibraryUpsertPayload = {
      name: libraryForm.name.trim(),
      description: libraryForm.description.trim() || null,
      enabled: libraryForm.enabled,
    };

    if (editingLibrary.value) {
      await updateContentRiskLibrary(editingLibrary.value.id, payload);
      ElMessage.success("规则库配置已更新。");
    } else {
      await createContentRiskLibrary(payload);
      ElMessage.success("规则库已创建。");
    }

    libraryDialogVisible.value = false;
    await loadLibraries();
  } catch (error) {
    const message = error instanceof Error ? error.message : "保存规则库失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    savingLibrary.value = false;
  }
}

async function submitRuleForm() {
  if (savingRule.value || !selectedLibrary.value) {
    return;
  }

  if (!ruleForm.name.trim() || !ruleForm.pattern.trim() || !ruleForm.risk_category.trim()) {
    ElMessage.warning("请填写规则名称、匹配内容和风险分类。");
    return;
  }

  if (!ruleForm.applies_to_query && !ruleForm.applies_to_answer) {
    ElMessage.warning("至少选择一个适用场景。");
    return;
  }

  savingRule.value = true;

  try {
    const payload: ContentRiskRuleUpsertPayload = {
      name: ruleForm.name.trim(),
      description: ruleForm.description.trim() || null,
      rule_type: ruleForm.rule_type,
      match_mode: ruleForm.match_mode,
      pattern: ruleForm.pattern.trim(),
      risk_category: ruleForm.risk_category.trim(),
      risk_level: ruleForm.risk_level,
      default_action: ruleForm.default_action,
      applies_to_query: ruleForm.applies_to_query,
      applies_to_answer: ruleForm.applies_to_answer,
      enabled: ruleForm.enabled,
    };

    if (editingRule.value) {
      await updateContentRiskRule(selectedLibrary.value.id, editingRule.value.id, payload);
      ElMessage.success("规则明细已更新。");
    } else {
      await createContentRiskRule(selectedLibrary.value.id, payload);
      ElMessage.success("规则明细已创建。");
    }

    ruleDialogVisible.value = false;
    await Promise.all([loadRules(selectedLibrary.value.id), loadLibraries()]);
  } catch (error) {
    const message = error instanceof Error ? error.message : "保存规则失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    savingRule.value = false;
  }
}

function openRules(library: ContentRiskLibrarySummary) {
  selectedLibrary.value = library;
  resetRuleFilters();
  void loadRules(library.id);
}

function backToLibraries() {
  selectedLibrary.value = null;
  rules.value = [];
  ruleLoadError.value = null;
}

function openTestingSandbox() {
  sandboxResult.value = null;
  sandboxVisible.value = true;
}

async function runSandboxTest() {
  if (sandboxTesting.value) {
    return;
  }

  if (!sandboxText.value.trim()) {
    ElMessage.warning("请输入需要测试的文本。");
    return;
  }

  sandboxTesting.value = true;
  sandboxResult.value = null;

  try {
    sandboxResult.value = await testContentRiskText({
      scene: sandboxScene.value,
      text: sandboxText.value.trim(),
    });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "规则测试失败，请稍后重试。"));
  } finally {
    sandboxTesting.value = false;
  }
}

onMounted(() => {
  void loadLibraries();
});
</script>

<template>
  <section class="content-risk-library-page">
    <template v-if="!selectedLibrary">
      <header class="rounded-3xl bg-white p-6 shadow-sm">
        <div class="flex flex-wrap items-start justify-between gap-5">
          <div class="max-w-3xl">
            <p class="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
              Content Risk
            </p>
            <h1 class="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
              全局规则库
            </h1>
            <p class="mt-2 text-sm leading-7 text-slate-500">
              统一维护平台全局生效的规则库。启用的规则会按自身适用场景参与用户提问和 AI 回答检测。
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-3">
            <el-button disabled>
              批量导入
            </el-button>
            <el-button
              type="primary"
              @click="openCreateLibraryDialog"
            >
              <el-icon><Plus /></el-icon>
              新建规则库
            </el-button>
          </div>
        </div>
      </header>

      <section class="grid gap-4 md:grid-cols-3">
        <div class="rounded-2xl bg-white px-5 py-4 shadow-sm">
          <p class="text-xs text-slate-400">
            规则库总数
          </p>
          <p class="mt-2 text-3xl font-semibold text-slate-900">
            {{ libraries.length }}
          </p>
        </div>
        <div class="rounded-2xl bg-white px-5 py-4 shadow-sm">
          <p class="text-xs text-emerald-600">
            启用中
          </p>
          <p class="mt-2 text-3xl font-semibold text-emerald-700">
            {{ enabledLibraryCount }}
          </p>
        </div>
        <div class="rounded-2xl bg-white px-5 py-4 shadow-sm">
          <p class="text-xs text-slate-400">
            规则总量
          </p>
          <p class="mt-2 text-3xl font-semibold text-slate-900">
            {{ totalRuleCount }}
          </p>
        </div>
      </section>

      <AppLoading
        v-if="loadingLibraries"
        title="全局规则库加载中"
        description="正在获取当前平台的规则库配置，请稍候。"
        :blocks="4"
      />

      <AppError
        v-else-if="libraryLoadError && !libraryIsForbidden"
        title="全局规则库加载失败"
        description="暂时无法获取规则库列表，请稍后重试。"
        :error="libraryLoadError"
        @retry="loadLibraries"
      />

      <AppError
        v-else-if="libraryIsForbidden"
        title="无权查看全局规则库"
        description="当前账号没有访问内容风控规则库的权限。"
        :error="libraryLoadError"
        :show-retry="false"
      />

      <section
        v-else
        class="content-risk-library-page__list-panel"
      >
        <section class="content-risk-library-page__toolbar">
          <div class="flex flex-wrap items-center gap-3">
            <el-input
              v-model="libraryFilters.keyword"
              clearable
              placeholder="搜索规则库名称或说明..."
              class="content-risk-library-page__search"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>

            <el-select
              v-model="libraryFilters.status"
              class="content-risk-library-page__status"
            >
              <el-option
                label="全部状态"
                value="all"
              />
              <el-option
                label="仅启用中"
                value="enabled"
              />
              <el-option
                label="仅停用中"
                value="disabled"
              />
            </el-select>
          </div>

          <span class="rounded-xl bg-slate-50 px-4 py-2 text-sm text-slate-500">
            共 {{ displayedLibraries.length }} 个规则库
          </span>
        </section>

        <AppEmpty
          v-if="displayedLibraries.length === 0"
          :title="hasLibraryFilters ? '未找到相关规则库' : '暂无全局规则库'"
          :description="
            hasLibraryFilters
              ? '请尝试更换关键词或清除筛选条件。'
              : '可以先创建一个规则库，再进入规则明细维护具体匹配规则。'
          "
        >
            <el-button
              v-if="hasLibraryFilters"
              link
              type="primary"
              @click="resetLibraryFilters"
            >
              清除筛选
            </el-button>
            <el-button
              v-else
              type="primary"
              @click="openCreateLibraryDialog"
            >
              创建规则库
            </el-button>
        </AppEmpty>

        <div
          v-else
          class="grid gap-5 md:grid-cols-2 xl:grid-cols-3"
        >
          <article
            v-for="library in displayedLibraries"
            :key="library.id"
            class="group flex min-h-[260px] flex-col rounded-3xl bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="min-w-0">
                <h2 class="truncate text-lg font-semibold text-slate-900">
                  {{ library.name }}
                </h2>
                <p class="mt-1 text-xs text-slate-400">
                  更新于 {{ formatDateTime(library.updatedAt) }}
                </p>
              </div>
              <el-tag
                :type="library.enabled ? 'success' : 'info'"
                effect="plain"
                round
              >
                {{ library.enabled ? "启用中" : "已停用" }}
              </el-tag>
            </div>

            <p class="mt-4 line-clamp-2 flex-1 text-sm leading-7 text-slate-500">
              {{ library.description?.trim() || "暂无说明，可在配置中补充规则库的适用边界。" }}
            </p>

            <div class="mt-5 grid grid-cols-2 gap-3 rounded-2xl bg-slate-50 p-4">
              <div>
                <p class="text-xs text-slate-400">
                  规则数量
                </p>
                <p class="mt-1 text-2xl font-semibold text-slate-900">
                  {{ library.ruleCount }}
                </p>
              </div>
              <div>
                <p class="text-xs text-slate-400">
                  今日拦截
                </p>
                <p class="mt-1 text-2xl font-semibold text-slate-400">
                  -
                </p>
              </div>
            </div>

            <div class="mt-5 flex gap-2 border-t border-slate-100 pt-4">
              <el-button
                class="flex-1"
                @click="openEditLibraryDialog(library)"
              >
                <el-icon><Setting /></el-icon>
                配置
              </el-button>
              <el-button
                type="primary"
                class="flex-1"
                @click="openRules(library)"
              >
                规则明细
              </el-button>
            </div>
          </article>
        </div>
      </section>
    </template>

    <template v-else>
      <div class="flex items-center gap-2 text-sm text-slate-500">
        <button
          type="button"
          class="transition hover:text-slate-900"
          @click="backToLibraries"
        >
          ← 返回大盘
        </button>
        <span class="text-slate-300">/</span>
        <span class="font-medium text-slate-900">{{ selectedLibrary.name }}</span>
        <span class="text-slate-300">/</span>
        <span>规则明细</span>
      </div>

      <section class="rounded-3xl bg-white p-5 shadow-sm">
        <div class="flex flex-wrap items-center justify-between gap-5">
          <div class="grid flex-1 gap-4 sm:grid-cols-3">
            <div>
              <p class="text-xs text-slate-400">
                规则总数
              </p>
              <p class="mt-1 text-2xl font-semibold text-slate-900">
                {{ rules.length }}
              </p>
            </div>
            <div>
              <p class="text-xs text-slate-400">
                启用中
              </p>
              <p class="mt-1 text-2xl font-semibold text-emerald-600">
                {{ enabledRuleCount }}
              </p>
            </div>
            <div>
              <p class="text-xs text-slate-400">
                今日总拦截
              </p>
              <p class="mt-1 text-2xl font-semibold text-slate-400">
                -
              </p>
            </div>
          </div>

          <el-button
            type="primary"
            plain
            @click="openTestingSandbox"
          >
            打开测试沙盒
          </el-button>
        </div>
      </section>

      <AppLoading
        v-if="loadingRules"
        title="规则明细加载中"
        description="正在获取当前规则库下的规则配置，请稍候。"
        :blocks="4"
      />

      <AppError
        v-else-if="ruleLoadError && !ruleIsForbidden"
        title="规则明细加载失败"
        description="暂时无法获取规则列表，请稍后重试。"
        :error="ruleLoadError"
        @retry="selectedLibrary ? loadRules(selectedLibrary.id) : undefined"
      />

      <AppError
        v-else-if="ruleIsForbidden"
        title="无权查看规则明细"
        description="当前账号没有访问该规则库明细的权限。"
        :error="ruleLoadError"
        :show-retry="false"
      />

      <section
        v-else
        class="content-risk-library-page__table-panel"
      >
        <section class="content-risk-library-page__toolbar">
          <div class="flex flex-wrap items-center gap-3">
            <el-input
              v-model="ruleFilters.keyword"
              clearable
              placeholder="搜索规则名称、分类或匹配内容..."
              class="content-risk-library-page__rule-search"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>

            <el-select
              v-model="ruleFilters.scene"
              class="content-risk-library-page__status"
            >
              <el-option
                label="全部场景"
                value="all"
              />
              <el-option
                label="用户提问"
                value="query"
              />
              <el-option
                label="AI 回答"
                value="answer"
              />
            </el-select>

            <el-select
              v-model="ruleFilters.status"
              class="content-risk-library-page__status"
            >
              <el-option
                label="全部状态"
                value="all"
              />
              <el-option
                label="已启用"
                value="enabled"
              />
              <el-option
                label="已停用"
                value="disabled"
              />
            </el-select>
          </div>

          <el-button
            type="primary"
            @click="openCreateRuleDialog"
          >
            <el-icon><Plus /></el-icon>
            新建规则
          </el-button>
        </section>

        <AppEmpty
          v-if="displayedRules.length === 0"
          :title="hasRuleFilters ? '未找到相关规则' : '暂无规则明细'"
          :description="
            hasRuleFilters
              ? '请尝试更换关键词、场景或状态筛选。'
              : '这个规则库还没有具体规则，可以先新增一条关键词或正则规则。'
          "
        >
          <el-button
            v-if="hasRuleFilters"
            link
            type="primary"
            @click="resetRuleFilters"
          >
            清除筛选
          </el-button>
          <el-button
            v-else
            type="primary"
            @click="openCreateRuleDialog"
          >
            新建规则
          </el-button>
        </AppEmpty>

        <el-table
          v-else
          :data="displayedRules"
          row-key="id"
        >
          <el-table-column
            label="排位"
            width="72"
            align="center"
          >
            <template #default="{ $index }">
              <span class="font-mono text-xs text-slate-400">#{{ $index + 1 }}</span>
            </template>
          </el-table-column>
          <el-table-column
            label="规则名称"
            min-width="260"
          >
            <template #default="{ row }">
              <div class="content-risk-library-page__name-cell">
                <strong>{{ row.name }}</strong>
                <span>{{ row.description?.trim() || row.pattern }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            label="匹配方式"
            min-width="140"
          >
            <template #default="{ row }">
              <div class="flex flex-wrap gap-1.5">
                <el-tag
                  size="small"
                  type="info"
                  effect="plain"
                >
                  {{ ruleTypeLabel(row.ruleType) }}
                </el-tag>
                <el-tag
                  size="small"
                  effect="plain"
                >
                  {{ matchModeLabel(row.matchMode) }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            label="风险"
            min-width="150"
          >
            <template #default="{ row }">
              <div class="flex flex-wrap gap-1.5">
                <el-tag
                  size="small"
                  :type="levelTagType(row.riskLevel)"
                  effect="plain"
                >
                  {{ levelLabel(row.riskLevel) }}
                </el-tag>
                <el-tag
                  size="small"
                  type="info"
                  effect="plain"
                >
                  {{ row.riskCategory }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            label="动作"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="actionTagType(row.defaultAction)"
                effect="plain"
              >
                {{ actionLabel(row.defaultAction) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="适用场景"
            min-width="150"
          >
            <template #default="{ row }">
              <div class="flex flex-wrap gap-1.5">
                <el-tag
                  v-if="row.appliesToQuery"
                  size="small"
                  effect="plain"
                >
                  用户提问
                </el-tag>
                <el-tag
                  v-if="row.appliesToAnswer"
                  size="small"
                  effect="plain"
                >
                  AI 回答
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            label="状态"
            width="100"
            align="center"
          >
            <template #default="{ row }">
              <el-tag
                :type="row.enabled ? 'success' : 'info'"
                effect="plain"
                round
              >
                {{ row.enabled ? "启用" : "停用" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="历史命中"
            width="110"
            align="center"
          >
            <template #default>
              <span class="text-slate-400">-</span>
            </template>
          </el-table-column>
          <el-table-column
            label="操作"
            width="110"
            fixed="right"
            align="right"
          >
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                @click="openEditRuleDialog(row)"
              >
                编辑
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </template>

    <el-drawer
      v-model="sandboxVisible"
      title="规则仿真测试台"
      size="560px"
      append-to-body
      destroy-on-close
      class="content-risk-library-page__sandbox"
    >
      <template #header>
        <div>
          <h2 class="m-0 text-base font-semibold text-slate-900">
            规则仿真测试台
          </h2>
          <p class="mt-1 text-xs text-slate-500">
            使用全局已启用规则，检测{{ sandboxSceneLabel }}场景下的命中结果。
          </p>
        </div>
      </template>

      <div class="content-risk-library-page__sandbox-body">
        <section class="rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div class="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-4 py-3">
            <span class="text-sm font-semibold text-slate-700">测试文本</span>
            <span class="font-mono text-xs text-slate-400">{{ sandboxText.length }} / 500</span>
          </div>

          <el-input
            v-model="sandboxText"
            type="textarea"
            :rows="7"
            maxlength="500"
            resize="none"
            placeholder="请输入需要测试的用户提问或 AI 回答文本..."
            class="content-risk-library-page__sandbox-input"
          />

          <div class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50 px-4 py-3">
            <el-radio-group v-model="sandboxScene">
              <el-radio value="query">
                用户提问
              </el-radio>
              <el-radio value="answer">
                AI 回答
              </el-radio>
            </el-radio-group>

            <el-button
              type="primary"
              :loading="sandboxTesting"
              @click="runSandboxTest"
            >
              执行测试
            </el-button>
          </div>
        </section>

        <section
          v-if="sandboxResult"
          class="space-y-4"
        >
          <article
            class="rounded-2xl border px-5 py-4 shadow-sm"
            :class="
              sandboxResult.action === 'block'
                ? 'border-rose-200 bg-rose-50'
                : sandboxResult.action === 'review'
                  ? 'border-amber-200 bg-amber-50'
                  : 'border-slate-200 bg-white'
            "
          >
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p class="text-sm font-semibold text-slate-900">
                  检测结论：{{ sandboxResult.hits.length > 0 ? "命中规则" : "未命中规则" }}
                </p>
                <p class="mt-1 text-xs text-slate-500">
                  场景：{{ sandboxSceneLabel }} · 命中 {{ sandboxResult.hits.length }} 条规则 ·
                  耗时 {{ sandboxResult.elapsedMs }}ms
                </p>
              </div>
              <el-tag
                :type="sandboxActionTone(sandboxResult.action)"
                effect="plain"
                round
              >
                {{ sandboxActionLabel(sandboxResult.action) }}
              </el-tag>
            </div>

            <p
              v-if="sandboxResult.riskLevel"
              class="mt-3 text-xs text-slate-500"
            >
              最高风险等级：{{ levelLabel(sandboxResult.riskLevel) }}
            </p>
          </article>

          <article class="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
            <h3 class="text-sm font-semibold text-slate-900">
              命中明细
            </h3>

            <div
              v-if="sandboxResult.hits.length === 0"
              class="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-400"
            >
              当前文本没有命中全局启用规则。
            </div>

            <div
              v-else
              class="mt-4 space-y-3"
            >
              <div
                v-for="hit in sandboxResult.hits"
                :key="`${hit.libraryId}-${hit.ruleId}`"
                class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"
              >
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p class="text-sm font-semibold text-slate-900">
                      {{ hit.ruleName }}
                    </p>
                    <p class="mt-1 text-xs text-slate-500">
                      {{ hit.riskCategory }} · {{ matchModeLabel(hit.matchMode) }} · {{ hit.pattern }}
                    </p>
                  </div>
                  <div class="flex flex-wrap gap-1.5">
                    <el-tag
                      size="small"
                      :type="levelTagType(hit.riskLevel)"
                      effect="plain"
                    >
                      {{ levelLabel(hit.riskLevel) }}
                    </el-tag>
                    <el-tag
                      size="small"
                      :type="actionTagType(hit.action)"
                      effect="plain"
                    >
                      {{ actionLabel(hit.action) }}
                    </el-tag>
                  </div>
                </div>
                <p class="mt-2 text-xs text-slate-500">
                  命中文本：{{ hit.matchedText }}
                </p>
              </div>
            </div>
          </article>

          <article class="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
            <h3 class="text-sm font-semibold text-slate-900">
              本次生效范围
            </h3>
            <p class="mt-2 text-xs leading-6 text-slate-500">
              来源：全局规则库 · 仅检测“已启用且适用于{{ sandboxSceneLabel }}”的规则。
            </p>
          </article>
        </section>

        <section
          v-else
          class="rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-8 text-center"
        >
          <p class="text-sm font-semibold text-slate-700">
            输入文本后执行测试
          </p>
          <p class="mt-2 text-xs leading-6 text-slate-400">
            结果会以结论卡片和命中明细展示，不再显示不直观的原始代码。
          </p>
        </section>
      </div>
    </el-drawer>

    <el-dialog
      v-model="libraryDialogVisible"
      :title="editingLibrary ? '编辑规则库' : '新建规则库'"
      width="520px"
      destroy-on-close
    >
      <el-form
        label-position="top"
        @submit.prevent="submitLibraryForm"
      >
        <el-form-item
          label="规则库名称"
          required
        >
          <el-input
            v-model="libraryForm.name"
            maxlength="100"
            show-word-limit
            placeholder="例如：广告引流规则库"
          />
        </el-form-item>
        <el-form-item label="规则库说明">
          <el-input
            v-model="libraryForm.description"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="说明这个规则库覆盖的风险边界"
          />
        </el-form-item>
        <el-form-item label="规则库状态">
          <el-switch
            v-model="libraryForm.enabled"
            inline-prompt
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="content-risk-library-page__dialog-footer">
          <el-button @click="libraryDialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="savingLibrary"
            @click="submitLibraryForm"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="ruleDialogVisible"
      :title="editingRule ? '编辑规则' : '新建规则'"
      width="680px"
      destroy-on-close
    >
      <el-form
        label-position="top"
        @submit.prevent="submitRuleForm"
      >
        <div class="grid gap-4 sm:grid-cols-2">
          <el-form-item
            label="规则名称"
            required
          >
            <el-input
              v-model="ruleForm.name"
              maxlength="100"
              show-word-limit
              placeholder="例如：微信导流 A 类"
            />
          </el-form-item>
          <el-form-item
            label="风险分类"
            required
          >
            <el-input
              v-model="ruleForm.risk_category"
              maxlength="80"
              placeholder="例如：广告引流"
            />
          </el-form-item>
          <el-form-item label="规则类型">
            <el-select
              v-model="ruleForm.rule_type"
              class="content-risk-library-page__dialog-field"
            >
              <el-option
                label="关键词"
                value="keyword"
              />
              <el-option
                label="正则"
                value="regex"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="匹配方式">
            <el-select
              v-model="ruleForm.match_mode"
              class="content-risk-library-page__dialog-field"
            >
              <el-option
                label="包含"
                value="contains"
              />
              <el-option
                label="精确"
                value="exact"
              />
              <el-option
                label="正则"
                value="regex"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="风险等级">
            <el-select
              v-model="ruleForm.risk_level"
              class="content-risk-library-page__dialog-field"
            >
              <el-option
                label="低风险"
                value="low"
              />
              <el-option
                label="中风险"
                value="medium"
              />
              <el-option
                label="高风险"
                value="high"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="默认动作">
            <el-select
              v-model="ruleForm.default_action"
              class="content-risk-library-page__dialog-field"
            >
              <el-option
                label="拦截"
                value="block"
              />
              <el-option
                label="复核"
                value="review"
              />
              <el-option
                label="仅记录"
                value="log"
              />
            </el-select>
          </el-form-item>
        </div>

        <el-form-item
          label="匹配内容"
          required
        >
          <el-input
            v-model="ruleForm.pattern"
            type="textarea"
            :rows="4"
            maxlength="1000"
            show-word-limit
            placeholder="关键词填写具体文本；正则规则填写正则表达式"
          />
        </el-form-item>

        <el-form-item label="规则说明">
          <el-input
            v-model="ruleForm.description"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="可选，说明命中原因或维护备注"
          />
        </el-form-item>

        <div class="grid gap-4 sm:grid-cols-2">
          <el-form-item label="适用场景">
            <el-checkbox v-model="ruleForm.applies_to_query">
              用户提问
            </el-checkbox>
            <el-checkbox v-model="ruleForm.applies_to_answer">
              AI 回答
            </el-checkbox>
          </el-form-item>
          <el-form-item label="规则状态">
            <el-switch
              v-model="ruleForm.enabled"
              inline-prompt
              active-text="启用"
              inactive-text="停用"
            />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <div class="content-risk-library-page__dialog-footer">
          <el-button @click="ruleDialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="savingRule"
            @click="submitRuleForm"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.content-risk-library-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.content-risk-library-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #edf1f6;
  padding: 16px 18px;
}

.content-risk-library-page__list-panel {
  overflow: hidden;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

.content-risk-library-page__list-panel > :not(.content-risk-library-page__toolbar) {
  margin: 18px;
}

.content-risk-library-page__search {
  width: 360px;
  max-width: 100%;
}

.content-risk-library-page__rule-search {
  width: 420px;
  max-width: 100%;
}

.content-risk-library-page__status {
  width: 132px;
}

.content-risk-library-page__table-panel {
  overflow: hidden;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

.content-risk-library-page__table-panel > :not(.content-risk-library-page__toolbar) {
  margin: 8px;
}

.content-risk-library-page__name-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.content-risk-library-page__name-cell strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-risk-library-page__name-cell span {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-risk-library-page__dialog-field {
  width: 100%;
}

.content-risk-library-page__dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 960px) {
  .content-risk-library-page__toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .content-risk-library-page__search,
  .content-risk-library-page__rule-search,
  .content-risk-library-page__status {
    width: 100%;
  }
}
</style>
