<script setup lang="ts">
import type { Component } from "vue";
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import {
  ArrowDown,
  ChatDotRound,
  Collection,
  DocumentChecked,
  Expand,
  FolderOpened,
  Fold,
  MagicStick,
  Odometer,
  SetUp,
  User,
  UserFilled,
} from "@element-plus/icons-vue";

import { adminNavGroups, adminPrimaryNav } from "@/app/navigation/admin-nav";
import { useAuthStore } from "@/stores/auth";

defineProps<{
  collapsed: boolean;
  mobile?: boolean;
}>();

const emit = defineEmits<{
  "toggle-collapse": [];
  navigate: [];
}>();

const route = useRoute();
const authStore = useAuthStore();

const navIcons: Record<
  (typeof adminPrimaryNav)[number]["key"] | (typeof adminNavGroups)[number]["items"][number]["key"],
  Component
> = {
  dashboard: Odometer,
  "knowledge-bases": Collection,
  projects: FolderOpened,
  assistants: MagicStick,
  organizations: User,
  users: UserFilled,
  "qa-logs": ChatDotRound,
  "content-risk-overview": SetUp,
  "content-risk-libraries": SetUp,
  "content-risk-logs": DocumentChecked,
};

const expandedGroupKeys = ref<Record<(typeof adminNavGroups)[number]["key"], boolean>>({
  "knowledge-and-apps": true,
  "operations-and-review": true,
  "organization-and-access": true,
});

const visibleNavGroups = computed(() =>
  adminNavGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => {
        if (item.key === "users" || item.key === "content-risk-libraries") {
          return authStore.user?.role === "system_admin";
        }
        return true;
      }),
    }))
    .filter((group) => group.items.length > 0),
);

function toggleNavGroup(groupKey: (typeof adminNavGroups)[number]["key"]) {
  expandedGroupKeys.value[groupKey] = !expandedGroupKeys.value[groupKey];
}

function isGroupExpanded(groupKey: (typeof adminNavGroups)[number]["key"]) {
  return expandedGroupKeys.value[groupKey];
}

function isGroupActive(group: (typeof adminNavGroups)[number]) {
  return group.items.some((item) => route.path.startsWith(item.to));
}

function isNavActive(to: string) {
  return route.path.startsWith(to);
}
</script>

<template>
  <aside
    class="flex h-full shrink-0 flex-col border-r border-slate-200 bg-[#111827] text-slate-300 transition-all duration-200 [&::-webkit-scrollbar]:hidden"
    :class="[
      mobile ? 'w-full' : collapsed ? 'w-[72px]' : 'w-[260px]',
    ]"
  >
    <div class="flex h-16 shrink-0 items-center border-b border-slate-800/60 px-4">
      <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--admin-primary)]">
        <el-icon class="text-xs text-white">
          <MagicStick />
        </el-icon>
      </div>

      <h1
        v-if="!collapsed || mobile"
        class="ml-3 min-w-0 truncate text-[15px] font-bold tracking-wide text-slate-100"
      >
        三圆AI知识库软件
      </h1>

      <button
        v-if="!mobile"
        type="button"
        class="ml-auto flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-800 hover:text-slate-200"
        :aria-label="collapsed ? '展开侧边栏' : '折叠侧边栏'"
        @click="emit('toggle-collapse')"
      >
        <el-icon>
          <Expand v-if="collapsed" />
          <Fold v-else />
        </el-icon>
      </button>
    </div>

    <nav class="flex-1 space-y-5 overflow-y-auto px-3 py-5" aria-label="后台主导航">
      <div class="space-y-1">
        <router-link
          v-for="item in adminPrimaryNav"
          :key="item.key"
          :to="item.to"
          class="group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-all duration-200"
          :class="
            isNavActive(item.to)
              ? 'admin-sidebar__nav-link--active'
              : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
          "
          :title="collapsed && !mobile ? item.label : undefined"
          @click="emit('navigate')"
        >
          <div
            v-if="isNavActive(item.to)"
            class="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r-full bg-[var(--admin-primary-light)]"
          />

          <el-icon
            :size="17"
            class="shrink-0 transition-transform duration-200"
            :class="isNavActive(item.to) ? 'scale-110' : 'group-hover:scale-110 group-hover:text-slate-300'"
          >
            <component :is="navIcons[item.key]" />
          </el-icon>
          <span v-if="!collapsed || mobile" class="truncate">{{ item.label }}</span>
        </router-link>
      </div>

      <section v-for="group in visibleNavGroups" :key="group.key" class="space-y-2">
        <button
          type="button"
          class="flex w-full items-center rounded-lg px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.18em] transition-colors"
          :class="
            isGroupActive(group)
              ? 'text-slate-300'
              : 'text-slate-500 hover:bg-slate-800/40 hover:text-slate-300'
          "
          :title="collapsed && !mobile ? group.label : undefined"
          @click="toggleNavGroup(group.key)"
        >
          <span v-if="!collapsed || mobile" class="truncate">{{ group.label }}</span>
          <span v-else class="mx-auto h-1 w-1 rounded-full bg-current" />
          <el-icon
            v-if="!collapsed || mobile"
            class="ml-auto transition-transform duration-200"
            :class="isGroupExpanded(group.key) ? 'rotate-0' : '-rotate-90'"
          >
            <ArrowDown />
          </el-icon>
        </button>

        <div v-show="collapsed && !mobile ? true : isGroupExpanded(group.key)" class="space-y-1">
          <router-link
            v-for="item in group.items"
            :key="item.key"
            :to="item.to"
            class="group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-all duration-200"
            :class="
              isNavActive(item.to)
                ? 'admin-sidebar__nav-link--active'
                : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
            "
            :title="collapsed && !mobile ? item.label : undefined"
            @click="emit('navigate')"
          >
            <div
              v-if="isNavActive(item.to)"
              class="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r-full bg-[var(--admin-primary-light)]"
            />

            <el-icon
              :size="17"
              class="shrink-0 transition-transform duration-200"
              :class="isNavActive(item.to) ? 'scale-110' : 'group-hover:scale-110 group-hover:text-slate-300'"
            >
              <component :is="navIcons[item.key]" />
            </el-icon>
            <span v-if="!collapsed || mobile" class="truncate">{{ item.label }}</span>
          </router-link>
        </div>
      </section>
    </nav>

  </aside>
</template>

<style scoped>
.admin-sidebar__nav-link--active {
  background: rgba(37, 99, 235, 0.12);
  color: #60a5fa;
}
</style>
