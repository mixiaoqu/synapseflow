export interface AdminNavItem {
  key:
    | "dashboard"
    | "projects"
    | "knowledge-bases"
    | "assistants"
    | "organizations"
    | "users"
    | "qa-logs"
    | "content-risk-overview"
    | "content-risk-libraries"
    | "content-risk-logs";
  label: string;
  to: string;
}

export interface AdminNavGroup {
  key: "knowledge-and-apps" | "operations-and-review" | "organization-and-access";
  label: string;
  items: AdminNavItem[];
}

export const adminPrimaryNav: AdminNavItem[] = [
  {
    key: "dashboard",
    label: "控制台",
    to: "/dashboard",
  },
];

export const adminNavGroups: AdminNavGroup[] = [
  {
    key: "knowledge-and-apps",
    label: "知识与应用",
    items: [
      {
        key: "knowledge-bases",
        label: "知识库",
        to: "/knowledge-bases",
      },
      {
        key: "assistants",
        label: "助手",
        to: "/assistants",
      },
      {
        key: "projects",
        label: "应用接入",
        to: "/projects",
      },
    ],
  },
  {
    key: "operations-and-review",
    label: "运营与质检",
    items: [
      {
        key: "qa-logs",
        label: "问答日志",
        to: "/qa-logs",
      },
      {
        key: "content-risk-overview",
        label: "风控总览",
        to: "/content-risk/overview",
      },
      {
        key: "content-risk-libraries",
        label: "风控规则库",
        to: "/content-risk/libraries",
      },
      {
        key: "content-risk-logs",
        label: "风控判定日志",
        to: "/content-risk/logs",
      },
    ],
  },
  {
    key: "organization-and-access",
    label: "组织与权限",
    items: [
      {
        key: "organizations",
        label: "团队",
        to: "/organizations",
      },
      {
        key: "users",
        label: "用户",
        to: "/users",
      },
    ],
  },
];
