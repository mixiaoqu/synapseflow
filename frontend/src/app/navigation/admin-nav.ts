export interface AdminNavItem {
  key:
    | "dashboard"
    | "model-usage"
    | "projects"
    | "knowledge-bases"
    | "assistants"
    | "agent-integrations"
    | "evaluations"
    | "organizations"
    | "roles-permissions"
    | "qa-logs"
    | "qa-test"
    | "content-risk-libraries"
    | "content-risk-logs";
  label: string;
  to: string;
}

export interface AdminNavGroup {
  key: "overview" | "build-and-apps" | "testing-and-evaluation" | "runtime-and-security" | "system-and-organization";
  label: string;
  items: AdminNavItem[];
}

export const adminNavGroups: AdminNavGroup[] = [
  {
    key: "overview",
    label: "概览",
    items: [
      {
        key: "dashboard",
        label: "控制台",
        to: "/dashboard",
      },
      {
        key: "model-usage",
        label: "AI 成本中心",
        to: "/model-usage",
      },
    ],
  },
  {
    key: "build-and-apps",
    label: "构建与应用",
    items: [
      {
        key: "knowledge-bases",
        label: "企业知识库",
        to: "/knowledge-bases",
      },
      {
        key: "assistants",
        label: "智能助手",
        to: "/assistants",
      },
      {
        key: "agent-integrations",
        label: "Agent 集成",
        to: "/agent-integrations",
      },
      {
        key: "projects",
        label: "应用接入",
        to: "/projects",
      },
    ],
  },
  {
    key: "testing-and-evaluation",
    label: "测试与评测",
    items: [
      {
        key: "qa-test",
        label: "问答测试台",
        to: "/qa-test",
      },
      {
        key: "evaluations",
        label: "评测中心",
        to: "/evaluations",
      },
    ],
  },
  {
    key: "runtime-and-security",
    label: "运行与安全",
    items: [
      {
        key: "qa-logs",
        label: "问答对话日志",
        to: "/qa-logs",
      },
      {
        key: "content-risk-libraries",
        label: "风控规则配置",
        to: "/content-risk/libraries",
      },
      {
        key: "content-risk-logs",
        label: "风控拦截日志",
        to: "/content-risk/logs",
      },
    ],
  },
  {
    key: "system-and-organization",
    label: "系统与组织",
    items: [
      {
        key: "organizations",
        label: "成员与团队",
        to: "/organizations",
      },
      {
        key: "roles-permissions",
        label: "角色与权限",
        to: "/users",
      },
    ],
  },
];
