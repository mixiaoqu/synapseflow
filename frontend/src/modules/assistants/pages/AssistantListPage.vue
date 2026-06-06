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

import AdminListPanel from "@/app/components/admin/AdminListPanel.vue";
import AdminTableToolbar from "@/app/components/admin/AdminTableToolbar.vue";
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
const hasLoadedData = ref(false);
const statusLoadingId = ref<number | null>(null);
const deletingAssistantId = ref<number | null>(null);
const pagination = ref({
  page: 1,
  pageSize: 10,
  total: 0,
});
let searchTimer: ReturnType<typeof setTimeout> | undefined;

const displayedAssistants = computed(() => assistants.value);

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
    const result = await listAssistants({
      team_id: teamScopeStore.selectedTeamId ?? undefined,
      keyword: toolbar.search.trim() || undefined,
      status: toolbar.status,
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
    });
    assistants.value = result.items;
    pagination.value.total = result.total;
    pagination.value.page = result.page;
    pagination.value.pageSize = result.page_size;
    hasLoadedData.value = true;
  } catch (error) {
    if (hasLoadedData.value) {
      ElMessage.error(error instanceof Error ? error.message : "助手列表刷新失败，请稍后重试。");
    } else {
      loadError.value = error;
    }
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  toolbar.search = "";
  toolbar.status = "all";
}

function handlePageChange(page: number) {
  pagination.value.page = page;
  void loadAssistantList();
}

function refreshAssistantListFromFirstPage() {
  pagination.value.page = 1;
  void loadAssistantList();
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
    pagination.value.page = 1;
    void loadAssistantList();
  },
);

watch(
  () => toolbar.search,
  () => {
    if (searchTimer) {
      clearTimeout(searchTimer);
    }
    searchTimer = setTimeout(refreshAssistantListFromFirstPage, 300);
  },
);

watch(
  () => toolbar.status,
  () => {
    refreshAssistantListFromFirstPage();
  },
);
</script>

<template>
  <section class="assistant-list-page">
    <AppLoading
      v-if="loading && !hasLoadedData"
      title="助手列表加载中"
      description="正在从后台获取助手配置，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !isForbidden && !hasLoadedData"
      title="助手列表加载失败"
      description="暂时无法获取助手列表，请稍后重试。"
      :error="loadError"
      @retry="loadAssistantList"
    />

    <AppError
      v-else-if="isForbidden && !hasLoadedData"
      title="无权查看助手列表"
      description="当前账号没有访问助手列表的权限。"
      :error="loadError"
      :show-retry="false"
    />

    <AdminListPanel v-else>
      <AdminTableToolbar>
        <template #left>
          <el-input
            v-model="toolbar.search"
            clearable
            placeholder="搜索助手名称、标识或描述..."
            class="assistant-list-page__search"
            @keyup.enter="refreshAssistantListFromFirstPage"
            @clear="refreshAssistantListFromFirstPage"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>

          <el-select
            v-model="toolbar.status"
            class="assistant-list-page__status"
          >
            <el-option label="全部状态" value="all" />
            <el-option label="已启用" value="active" />
            <el-option label="已停用" value="inactive" />
          </el-select>
          <el-button :loading="loading" type="primary" @click="refreshAssistantListFromFirstPage">
            搜索
          </el-button>
          <el-button :disabled="loading" @click="resetFilters">重置</el-button>
        </template>

        <template #right>
          <span class="assistant-list-page__scope">当前团队：{{ selectedTeamName }}</span>
          <el-button type="primary" @click="openCreateAssistant">
            <el-icon><Plus /></el-icon>
            新建助手
          </el-button>
        </template>
      </AdminTableToolbar>

      <AppEmpty
        v-if="displayedAssistants.length === 0"
        v-loading="loading"
        class="assistant-list-page__empty"
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

      <el-table
        v-else
        v-loading="loading"
        :data="displayedAssistants"
        row-key="id"
        class="assistant-list-page__table"
        element-loading-text="正在更新助手列表"
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
      <div v-if="pagination.total > pagination.pageSize" class="assistant-list-page__pagination">
        <el-pagination
          background
          layout="prev, pager, next"
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          @current-change="handlePageChange"
        />
      </div>
    </AdminListPanel>
  </section>
</template>

<style scoped>
.assistant-list-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.assistant-list-page__scope {
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.assistant-list-page__search {
  width: 280px;
}

.assistant-list-page__status {
  width: 132px;
}

.assistant-list-page__pagination {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
  padding: 12px;
}

.assistant-list-page__table {
  width: 100%;
}

.assistant-list-page__empty {
  min-height: 420px;
  border-top: 1px solid #e2e8f0;
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
  .assistant-list-page__search,
  .assistant-list-page__status {
    width: 100%;
  }
}
</style>
