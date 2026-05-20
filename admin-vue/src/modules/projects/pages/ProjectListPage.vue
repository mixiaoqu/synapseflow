<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Search } from "@element-plus/icons-vue";

import { listProjects } from "@/shared/api/projects";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import { useTeamScopeStore } from "@/stores/team-scope";
import { isForbiddenError } from "@/shared/utils/error";
import type { ProjectSummary } from "@/shared/types/project";

const router = useRouter();
const teamScopeStore = useTeamScopeStore();

const keyword = ref("");
const projects = ref<ProjectSummary[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);

const displayedProjects = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase();
  return projects.value.filter((item) => {
    if (!normalizedKeyword) {
      return true;
    }

    return [item.name, item.code, item.description ?? "", item.product_name ?? ""].some((value) =>
      value.toLowerCase().includes(normalizedKeyword),
    );
  });
});

const isForbidden = computed(() => Boolean(loadError.value) && isForbiddenError(loadError.value));

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

async function loadProjectList() {
  if (loading.value) {
    return;
  }

  loading.value = true;
  loadError.value = null;

  try {
    projects.value = await listProjects(teamScopeStore.selectedTeamId ?? undefined);
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

function openProjectApps(projectId: number) {
  void router.push(`/projects/${projectId}/apps`);
}

onMounted(() => {
  void loadProjectList();
});

watch(
  () => teamScopeStore.selectedTeamId,
  () => {
    void loadProjectList();
  },
);
</script>

<template>
  <section class="project-list-page">
    <header class="project-list-page__header">
      <div>
        <h1 class="project-list-page__title">应用与发布</h1>
        <p class="project-list-page__description">先选择业务项目，再进入该项目下的发布渠道与接入配置。</p>
      </div>

      <el-input
        v-model="keyword"
        size="large"
        clearable
        placeholder="搜索项目名称、编码或产品..."
        class="project-list-page__search"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
    </header>

    <AppLoading
      v-if="loading"
      title="项目列表加载中"
      description="正在获取当前团队可访问的项目，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError && !isForbidden"
      title="项目列表加载失败"
      description="暂时无法获取项目列表，请稍后重试。"
      :error="loadError"
      @retry="loadProjectList"
    />

    <AppError
      v-else-if="isForbidden"
      title="无权查看项目列表"
      description="当前账号没有访问项目列表的权限。"
      :error="loadError"
      :show-retry="false"
    />

    <AppEmpty
      v-else-if="displayedProjects.length === 0"
      title="暂无项目"
      description="当前筛选条件下没有可管理的业务项目。"
    />

    <section v-else class="project-list-page__table-panel">
      <el-table :data="displayedProjects" row-key="id" class="project-list-page__table">
        <el-table-column label="项目名称" min-width="280">
          <template #default="{ row }">
            <div class="project-list-page__name-cell">
              <strong>{{ row.name }}</strong>
              <span>{{ row.description?.trim() || "暂无说明" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="项目编码" min-width="180">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="产品" min-width="180">
          <template #default="{ row }">
            <span>{{ row.product_name || "未设置" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="所属团队" min-width="150">
          <template #default="{ row }">
            <span>{{ row.team_name || "未知团队" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="发布渠道" width="120" align="center">
          <template #default="{ row }">
            <span>{{ row.app_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain" round>
              {{ row.is_active ? "启用中" : "已停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近更新" width="140">
          <template #default="{ row }">
            <span>{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="right">
          <template #default="{ row }">
            <el-button type="primary" plain size="small" @click="openProjectApps(row.id)">
              管理发布渠道
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>

<style scoped>
.project-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.project-list-page__header {
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

.project-list-page__title {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.project-list-page__description {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.project-list-page__search {
  width: 360px;
  max-width: 100%;
}

.project-list-page__table-panel {
  border: 1px solid #dbe2ea;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  padding: 8px 8px 2px;
}

.project-list-page__name-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.project-list-page__name-cell strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-list-page__name-cell span {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 960px) {
  .project-list-page__header {
    flex-direction: column;
    align-items: stretch;
  }

  .project-list-page__search {
    width: 100%;
  }
}
</style>
