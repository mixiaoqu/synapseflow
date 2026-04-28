"use client";

import { Building2 } from "lucide-react";

import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { TeamScopeSwitcher } from "@/components/teams/TeamScopeSwitcher";

export function TeamContextBar() {
  const { selectedTeam, teams, teamsLoading } = useTeamScope();
  const showTeamSwitcher = teamsLoading || teams.length > 1;

  return (
    <div className="shrink-0 border-b border-slate-200 bg-white/95 px-6 py-3 text-slate-900 shadow-sm shadow-slate-900/[0.02] backdrop-blur">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-blue-100 bg-blue-50 text-blue-600">
            <Building2 className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="text-xs font-medium uppercase tracking-[0.16em] text-slate-400">
                当前团队
              </span>
              <span className="truncate text-sm font-semibold text-slate-900">
                {teamsLoading ? "正在加载..." : selectedTeam?.name ?? "未选择团队"}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-slate-500">
              知识库、助手、审核发布等核心操作都会使用当前团队范围。
            </p>
          </div>
        </div>
        {showTeamSwitcher ? <TeamScopeSwitcher className="w-full xl:w-auto" /> : null}
      </div>
    </div>
  );
}
