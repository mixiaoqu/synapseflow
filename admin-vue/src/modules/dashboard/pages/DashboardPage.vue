<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import FilterToolbar from "@/shared/components/page/FilterToolbar.vue";
import ResourceListPage from "@/shared/components/page/ResourceListPage.vue";

const route = useRoute();

const currentTitle = computed(() => String(route.meta.title ?? "资源入口"));
const currentDescription = computed(() =>
  String(route.meta.description ?? "当前页面提供平台模块的统一骨架，后续业务组件将在此区域按模块接入。"),
);
</script>

<template>
  <ResourceListPage
    eyebrow="模块工作台"
    :title="currentTitle"
    :description="currentDescription"
  >
    <template #filters>
      <FilterToolbar
        title="页面操作区"
        description="统一保留搜索、筛选和主操作位。"
      >
        <el-button plain>
          筛选条件
        </el-button>
        <el-button plain>
          状态标签
        </el-button>

        <template #actions>
          <el-button type="primary">
            新建内容
          </el-button>
        </template>
      </FilterToolbar>
    </template>

    <section class="dashboard-page__workspace">
      <div
        class="min-h-[calc(100vh-270px)] rounded-[20px] border border-gray-200 bg-white shadow-sm"
        aria-label="模块内容空白面板"
      />
    </section>
  </ResourceListPage>
</template>
