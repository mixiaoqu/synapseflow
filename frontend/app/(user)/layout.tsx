"use client";

import Link from "next/link";
import { Suspense } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { ChevronDown, LogOut, Shield } from "lucide-react";

import { TeamScopeProvider } from "@/components/team-scope/TeamScopeProvider";
import { TeamScopeSwitcher } from "@/components/teams/TeamScopeSwitcher";
import { useAuthSession } from "@/hooks/useAuthSession";
import { canAccessAdmin } from "@/lib/auth/roles";
import { clearAuthSession } from "@/lib/auth/session";

function SessionLoadingScreen() {
  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-[#f8fafc] text-slate-700">
      <div className="rounded-2xl border border-slate-200 bg-white px-6 py-4 text-sm shadow-sm">
        正在恢复登录状态...
      </div>
    </div>
  );
}

function UserLayoutContent({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const nextPath = `${pathname || "/ask"}${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
  const loginHref = `/login?next=${encodeURIComponent(nextPath)}`;
  const { currentUser, authChecked } = useAuthSession(loginHref);

  if (!authChecked || !currentUser) {
    return <SessionLoadingScreen />;
  }

  return (
    <TeamScopeProvider userId={currentUser.id}>
      <div className="flex h-[100dvh] min-h-0 flex-col overflow-hidden bg-[#f8fafc]">
        <header className="shrink-0 border-b border-slate-200/80 bg-white/95 backdrop-blur">
          <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4 px-4 py-3 sm:px-6">
            <div className="min-w-0">
              <Link href="/ask" className="block truncate text-base font-semibold text-slate-900">
                助手驱动的企业知识问答
              </Link>
            </div>

            <div className="flex items-center gap-3">
              <TeamScopeSwitcher />

              {canAccessAdmin(currentUser) ? (
                <Link
                  href="/admin"
                  className="hidden items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm transition-colors hover:bg-slate-50 sm:inline-flex"
                >
                  <Shield className="h-4 w-4" />
                  管理后台
                </Link>
              ) : null}

              <details className="group relative">
                <summary className="flex cursor-pointer list-none items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm transition-colors hover:bg-slate-50">
                  <div className="hidden text-right sm:block">
                    <div className="max-w-[180px] truncate font-medium text-slate-800">
                      {currentUser.full_name || currentUser.username}
                    </div>
                  </div>
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">
                    {(currentUser.full_name || currentUser.username).slice(0, 1).toUpperCase()}
                  </div>
                  <ChevronDown className="h-4 w-4 text-slate-400" />
                </summary>

                <div className="absolute right-0 z-20 mt-2 w-56 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
                  <div className="border-b border-slate-100 px-4 py-3">
                    <div className="truncate text-sm font-medium text-slate-900">
                      {currentUser.full_name || currentUser.username}
                    </div>
                    <div className="truncate text-xs text-slate-500">{currentUser.email}</div>
                  </div>

                  {canAccessAdmin(currentUser) ? (
                    <Link
                      href="/admin"
                      className="flex items-center gap-2 px-4 py-3 text-sm text-slate-700 transition-colors hover:bg-slate-50 sm:hidden"
                    >
                      <Shield className="h-4 w-4" />
                      管理后台
                    </Link>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => clearAuthSession()}
                    className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm text-slate-700 transition-colors hover:bg-slate-50"
                  >
                    <LogOut className="h-4 w-4" />
                    退出登录
                  </button>
                </div>
              </details>
            </div>
          </div>
        </header>

        <main className="h-0 min-h-0 flex-1 overflow-hidden">{children}</main>
      </div>
    </TeamScopeProvider>
  );
}

export default function UserLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Suspense fallback={<SessionLoadingScreen />}>
      <UserLayoutContent>{children}</UserLayoutContent>
    </Suspense>
  );
}
