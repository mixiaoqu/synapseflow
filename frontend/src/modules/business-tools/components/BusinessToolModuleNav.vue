<script setup lang="ts">
import { Connection, Document, Link, Tools } from "@element-plus/icons-vue";
import { useRoute } from "vue-router";

const items = [
  { label: "工具目录", to: "/business-tools", icon: Tools, exact: true },
  { label: "业务连接", to: "/business-tools/connections", icon: Connection },
  { label: "业务接口", to: "/business-tools/apis", icon: Link },
  { label: "调用记录", to: "/business-tools/logs", icon: Document },
];
const route = useRoute();

function isActive(path: string, exact?: boolean) {
  if (!exact) {
    return route.path.startsWith(path);
  }
  if (path !== "/business-tools") {
    return route.path === path;
  }
  return (
    route.path === "/business-tools" ||
    route.path === "/business-tools/new" ||
    /^\/business-tools\/\d+$/.test(route.path)
  );
}
</script>

<template>
  <nav class="business-tool-nav" aria-label="业务工具模块导航">
    <router-link
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      class="business-tool-nav__item"
      :class="{ 'is-active': isActive(item.to, item.exact) }"
    >
      <el-icon><component :is="item.icon" /></el-icon>
      <span>{{ item.label }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.business-tool-nav {
  display: flex;
  min-height: 44px;
  gap: 4px;
  overflow-x: auto;
  border-bottom: 1px solid var(--admin-border-soft);
  background: var(--admin-surface);
  padding: 0 4px;
}

.business-tool-nav__item {
  position: relative;
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  padding: 0 14px;
  color: var(--admin-text-muted);
  font-size: 14px;
  font-weight: 500;
  transition: color 180ms ease, background-color 180ms ease;
}

.business-tool-nav__item:hover {
  background: var(--admin-surface-muted);
  color: var(--admin-text);
}

.business-tool-nav__item.is-active {
  color: var(--admin-primary);
}

.business-tool-nav__item.is-active::after {
  position: absolute;
  right: 12px;
  bottom: -1px;
  left: 12px;
  height: 2px;
  border-radius: 2px 2px 0 0;
  background: var(--admin-primary);
  content: "";
}
</style>
