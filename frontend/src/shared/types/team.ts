export interface TeamSummary {
  id: number;
  name: string;
  code: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

/** 团队成员记录 */
export interface TeamMember {
  id: number;
  team_id: number;
  user_id: number;
  username?: string | null;
  email?: string | null;
  full_name?: string | null;
  role: string;
  created_at: string;
  updated_at: string;
}

/** 创建团队请求体 */
export interface CreateTeamPayload {
  name: string;
  code?: string | null;
  description?: string | null;
  member_ids?: number[];
}

/** 更新团队请求体 */
export interface UpdateTeamPayload {
  name: string;
  code?: string | null;
  description?: string | null;
}

export type TeamBulkAction = "delete";

/** 团队批量操作响应 */
export interface TeamBulkActionResponse {
  affected: number;
}

/** 团队角色标签映射 */
export const TEAM_ROLE_LABELS: Record<string, string> = {
  owner: "所有者",
  admin: "管理员",
  editor: "内容编辑",
  reviewer: "审核人员",
  viewer: "只读成员",
};

export type TeamRole = keyof typeof TEAM_ROLE_LABELS;

/** 分页团队列表响应 */
export interface TeamListResponse {
  items: TeamSummary[];
  total: number;
  page: number;
  page_size: number;
}
