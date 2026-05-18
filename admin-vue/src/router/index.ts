import { createRouter, createWebHistory } from "vue-router";

import AdminLayout from "@/app/layouts/AdminLayout.vue";
import AuthLayout from "@/app/layouts/AuthLayout.vue";
import { createAuthGuard } from "@/app/guards/auth";
import LoginPage from "@/modules/auth/pages/LoginPage.vue";
import ModulePlaceholderPage from "@/modules/platform/pages/ModulePlaceholderPage.vue";

// 当前阶段所有一级后台模块先复用统一骨架页，后续再逐个替换成真实业务页面。
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      component: AuthLayout,
      meta: {
        public: true,
        guestOnly: true,
      },
      children: [
        {
          path: "",
          name: "login",
          component: LoginPage,
          meta: {
            title: "登录",
          },
        },
      ],
    },
    {
      path: "/",
      component: AdminLayout,
      meta: {
        requiresAuth: true,
      },
      children: [
        {
          path: "",
          redirect: "/dashboard",
        },
        {
          path: "dashboard",
          name: "dashboard",
          component: ModulePlaceholderPage,
          meta: {
            title: "控制台",
            description: "平台总览与待办入口，后续在此接入全局工作台内容。",
          },
        },
        {
          path: "projects",
          name: "projects",
          component: ModulePlaceholderPage,
          meta: {
            title: "项目",
            description: "项目资源导航占位，后续任务在此接入项目管理相关页面。",
          },
        },
        {
          path: "knowledge-bases",
          name: "knowledge-bases",
          component: ModulePlaceholderPage,
          meta: {
            title: "知识库",
            description: "知识库资源导航占位，后续任务在此接入目录、文档和绑定流程。",
          },
        },
        {
          path: "assistants",
          name: "assistants",
          component: ModulePlaceholderPage,
          meta: {
            title: "助手",
            description: "助手资源导航占位，后续任务在此接入助手配置与调试能力。",
          },
        },
        {
          path: "organizations",
          name: "organizations",
          component: ModulePlaceholderPage,
          meta: {
            title: "组织",
            description: "组织资源导航占位，后续任务在此接入团队、成员与角色管理。",
          },
        },
        {
          path: "governance",
          name: "governance",
          component: ModulePlaceholderPage,
          meta: {
            title: "治理",
            description: "治理资源导航占位，后续任务在此接入审计、敏感词与规则治理。",
          },
        },
      ],
    },
  ],
});

router.beforeEach(createAuthGuard());

export default router;
