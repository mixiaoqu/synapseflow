<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Delete,
  EditPen,
  Plus,
  Search,
} from "@element-plus/icons-vue";

import {
  bulkActionAssistants,
  deleteAssistant,
  getAssistantUsage,
  listAssistants,
} from "@/shared/api/assistants";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { useTeamScopeStore } from "@/stores/team-scope";
import { isForbiddenError } from "@/shared/utils/error";
import type { AssistantSummary } from "@/shared/types/assistant";

type StatusFilter = "all" | "active" | "inactive";

const router = useRouter();
const teamScopeStore = useTeamScopeStore();

const toolbar = reactive({
  search: "",
  status: "all" as StatusFilter,
});

const assistants = ref<AssistantSummary[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const statusLoadingId = ref<number | null>(null);
const deletingAssistantId = ref<number | null>(null);

const displayedAssistants = computed(() => {
  const keyword = toolbar.search.trim().toLowerCase();

  return assistants.value.filter((item) => {
    const matchesKeyword =
      keyword.length === 0 ||
      [item.name, item.slug, item.description ?? ""].some((value) =>
        value.toLowerCase().includes(keyword),
      );
    const matchesStatus =
      toolbar.status === "all" ||
      (toolbar.status === "active" ? item.is_active : !item.is_active);
    return matchesKeyword && matchesStatus;
  });
});

const selectedTeamName = computed(() => teamScopeStore.selectedTeam?.name ?? "未选择团队");
const hasActiveFilters = computed(
  () => toolbar.search.trim().length > 0 || toolbar.status !== "all",
);
const isForbidden = computed(() => Boolean(loadError.value) && isForbiddenError(loadError.value));

function formatDateTime(value: string) {
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

async function loadAssistantList() {
  if (loading.value) {
    return;
  }

  loading.value = true;
  loadError.value = null;

  try {
    assistants.value = await listAssistants({
      team_id: teamScopeStore.selectedTeamId ?? undefined,
    });
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  toolbar.search = "";
  toolbar.status = "all";
}

function openCreateAssistant() {
  if (!teamScopeStore.selectedTeamId) {
    ElMessage.warning("请先选择所属团队，再创建助手。");
    return;
  }

  void router.push("/assistants/new");
}

function openAssistantDetail(assistantId: number) {
  void router.push(`/assistants/${assistantId}`);
}

async function handleToggleStatus(assistant: AssistantSummary, nextValue: boolean | string | number) {
  if (statusLoadingId.value) {
    return;
  }

  const targetValue = Boolean(nextValue);
  const action = targetValue ? "enable" : "disable";

  statusLoadingId.value = assistant.id;
  try {
    await bulkActionAssistants([assistant.id], action);
    assistant.is_active = targetValue;
    ElMessage.success(`已${targetValue ? "启用" : "停用"}助手“${assistant.name}”。`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "更新助手状态失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    statusLoadingId.value = null;
  }
}

async function handleDeleteAssistant(assistant: AssistantSummary) {
  if (deletingAssistantId.value) {
    return;
  }

  deletingAssistantId.value = assistant.id;
  try {
    const usage = await getAssistantUsage(assistant.id);
    const hasDependencies = usage.has_dependencies;

    try {
      await ElMessageBox.confirm(
        hasDependencies
          ? `助手“${assistant.name}”仍有 ${usage.active_session_count} 个活跃会话、${usage.related_log_count} 条日志引用。确定强制删除吗？`
          : `确定删除助手“${assistant.name}”吗？删除后不可恢复。`,
        hasDependencies ? "强制删除助手" : "删除助手",
        {
          type: "warning",
          confirmButtonText: hasDependencies ? "强制删除" : "删除",
          cancelButtonText: "取消",
        },
      );
    } catch {
      return;
    }

    await deleteAssistant(assistant.id, {
      force: hasDependencies,
    });
    ElMessage.success(`已删除助手“${assistant.name}”。`);
    await loadAssistantList();
  } catch (error) {
    const message = error instanceof Error ? error.message : "删除助手失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    deletingAssistantId.value = null;
  }
}

onMounted(() => {
  void loadAssistantList();
});

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    void loadAssistantList();
  },
);
</script>

<template>
  <section class="assistant-list-page">
    <header class="assistant-list-page__header">
      <div class="assistant-list-page__header-copy">
        <h1 class="assistant-list-page__title">助手管理</h1>
        <p class="assistant-list-page__description">
          在当前团队作用域下维护助手资料、提示词和预览调试入口。
        </p>
      </div>

      <div class="assistant-list-page__header-actions">
        <span class="assistant-list-page__scope">当前团队：{{ selectedTeamName }}</span>
        <el-button type="primary" @click="openCreateAssistant">
          <el-icon class="mr-2"><Plus /></el-icon>
          新建助手
        </el-button>
      </div>
    </header>

    <section
      v-if="!loading && !loadError"
      class="assistant-list-page__toolbar"
    >
      <el-input
        v-model="toolbar.search"
        size="large"
        clearable
        placeholder="搜索助手名称、标识或描述..."
        class="assistant-list-page__search"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-select
        v-model="toolbar.status"
        size="large"
        class="assistant-list-page__status"
      >
        <el-option label="全部状态" value="all" />
        <el-option label="已启用" value="active" />
        <el-option label="已停用" value="inactive" />
      </el-select>
    </section>

    <AppLoading
      v-if="loading"
      title="助手列表加载中"
      description="正在从后台获取助手配置，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !isForbidden"
      title="助手列表加载失败"
      description="暂时无法获取助手列表，请稍后重试。"
      :error="loadError"
      @retry="loadAssistantList"
    />

    <AppError
      v-else-if="isForbidden"
      title="无权查看助手列表"
      description="当前账号没有访问助手列表的权限。"
      :error="loadError"
      :show-retry="false"
    />

    <AppEmpty
      v-else-if="displayedAssistants.length === 0"
      :title="hasActiveFilters ? '未找到相关助手' : '暂无助手'"
      :description="
        hasActiveFilters
          ? '请尝试更换搜索关键词，或清除筛选后查看全部助手。'
          : '当前团队下还没有可配置的助手。'
      "
    >
      <el-button link type="primary" @click="hasActiveFilters ? resetFilters() : openCreateAssistant()">
        {{ hasActiveFilters ? "清除筛选" : "创建助手" }}
      </el-button>
    </AppEmpty>

    <section v-else class="assistant-list-page__table-panel">
      <el-table
        :data="displayedAssistants"
        row-key="id"
        class="assistant-list-page__table"
      >
        <el-table-column label="助手名称" min-width="280">
          <template #default="{ row }">
            <div class="assistant-list-page__name-cell">
              <strong>{{ row.name }}</strong>
              <span>{{ row.description?.trim() || "暂无说明" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="标识" min-width="180">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.slug }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="llm_model_key" label="模型" min-width="160">
          <template #default="{ row }">
            <span>{{ row.llm_model_key || "未指定" }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="90" align="center" />
        <el-table-column label="更新时间" min-width="180">
          <template #default="{ row }">
            <span>{{ formatDateTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              :loading="statusLoadingId === row.id"
              @change="(value) => handleToggleStatus(row, value)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openAssistantDetail(row.id)">
              <el-icon><EditPen /></el-icon>
              <span>配置</span>
            </el-button>
            <el-button
              link
              type="danger"
              :loading="deletingAssistantId === row.id"
              @click="handleDeleteAssistant(row)"
            >
              <el-icon><Delete /></el-icon>
              <span>删除</span>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>

<style scoped>
.assistant-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.assistant-list-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 56px;
  border: 1px solid #dbe2ea;
  border-radius: 12px;
  background: #ffffff;
  padding: 16px 18px;
}

.assistant-list-page__header-copy {
  min-width: 0;
}

.assistant-list-page__title {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.assistant-list-page__description {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.assistant-list-page__header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.assistant-list-page__scope {
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.assistant-list-page__toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #dbe2ea;
  border-radius: 12px;
  background: #ffffff;
  padding: 14px 16px;
}

.assistant-list-page__search {
  width: 360px;
  max-width: 100%;
}

.assistant-list-page__status {
  width: 132px;
}

.assistant-list-page__table-panel {
  border: 1px solid #dbe2ea;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  padding: 8px 8px 2px;
}

.assistant-list-page__table {
  width: 100%;
}

.assistant-list-page__name-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.assistant-list-page__name-cell strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.assistant-list-page__name-cell span {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 960px) {
  .assistant-list-page__header,
  .assistant-list-page__toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .assistant-list-page__header-actions {
    justify-content: space-between;
  }

  .assistant-list-page__search,
  .assistant-list-page__status {
    width: 100%;
  }
}
</style>
