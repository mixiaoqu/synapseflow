import { request } from "@/shared/api/http";
import type { TeamSummary } from "@/shared/types/team";

export function listTeams() {
  return request<TeamSummary[]>({
    url: "/teams",
    method: "GET",
  });
}
