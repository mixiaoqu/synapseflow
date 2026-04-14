"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, LogOut, Shield, Users } from "lucide-react";

import { AskTeamScopeProvider, useAskTeamScope } from "@/components/kb-chat/AskTeamScopeProvider";
import { useAuthSession } from "@/hooks/useAuthSession";
import { canAccessAdmin } from "@/lib/auth/roles";
import { clearAuthSession } from "@/lib/auth/session";

function SessionLoadingScreen() {
  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-[#f7f7f5] text-slate-700">
      <div className="rounded-2xl border border-slate-200 bg-white px-6 py-4 text-sm shadow-sm">
        正在恢复登录状态...
      </div>
    </div>
  );
}

function TeamScopeSwitcher() {
  const { teamId, setTeamId, teams, teamsLoading, selectedTeam } = useAskTeamScope();

  if (teamsLoading) {
    return (
      <div className="inline-flex h-10 min-w-[180px] items-center rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-400 shadow-sm">
        正在加载团队...
      </div>
    );
  }

  if (teams.length <= 1) {
    return (
      <div className="inline-flex h-10 min-w-[180px] items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 shadow-sm">
        <Users className="h-4 w-4 text-slate-400" />
        <span className="truncate">{selectedTeam?.name ?? "暂无团队"}</span>
      </div>
    );
  }

  return (
    <div className="relative">
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

export default function UserLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const loginHref = `/login?next=${encodeURIComponent(pathname || "/ask")}`;
  const { currentUser, authChecked } = useAuthSession(loginHref);

  if (!authChecked || !currentUser) {
    return <SessionLoadingScreen />;
  }

  return (
    <AskTeamScopeProvider userId={currentUser.id}>
      <div className="flex h-[100dvh] min-h-0 flex-col overflow-hidden bg-[#f7f7f5]">
        <header className="shrink-0 border-b border-slate-200/80 bg-white/92 backdrop-blur-md">
          <div className="mx-auto flex max-w-[1320px] flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <Link href="/ask" className="text-base font-semibold text-slate-900">
                企业知识问答
              </Link>
              <p className="mt-0.5 text-xs text-slate-500">
                团队作为全局工作上下文，会话默认继承当前团队
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
              <TeamScopeSwitcher />

              <div className="flex items-center gap-3">
                {canAccessAdmin(currentUser) ? (
                  <Link
                    href="/admin"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
                  >
                    <Shield className="h-4 w-4" />
                    进入管理后台
                  </Link>
                ) : null}

                <div className="hidden text-right sm:block">
                  <p className="text-sm font-medium text-slate-800">
                    {currentUser.full_name || currentUser.username}
                  </p>
                  <p className="text-xs text-slate-500">{currentUser.email}</p>
                </div>

                <button
                  type="button"
                  onClick={() => clearAuthSession()}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
                >
                  <LogOut className="h-4 w-4" />
                  退出登录
                </button>
              </div>
            </div>
          </div>
        </header>

        <main className="h-0 min-h-0 flex-1 overflow-hidden">{children}</main>
      </div>
    </AskTeamScopeProvider>
  );
}
