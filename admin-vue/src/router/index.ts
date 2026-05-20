import { createRouter, createWebHistory } from "vue-router";

import AdminLayout from "@/app/layouts/AdminLayout.vue";
import AuthLayout from "@/app/layouts/AuthLayout.vue";
import { createAuthGuard } from "@/app/guards/auth";
import LoginPage from "@/modules/auth/pages/LoginPage.vue";
import AssistantDetailPage from "@/modules/assistants/pages/AssistantDetailPage.vue";
import AssistantListPage from "@/modules/assistants/pages/AssistantListPage.vue";
import EmbedAssistantPage from "@/modules/embed/pages/EmbedAssistantPage.vue";
import DocumentDetailPage from "@/modules/knowledge-bases/pages/DocumentDetailPage.vue";
import KnowledgeBaseDetailPage from "@/modules/knowledge-bases/pages/KnowledgeBaseDetailPage.vue";
import KnowledgeBaseListPage from "@/modules/knowledge-bases/pages/KnowledgeBaseListPage.vue";
import ModulePlaceholderPage from "@/modules/platform/pages/ModulePlaceholderPage.vue";
import ProjectAppDetailPage from "@/modules/projects/pages/ProjectAppDetailPage.vue";
import ProjectAppListPage from "@/modules/projects/pages/ProjectAppListPage.vue";
import ProjectListPage from "@/modules/projects/pages/ProjectListPage.vue";

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
      path: "/embed/assistant",
      name: "embed-assistant",
      component: EmbedAssistantPage,
      meta: {
        public: true,
        bypassAdminCheck: true,
        title: "嵌入助手",
      },
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
          component: ProjectListPage,
          meta: {
            title: "应用与发布",
            description: "项目列表与发布渠道管理入口。",
          },
        },
        {
          path: "projects/:projectId/apps",
          name: "project-apps",
          component: ProjectAppListPage,
          meta: {
            title: "发布渠道",
            description: "当前项目下的应用与发布配置列表。",
          },
        },
        {
          path: "projects/:projectId/apps/new",
          name: "project-app-create",
          component: ProjectAppDetailPage,
          meta: {
            title: "新建发布渠道",
            description: "新建项目下的应用与发布配置。",
          },
        },
        {
          path: "projects/:projectId/apps/:appId",
          name: "project-app-detail",
          component: ProjectAppDetailPage,
          meta: {
            title: "发布渠道详情",
            description: "编辑项目下的应用与发布配置。",
          },
        },
        {
          path: "knowledge-bases",
          name: "knowledge-bases",
          component: KnowledgeBaseListPage,
          meta: {
            title: "知识库",
            description: "知识库卡片工作台，后续继续接入目录、文档与绑定流程。",
          },
        },
        {
          path: "knowledge-bases/:knowledgeBaseId",
          name: "knowledge-base-detail",
          component: KnowledgeBaseDetailPage,
          meta: {
            title: "知识库详情",
            description: "知识库分类侧栏与文档管理工作台。",
          },
        },
        {
          path: "knowledge-bases/:knowledgeBaseId/documents/:documentId",
          name: "knowledge-base-document-detail",
          component: DocumentDetailPage,
          meta: {
            title: "文档详情",
            description: "文档正文与真实分块查看页面。",
          },
        },
        {
          path: "assistants",
          name: "assistants",
          component: AssistantListPage,
          meta: {
            title: "助手",
            description: "助手列表、配置与预览调试工作台。",
          },
        },
        {
          path: "assistants/new",
          name: "assistant-create",
          component: AssistantDetailPage,
          meta: {
            title: "新建助手",
            description: "创建新的助手配置并进行预览调试。",
          },
        },
        {
          path: "assistants/:assistantId",
          name: "assistant-detail",
          component: AssistantDetailPage,
          meta: {
            title: "助手详情",
            description: "编辑助手配置并进行预览调试。",
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
