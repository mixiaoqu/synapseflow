<script setup lang="ts">
import type { Component } from "vue";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Bell,
  Collection,
  Fold,
  FolderOpened,
  House,
  MagicStick,
  Odometer,
  Setting,
  SetUp,
  User,
} from "@element-plus/icons-vue";

import { adminNav } from "@/app/navigation/admin-nav";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const pageTitle = computed(() => String(route.meta.title ?? "管理后台"));
const currentNav = computed(() => adminNav.find((item) => route.path.startsWith(item.to)));
const breadcrumbLabel = computed(() => currentNav.value?.label ?? "控制台");
const pageDescription = computed(() =>
  String(route.meta.description ?? "统一承载后台模块入口、检索面板与资源页面内容。"),
);

const navIcons: Record<(typeof adminNav)[number]["key"], Component> = {
  dashboard: Odometer,
  "knowledge-bases": Collection,
  projects: FolderOpened,
  assistants: MagicStick,
  organizations: User,
  governance: SetUp,
};

async function handleLogout() {
  authStore.signOut();
  await router.replace("/login");
}
</script>

<template>
  <div class="flex min-h-screen bg-gray-100">
    <aside class="flex w-60 shrink-0 flex-col bg-slate-900 text-white">
      <div class="px-6 pt-6">
        <h1 class="text-lg font-semibold leading-7 text-white">
          AI企业知识库后台
        </h1>
      </div>

      <nav
        class="mt-6 flex flex-col gap-2 px-3"
        aria-label="后台主导航"
      >
        <router-link
          v-for="item in adminNav"
          :key="item.key"
          :to="item.to"
          class="flex min-h-11 items-center gap-3 rounded-xl border border-transparent px-4 text-sm font-medium text-slate-400 transition-colors"
          :class="
            route.path.startsWith(item.to)
              ? 'border-slate-700 bg-slate-800 text-white'
              : 'hover:bg-slate-800/80 hover:text-slate-200'
          "
        >
          <el-icon :size="16">
            <component :is="navIcons[item.key]" />
          </el-icon>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <header class="flex items-center justify-between gap-6 border-b border-gray-200 bg-white px-5 py-4 shadow-sm">
        <div class="flex min-w-0 items-start gap-4">
          <div class="flex items-center pt-0.5">
            <el-button
              :icon="Fold"
              circle
              plain
            />
          </div>
          <div class="min-w-0">
            <el-breadcrumb separator="/">
              <el-breadcrumb-item :icon="House">
                企业系统
              </el-breadcrumb-item>
              <el-breadcrumb-item>{{ breadcrumbLabel }}</el-breadcrumb-item>
            </el-breadcrumb>
            <h2 class="mt-2 text-2xl font-semibold leading-8 text-gray-900">
              {{ pageTitle }}
            </h2>
            <p class="mt-1 text-sm leading-6 text-slate-500">
              {{ pageDescription }}
            </p>
          </div>
        </div>

        <div class="flex items-center gap-4">
          <el-button
            :icon="Bell"
            circle
            plain
          />
          <el-button
            :icon="Setting"
            circle
            plain
          />
          <div class="flex flex-col items-end gap-1">
            <span class="text-sm font-semibold text-gray-900">
              {{ authStore.user?.full_name || authStore.user?.username || "Admin User" }}
            </span>
            <span class="text-xs uppercase tracking-wide text-slate-500">
              {{ authStore.user?.role || "system operator" }}
            </span>
          </div>
          <el-button
            plain
            @click="handleLogout"
          >
            退出登录
          </el-button>
        </div>
      </header>

      <main class="flex-1 p-5">
        <router-view />
      </main>
    </div>
  </div>
</template>
