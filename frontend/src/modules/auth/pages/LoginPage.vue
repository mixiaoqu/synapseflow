<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Hide, Lock, Monitor, User, View } from "@element-plus/icons-vue";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const submitting = ref(false);
const passwordVisible = ref(false);

const form = reactive({
  usernameOrEmail: "",
  password: "",
});

const passwordInputType = computed(() => (passwordVisible.value ? "text" : "password"));
const passwordIcon = computed(() => (passwordVisible.value ? Hide : View));

function togglePasswordVisibility() {
  passwordVisible.value = !passwordVisible.value;
}

async function handleSubmit() {
  if (submitting.value) {
    return;
  }

  if (!form.usernameOrEmail.trim() || !form.password.trim()) {
    ElMessage.warning("请输入账号和密码。");
    return;
  }

  submitting.value = true;

  try {
    await authStore.signIn({
      usernameOrEmail: form.usernameOrEmail.trim(),
      password: form.password,
    });

    ElMessage.success("登录成功，正在进入后台。");

    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.replace(redirect);
  } catch (error) {
    const message = error instanceof Error ? error.message : "登录失败，请稍后重试。";
    ElMessage.error(message);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section class="login-page relative flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
    <div
      class="pointer-events-none absolute inset-x-0 top-0 h-[320px] bg-gradient-to-b from-blue-50/70 via-slate-50 to-transparent"
    />

    <div class="relative z-10 w-full max-w-md">
      <div class="mb-8 text-center">
        <div
          class="mx-auto mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--admin-primary)] text-white shadow-[0_8px_20px_rgba(37,99,235,0.18)]"
        >
          <el-icon :size="24">
            <Monitor />
          </el-icon>
        </div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-950">
          三圆AI知识库软件
        </h1>
        <p class="mt-2 text-sm leading-6 text-slate-500">
          面向内部知识资产、项目文档与助手能力的管理后台
        </p>
      </div>

      <div class="rounded-xl border border-[var(--admin-border)] bg-white p-6 shadow-[var(--admin-shadow-panel)] sm:p-8">
        <div class="mb-6 border-b border-slate-100 pb-3">
          <span class="text-sm font-semibold text-slate-900">账号密码登录</span>
        </div>

        <div class="space-y-5">
          <div>
            <h2 class="text-2xl font-bold tracking-tight text-slate-950">
              管理员登录
            </h2>
            <p class="mt-2 text-sm leading-6 text-slate-500">
              使用企业账号登录，进入知识库、助手与应用接入管理后台。
            </p>
          </div>

          <el-form
            label-position="top"
            @submit.prevent="handleSubmit"
          >
            <el-form-item label="登录账号">
              <el-input
                v-model="form.usernameOrEmail"
                size="large"
                placeholder="用户名或企业邮箱"
                autocomplete="username"
              >
                <template #prefix>
                  <el-icon>
                    <User />
                  </el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="访问密码">
              <el-input
                v-model="form.password"
                :type="passwordInputType"
                size="large"
                placeholder="请输入密码"
                autocomplete="current-password"
                @keyup.enter="handleSubmit"
              >
                <template #prefix>
                  <el-icon>
                    <Lock />
                  </el-icon>
                </template>
                <template #suffix>
                  <button
                    type="button"
                    class="flex items-center border-0 bg-transparent p-0 text-slate-400 transition hover:text-slate-600"
                    @click="togglePasswordVisibility"
                  >
                    <el-icon>
                      <component :is="passwordIcon" />
                    </el-icon>
                  </button>
                </template>
              </el-input>
            </el-form-item>

            <el-button
              type="primary"
              size="large"
              class="!mt-1 !w-full"
              :loading="submitting"
              @click="handleSubmit"
            >
              登录
            </el-button>
          </el-form>
        </div>

        <div
          class="mt-6 border-t border-slate-100 pt-4 text-center text-[11px] leading-5 text-slate-400"
        >
          当前阶段仅开放内部管理员登录入口。如无法访问，请联系
          <span class="font-semibold text-slate-600">IT 运维部管理员</span>
          处理账号与权限。
        </div>
      </div>

      <footer class="mt-6 text-center text-[11px] leading-5 text-slate-400">
        <p class="font-medium text-slate-500">
          仅限内部员工访问 · 禁止外泄内部数据
        </p>
        <p class="mt-1">
          © 2026 企业技术中心 (IT Department). 保留所有权利。
        </p>
      </footer>
    </div>
  </section>
</template>

<style scoped>
.login-page {
  --el-color-primary: var(--admin-primary);
  --el-color-primary-light-3: var(--admin-primary-light);
  --el-color-primary-light-7: var(--admin-primary-border);
  --el-color-primary-light-9: var(--admin-primary-soft);
  --el-color-primary-dark-2: var(--admin-primary-hover);
}
</style>
