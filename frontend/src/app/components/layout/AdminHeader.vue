<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import {
  CaretBottom,
  Menu,
  SwitchButton,
} from "@element-plus/icons-vue";

import { useAuthStore } from "@/stores/auth";
import { useTeamScopeStore } from "@/stores/team-scope";

defineProps<{
  title: string;
  breadcrumbs: Array<{
    label: string;
    to?: string;
  }>;
}>();

const emit = defineEmits<{
  "open-mobile-sidebar": [];
}>();

const router = useRouter();
const authStore = useAuthStore();
const teamScopeStore = useTeamScopeStore();

const currentUserName = computed(() => authStore.user?.full_name || authStore.user?.username || "Admin User");
const currentUserRole = computed(() => authStore.user?.role || "System Operator");
const currentUserInitial = computed(() => currentUserName.value.trim().charAt(0).toUpperCase() || "A");

async function handleLogout() {
  teamScopeStore.clear();
  authStore.signOut();
  await router.replace("/login");
}
</script>

<template>
  <header class="flex h-16 shrink-0 items-center gap-4 border-b border-slate-200 bg-white px-4 shadow-sm lg:px-6">
    <button
      type="button"
      class="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 lg:hidden"
      aria-label="打开侧边栏"
      @click="emit('open-mobile-sidebar')"
    >
      <el-icon :size="19">
        <Menu />
      </el-icon>
    </button>

    <div class="min-w-0 flex-1">
      <div class="flex min-w-0 items-center gap-2 text-xs text-slate-500">
        <template v-for="(crumb, index) in breadcrumbs" :key="`${crumb}-${index}`">
          <router-link
            v-if="crumb.to"
            :to="crumb.to"
            class="truncate transition-colors hover:text-[var(--admin-primary)]"
          >
            {{ crumb.label }}
          </router-link>
          <span v-else class="truncate">{{ crumb.label }}</span>
          <span v-if="index < breadcrumbs.length - 1" class="text-slate-300">/</span>
        </template>
      </div>
      <h2 class="mt-0.5 truncate text-lg font-semibold text-slate-900">
        {{ title }}
      </h2>
    </div>

    <div class="flex shrink-0 items-center gap-2">
      <el-dropdown trigger="click" placement="bottom-end">
        <button
          type="button"
          class="flex h-9 items-center gap-2 rounded-md px-1.5 text-left transition-colors hover:bg-slate-100 sm:pl-2 sm:pr-2.5"
        >
          <span class="admin-header__avatar flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[13px] font-bold">
            {{ currentUserInitial }}
          </span>
          <span class="hidden min-w-0 flex-col sm:flex">
            <span class="max-w-[120px] truncate text-[13px] font-medium text-slate-800">
              {{ currentUserName }}
            </span>
            <span class="max-w-[120px] truncate text-[11px] capitalize text-slate-500">
              {{ currentUserRole }}
            </span>
          </span>
          <el-icon class="hidden text-slate-400 sm:inline-flex">
            <CaretBottom />
          </el-icon>
        </button>

        <template #dropdown>
          <el-dropdown-menu class="w-[220px]">
            <el-dropdown-item disabled>
              <span class="text-xs text-slate-400">登录账号: {{ currentUserName }}</span>
            </el-dropdown-item>
            <el-dropdown-item divided class="!text-rose-500 hover:!bg-rose-50 hover:!text-rose-600" @click="handleLogout">
              <el-icon>
                <SwitchButton />
              </el-icon>
              安全退出
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<style scoped>
.admin-header__avatar {
  border: 1px solid var(--admin-primary-border);
  background: var(--admin-primary-soft);
  color: var(--admin-primary);
}
</style>
