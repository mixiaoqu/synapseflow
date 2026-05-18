export interface AdminNavItem {
  key: "dashboard" | "projects" | "knowledge-bases" | "assistants" | "organizations" | "governance";
  label: string;
  caption: string;
  to: string;
}

export const adminNav: AdminNavItem[] = [
  {
    key: "dashboard",
    label: "控制台",
    caption: "平台总览与待办入口",
    to: "/dashboard",
  },
  {
    key: "projects",
    label: "项目",
    caption: "项目与应用编排",
    to: "/projects",
  },
  {
    key: "knowledge-bases",
    label: "知识库",
    caption: "知识资产与目录管理",
    to: "/knowledge-bases",
  },
  {
    key: "assistants",
    label: "助手",
    caption: "助手能力与预览入口",
    to: "/assistants",
  },
  {
    key: "organizations",
    label: "组织",
    caption: "组织、成员与权限",
    to: "/organizations",
  },
  {
    key: "governance",
    label: "治理",
    caption: "策略、审计与安全治理",
    to: "/governance",
  },
];
