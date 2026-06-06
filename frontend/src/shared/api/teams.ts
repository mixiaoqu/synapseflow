import { request } from "@/shared/api/http";
import type {
  TeamBulkAction,
  TeamBulkActionResponse,
  TeamMember,
  TeamListResponse,
  TeamRole,
  TeamSummary,
} from "@/shared/types/team";
import type { CreateTeamPayload, UpdateTeamPayload } from "@/shared/types/team";

/** 团队列表查询参数 */
interface ListTeamsParams {
  page?: number;
  page_size?: number;
  keyword?: string;
}

/**
 * 获取团队列表（分页）
 * @param params - 分页参数（page、page_size、keyword）
 * @returns 分页团队列表响应
 */
export function listTeams(params?: ListTeamsParams) {
  return request<TeamListResponse>({
    url: "/teams",
    method: "GET",
    params,
  });
}

/**
 * 创建新团队
 * @param payload - 团队创建数据（名称必填，编码和描述可选）
 * @returns 创建后的团队数据
 */
export function createTeam(payload: CreateTeamPayload) {
  return request<TeamSummary>({
    url: "/teams",
    method: "POST",
    data: payload,
  });
}

/**
 * 更新团队信息
 * @param teamId - 团队 ID
 * @param payload - 更新数据
 * @returns 更新后的团队数据
 */
export function updateTeam(teamId: number, payload: UpdateTeamPayload) {
  return request<TeamSummary>({
    url: `/teams/${teamId}`,
    method: "PUT",
    data: payload,
  });
}

/**
 * 删除团队
 * @param teamId - 团队 ID
 */
export function deleteTeam(teamId: number) {
  return request<{ message: string }>({
    url: `/teams/${teamId}`,
    method: "DELETE",
  });
}

/** 批量操作团队 */
export function bulkActionTeams(teamIds: number[], action: TeamBulkAction) {
  return request<TeamBulkActionResponse>({
    url: "/teams/bulk-actions",
    method: "POST",
    data: {
      team_ids: teamIds,
      action,
    },
  });
}

/**
 * 获取团队成员列表
 * @param teamId - 团队 ID
 * @returns 成员数组
 */
export function listTeamMembers(teamId: number) {
  return request<TeamMember[]>({
    url: `/teams/${teamId}/members`,
    method: "GET",
  });
}

/**
 * 添加团队成员
 * @param teamId - 团队 ID
 * @param payload - 成员添加数据（用户 ID + 角色）
 * @returns 创建后的成员记录
 */
export function addTeamMember(
  teamId: number,
  payload: { user_id: number; role: string }
) {
  return request<TeamMember>({
    url: `/teams/${teamId}/members`,
    method: "POST",
    data: payload,
  });
}

/**
 * 更新成员角色
 * @param teamId - 团队 ID
 * @param userId - 用户 ID
 * @param payload - 角色更新数据
 * @returns 更新后的成员记录
 */
export function updateTeamMember(
  teamId: number,
  userId: number,
  payload: { role: string }
) {
  return request<TeamMember>({
    url: `/teams/${teamId}/members/${userId}`,
    method: "PUT",
    data: payload,
  });
}

/**
 * 移除团队成员
 * @param teamId - 团队 ID
 * @param userId - 用户 ID
 */
export function deleteTeamMember(teamId: number, userId: number) {
  return request<{ message: string }>({
    url: `/teams/${teamId}/members/${userId}`,
    method: "DELETE",
  });
}

/** 批量更新团队成员角色 */
export function bulkUpdateTeamMembersRole(teamId: number, userIds: number[], role: TeamRole) {
  return request<TeamBulkActionResponse>({
    url: `/teams/${teamId}/members/bulk-role`,
    method: "POST",
    data: {
      user_ids: userIds,
      role,
    },
  });
}

/** 批量移除团队成员 */
export function bulkDeleteTeamMembers(teamId: number, userIds: number[]) {
  return request<TeamBulkActionResponse>({
    url: `/teams/${teamId}/members/bulk-delete`,
    method: "POST",
    data: {
      user_ids: userIds,
    },
  });
}
