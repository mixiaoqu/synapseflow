export interface AdminNavItem {
  key:
    | "dashboard"
    | "projects"
    | "knowledge-bases"
    | "assistants"
    | "organizations"
    | "users"
    | "content-risk-overview"
    | "content-risk-libraries";
  label: string;
  to: string;
}

export interface AdminNavGroup {
  key: "knowledge-and-apps" | "organization-and-access" | "content-risk";
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
  {
    key: "content-risk",
    label: "内容风控",
    items: [
      {
        key: "content-risk-overview",
        label: "数据总览",
        to: "/content-risk/overview",
      },
      {
        key: "content-risk-libraries",
        label: "全局规则库",
        to: "/content-risk/libraries",
      },
    ],
  },
];
