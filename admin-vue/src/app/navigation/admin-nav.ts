export interface AdminNavItem {
  key: "dashboard" | "projects" | "knowledge-bases" | "assistants" | "organizations" | "governance";
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
    label: "项目",
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
    label: "组织",
    to: "/organizations",
  },
  {
    key: "governance",
    label: "治理",
    to: "/governance",
  },
];
