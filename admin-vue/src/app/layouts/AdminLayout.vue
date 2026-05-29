<script setup lang="ts">
import type { Component } from "vue";
import { computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Collection,
  FolderOpened,
  MagicStick,
  Odometer,
  SetUp,
  User,
  UserFilled,
  CaretBottom,
  SwitchButton
} from "@element-plus/icons-vue";

import { adminNav } from "@/app/navigation/admin-nav";
import { useAuthStore } from "@/stores/auth";
import { useTeamScopeStore } from "@/stores/team-scope";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const teamScopeStore = useTeamScopeStore();

const currentUserName = computed(() => authStore.user?.full_name || authStore.user?.username || "Admin User");
const currentUserRole = computed(() => authStore.user?.role || "System Operator");
const currentUserInitial = computed(() => currentUserName.value.trim().charAt(0).toUpperCase() || "A");
const selectedTeamId = computed({
  get() {
    return teamScopeStore.selectedTeamId;
  },
  set(value: number | null) {
    teamScopeStore.setSelectedTeam(value);
  }
});

const navIcons: Record<(typeof adminNav)[number]["key"], Component> = {
  dashboard: Odometer,
  "knowledge-bases": Collection,
  projects: FolderOpened,
  assistants: MagicStick,
  organizations: User,
  users: UserFilled,
  governance: SetUp,
};

async function handleLogout() {
  teamScopeStore.clear();
  authStore.signOut();
  await router.replace("/login");
}

onMounted(() => {
  void teamScopeStore.bootstrap();
});
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-slate-50">
    
    <aside class="flex w-[260px] shrink-0 flex-col bg-[#0F172A] text-slate-300 shadow-2xl transition-all duration-300 [&::-webkit-scrollbar]:hidden">
      
      <div class="flex h-16 shrink-0 items-center px-5 border-b border-slate-800/60">
        <div class="mr-3 flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/20">
          <el-icon class="text-white text-xs"><MagicStick /></el-icon>
        </div>
        <h1 class="text-[15px] font-bold tracking-wide text-slate-100">
          三圆AI知识库软件
        </h1>
      </div>

      <nav class="flex-1 overflow-y-auto px-3 py-5 space-y-1" aria-label="后台主导航">
        <router-link
          v-for="item in adminNav"
          :key="item.key"
          :to="item.to"
          class="group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-all duration-200"
          :class="
            route.path.startsWith(item.to)
              ? 'bg-indigo-500/10 text-indigo-400' 
              : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
          "
        >
          <div 
            v-if="route.path.startsWith(item.to)"
            class="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r-full bg-indigo-500"
          ></div>
          
          <el-icon 
            :size="17" 
            class="transition-transform duration-200"
            :class="route.path.startsWith(item.to) ? 'scale-110' : 'group-hover:scale-110 group-hover:text-slate-300'"
          >
            <component :is="navIcons[item.key]" />
          </el-icon>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="shrink-0 border-t border-slate-800/60 bg-slate-900/30 p-4">
        
        <div class="mb-3 px-1">
          <div class="mb-1.5 flex items-center justify-between">
            <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500">
              Workspace
            </span>
          </div>
          <el-select
            v-model="selectedTeamId"
            class="!w-full custom-dark-select"
            size="default"
            :loading="teamScopeStore.loading"
            placeholder="切换团队..."
            :disabled="!teamScopeStore.hasTeams"
          >
            <el-option
              v-for="team in teamScopeStore.teams"
              :key="team.id"
              :label="team.name"
              :value="team.id"
            />
          </el-select>
          <p v-if="teamScopeStore.errorMessage" class="mt-1.5 text-[11px] text-rose-400/90">
            {{ teamScopeStore.errorMessage }}
          </p>
        </div>

        <el-dropdown trigger="click" class="w-full" placement="top">
          <div class="flex w-full cursor-pointer items-center gap-3 rounded-lg p-2 transition-colors hover:bg-slate-800/80">
            <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-indigo-500/20 border border-indigo-500/30 text-[13px] font-bold text-indigo-300">
              {{ currentUserInitial }}
            </div>
            
            <div class="flex min-w-0 flex-1 flex-col text-left">
              <span class="truncate text-[13px] font-medium text-slate-200">
                {{ currentUserName }}
              </span>
              <span class="truncate text-[11px] text-slate-500 capitalize">
                {{ currentUserRole }}
              </span>
            </div>
            
            <el-icon class="text-slate-500 transition-colors hover:text-slate-300"><CaretBottom /></el-icon>
          </div>

          <template #dropdown>
            <el-dropdown-menu class="w-[228px]">
              <el-dropdown-item disabled>
                <span class="text-xs text-slate-400">登录账号: {{ currentUserName }}</span>
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout" class="!text-rose-500 hover:!bg-rose-50 hover:!text-rose-600">
                <el-icon><SwitchButton /></el-icon>
                安全退出
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

      </div>
    </aside>

    <div class="flex min-h-0 min-w-0 flex-1 flex-col">
      <main class="min-h-0 flex-1 overflow-y-auto p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
/* 针对深色侧边栏中的 el-select 进行样式穿透美化 */
:deep(.custom-dark-select .el-input__wrapper) {
  background-color: rgba(30, 41, 59, 0.4) !important; /* 更通透的背景 */
  box-shadow: 0 0 0 1px rgba(71, 85, 105, 0.4) inset !important; /* 更柔和的边框 */
  border-radius: 6px;
}
:deep(.custom-dark-select .el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.8) inset !important; /* 聚焦时的靛蓝色边框 */
}
:deep(.custom-dark-select .el-input__inner) {
  color: #cbd5e1 !important; /* slate-300 */
  font-size: 13px;
}
</style>