import { createRouter, createWebHistory } from "vue-router";

import AdminLayout from "@/app/layouts/AdminLayout.vue";
import AuthLayout from "@/app/layouts/AuthLayout.vue";
import { createAuthGuard } from "@/app/guards/auth";
import { useAdminBreadcrumbStore } from "@/stores/admin-breadcrumb";
import LoginPage from "@/modules/auth/pages/LoginPage.vue";
import AssistantDetailPage from "@/modules/assistants/pages/AssistantDetailPage.vue";
import AssistantListPage from "@/modules/assistants/pages/AssistantListPage.vue";
import BusinessApiDetailPage from "@/modules/business-tools/pages/BusinessApiDetailPage.vue";
import BusinessApiPage from "@/modules/business-tools/pages/BusinessApiPage.vue";
import BusinessToolListPage from "@/modules/business-tools/pages/BusinessToolListPage.vue";
import BusinessConnectionPage from "@/modules/business-tools/pages/BusinessConnectionPage.vue";
import BusinessToolCallLogPage from "@/modules/business-tools/pages/BusinessToolCallLogPage.vue";
import BusinessToolDetailPage from "@/modules/business-tools/pages/BusinessToolDetailPage.vue";
import ContentRiskLibrariesPage from "@/modules/content-risk/pages/ContentRiskLibrariesPage.vue";
import ContentRiskLogsPage from "@/modules/content-risk/pages/ContentRiskLogsPage.vue";
import EmbedAssistantPage from "@/modules/embed/pages/EmbedAssistantPage.vue";
import EvaluationDatasetDetailPage from "@/modules/evaluations/pages/EvaluationDatasetDetailPage.vue";
import EvaluationKnowledgeBasePage from "@/modules/evaluations/pages/EvaluationKnowledgeBasePage.vue";
import EvaluationOverviewPage from "@/modules/evaluations/pages/EvaluationOverviewPage.vue";
import EvaluationReportsPage from "@/modules/evaluations/pages/EvaluationReportsPage.vue";
import DocumentDetailPage from "@/modules/knowledge-bases/pages/DocumentDetailPage.vue";
import KnowledgeBaseDetailPage from "@/modules/knowledge-bases/pages/KnowledgeBaseDetailPage.vue";
import KnowledgeBaseListPage from "@/modules/knowledge-bases/pages/KnowledgeBaseListPage.vue";
import DashboardPage from "@/modules/platform/pages/DashboardPage.vue";
import QaLogListPage from "@/modules/qa-logs/pages/QaLogListPage.vue";
import TeamListPage from "@/modules/organizations/pages/TeamListPage.vue";
import UserListPage from "@/modules/users/pages/UserListPage.vue";
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
          component: DashboardPage,
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
            description: "产品、项目与应用端接入管理入口。",
          },
        },
        {
          path: "projects/:projectId/apps",
          name: "project-apps",
          component: ProjectAppListPage,
          meta: {
            parent: "projects",
            title: "应用端",
            description: "当前项目下的应用端与接入配置。",
          },
        },
        {
          path: "projects/:projectId/apps/new",
          name: "project-app-create",
          component: ProjectAppDetailPage,
          meta: {
            parent: "project-apps",
            title: "新建应用端",
            description: "新建项目下的应用端与接入配置。",
          },
        },
        {
          path: "projects/:projectId/apps/:appId",
          name: "project-app-detail",
          component: ProjectAppDetailPage,
          meta: {
            parent: "project-apps",
            title: "应用端详情",
            description: "编辑项目下的应用端与接入配置。",
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
            parent: "knowledge-bases",
            title: "知识库详情",
            description: "知识库分类侧栏与文档管理工作台。",
          },
        },
        {
          path: "knowledge-bases/:knowledgeBaseId/documents/:documentId",
          name: "knowledge-base-document-detail",
          component: DocumentDetailPage,
          meta: {
            parent: "knowledge-base-detail",
            title: "文档详情",
            description: "文档正文与真实分块查看页面。",
          },
        },
        {
          path: "evaluations/knowledge-bases/:knowledgeBaseId",
          name: "evaluation-knowledge-base-detail",
          component: KnowledgeBaseDetailPage,
          meta: {
            parent: "evaluation-knowledge-bases",
            title: "评测基准库详情",
            description: "评测基准库分类侧栏与文档管理工作台。",
          },
        },
        {
          path: "evaluations/knowledge-bases/:knowledgeBaseId/documents/:documentId",
          name: "evaluation-knowledge-base-document-detail",
          component: DocumentDetailPage,
          meta: {
            parent: "evaluation-knowledge-base-detail",
            title: "文档详情",
            description: "评测基准库文档正文与真实分块查看页面。",
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
            parent: "assistants",
            title: "新建助手",
            description: "创建新的助手配置并进行预览调试。",
          },
        },
        {
          path: "assistants/:assistantId",
          name: "assistant-detail",
          component: AssistantDetailPage,
          meta: {
            parent: "assistants",
            title: "助手详情",
            description: "编辑助手配置并进行预览调试。",
          },
        },
        {
          path: "business-tools",
          name: "business-tools",
          component: BusinessToolListPage,
          meta: {
            title: "业务工具",
            description: "维护可供智能助手调用的外部业务接口工具。",
          },
        },
        {
          path: "business-tools/connections",
          name: "business-tool-connections",
          component: BusinessConnectionPage,
          meta: {
            parent: "business-tools",
            title: "业务连接",
            description: "管理外部业务系统地址、环境和鉴权引用。",
          },
        },
        {
          path: "business-tools/apis",
          name: "business-tool-apis",
          component: BusinessApiPage,
          meta: {
            parent: "business-tools",
            title: "业务接口",
            description: "维护可被业务工具复用的外部接口定义。",
          },
        },
        {
          path: "business-tools/apis/new",
          name: "business-tool-api-create",
          component: BusinessApiDetailPage,
          meta: {
            parent: "business-tool-apis",
            title: "新建业务接口",
            description: "创建一份可供业务工具实现复用的外部接口定义。",
          },
        },
        {
          path: "business-tools/apis/:apiId",
          name: "business-tool-api-detail",
          component: BusinessApiDetailPage,
          meta: {
            parent: "business-tool-apis",
            title: "业务接口详情",
            description: "编辑外部接口结构、请求字段和响应字段定义。",
          },
        },
        {
          path: "business-tools/logs",
          name: "business-tool-logs",
          component: BusinessToolCallLogPage,
          meta: {
            parent: "business-tools",
            title: "业务工具调用记录",
            description: "查看工具调用状态、耗时和脱敏请求响应摘要。",
          },
        },
        {
          path: "business-tools/new",
          name: "business-tool-create",
          component: BusinessToolDetailPage,
          meta: {
            parent: "business-tools",
            title: "新建业务工具",
            description: "定义业务能力、绑定实现并发布给应用使用。",
          },
        },
        {
          path: "business-tools/:toolId",
          name: "business-tool-detail",
          component: BusinessToolDetailPage,
          meta: {
            parent: "business-tools",
            title: "业务工具详情",
            description: "编辑业务能力、工具实现、测试配置与发布状态。",
          },
        },
        {
          path: "qa-logs",
          name: "qa-logs",
          component: QaLogListPage,
          meta: {
            title: "问答日志",
            description: "查看问答记录、检索命中、用户反馈和人工质检结果。",
          },
        },
        {
          path: "evaluations",
          name: "evaluations",
          component: EvaluationOverviewPage,
          meta: {
            title: "评测集",
            description: "维护知识库问答评测集、用例和运行入口。",
          },
        },
        {
          path: "evaluations/knowledge-bases",
          name: "evaluation-knowledge-bases",
          component: EvaluationKnowledgeBasePage,
          meta: {
            parent: "evaluations",
            title: "评测基准库",
            description: "管理评测集绑定的稳定数据来源。",
          },
        },
        {
          path: "evaluations/datasets/:datasetId",
          name: "evaluation-dataset-detail",
          component: EvaluationDatasetDetailPage,
          meta: {
            parent: "evaluations",
            title: "评测集详情",
            description: "维护评测用例和评测运行入口。",
          },
        },
        {
          path: "evaluations/runs/:runId",
          name: "evaluation-run-report",
          component: EvaluationReportsPage,
          meta: {
            parent: "evaluations",
            title: "评测报告",
            description: "查看单次评测运行的报告和用例结果。",
          },
        },
        {
          path: "evaluations/reports",
          name: "evaluation-reports",
          component: EvaluationReportsPage,
          meta: {
            parent: "evaluations",
            title: "评测任务 / 报告",
            description: "查看后台评测任务状态和单次评测报告。",
          },
        },
        {
          path: "organizations",
          name: "organizations",
          component: TeamListPage,
          meta: {
            title: "组织",
            description: "团队与成员管理。",
          },
        },
        {
          path: "users",
          name: "users",
          component: UserListPage,
          meta: {
            title: "用户",
            description: "管理系统中所有用户的账号信息、角色权限和启停状态。",
          },
        },
        {
          path: "content-risk",
          redirect: "/content-risk/logs",
        },
        {
          path: "governance",
          redirect: "/content-risk/logs",
        },
        {
          path: "content-risk/libraries",
          name: "content-risk-libraries",
          component: ContentRiskLibrariesPage,
          meta: {
            title: "内容风控中心 - 全局规则库",
            description: "统一维护全局生效的规则库、规则明细和适用场景。",
          },
        },
        {
          path: "content-risk/logs",
          name: "content-risk-logs",
          component: ContentRiskLogsPage,
          meta: {
            title: "内容风控中心 - 判定日志",
            description: "查询内容风控触发记录、命中规则、风险等级和最终动作。",
          },
        },
      ],
    },
  ],
});

router.beforeEach(createAuthGuard());
router.afterEach(() => {
  useAdminBreadcrumbStore().clearDynamicTitles();
});

export default router;
