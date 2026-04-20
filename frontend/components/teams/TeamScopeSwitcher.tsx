"use client";

import { ChevronDown, Users } from "lucide-react";

import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { cn } from "@/lib/utils";

export function TeamScopeSwitcher({
  className,
}: {
  className?: string;
}) {
  const { teamId, setTeamId, teams, teamsLoading, selectedTeam } = useTeamScope();

  if (teamsLoading) {
    return (
      <div
        className={cn(
          "inline-flex h-10 min-w-[180px] items-center rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-400 shadow-sm",
          className,
        )}
      >
        正在加载团队...
      </div>
    );
  }

  if (teams.length <= 1) {
    return (
      <div
        className={cn(
          "inline-flex h-10 min-w-[180px] items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 shadow-sm",
          className,
        )}
      >
        <Users className="h-4 w-4 text-slate-400" />
        <span className="truncate">{selectedTeam?.name ?? "暂无团队"}</span>
      </div>
    );
  }

  return (
    <div className={cn("relative", className)}>
      <Users className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <select
        value={teamId != null ? String(teamId) : ""}
        onChange={(event) => setTeamId(event.target.value ? Number(event.target.value) : null)}
        className="h-10 min-w-[200px] appearance-none rounded-xl border border-slate-200 bg-white pl-9 pr-9 text-sm text-slate-700 shadow-sm outline-none transition hover:border-slate-300 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
      >
        <option value="">选择团队</option>
        {teams.map((team) => (
          <option key={team.id} value={team.id}>
            {team.name}
          </option>
        ))}
      </select>
    </div>
  );
}
