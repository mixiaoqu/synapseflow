export interface AdminNavItem {
  key: "dashboard" | "projects" | "knowledge-bases" | "assistants" | "organizations" | "users" | "governance";
  label: string;
  to: string;
}

// 一级导航只保留平台级业务域，知识库内的文档/目录/审核等能力放到各模块内部继续展开。
export const adminNav: AdminNavItem[] = [
  {
    key: "dashboard",
    label: "控制台",
    to: "/dashboard",
  },
  {
    key: "projects",
    label: "应用与发布",
    to: "/projects",
  },
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
    key: "organizations",
    label: "团队",
    to: "/organizations",
  },
  {
    key: "users",
    label: "用户",
    to: "/users",
  },
  {
    key: "governance",
    label: "治理",
    to: "/governance",
  },
];
