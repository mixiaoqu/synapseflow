"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  Bot,
  Building2,
  CheckSquare,
  ChevronDown,
  ChevronRight,
  FolderKanban,
  Home,
  LogOut,
  Settings,
  ShieldAlert,
  Users,
} from "lucide-react";

import { TeamScopeProvider } from "@/components/team-scope/TeamScopeProvider";
import { TeamContextBar } from "@/components/team-scope/TeamContextBar";
import { BackgroundTasksPanel } from "@/components/tasks/BackgroundTasksPanel";
import { useAuthSession } from "@/hooks/useAuthSession";
import { clearAuthSession } from "@/lib/auth/session";

const AVATAR_PALETTES = [
  "bg-blue-100 text-blue-700",
  "bg-emerald-100 text-emerald-700",
  "bg-violet-100 text-violet-700",
  "bg-amber-100 text-amber-700",
  "bg-rose-100 text-rose-700",
  "bg-cyan-100 text-cyan-700",
  "bg-fuchsia-100 text-fuchsia-700",
  "bg-teal-100 text-teal-700",
];

const menuGroups = [
  {
    title: "概览",
    items: [
      { href: "/admin", title: "后台首页", icon: Home },
    ],
  },
  {
    title: "业务核心",
    items: [
      { href: "/admin/projects", title: "项目管理", icon: FolderKanban },
      { href: "/admin/documents", title: "知识库管理", icon: BookOpen },
      { href: "/admin/assistants", title: "助手管理", icon: Bot },
    ],
  },
  {
    title: "组织架构",
    items: [
      { href: "/admin/teams", title: "团队管理", icon: Building2 },
      { href: "/admin/users", title: "用户管理", icon: Users },
    ],
  },
  {
    title: "合规与质检",
    items: [
      { href: "/admin/review", title: "审核发布", icon: CheckSquare },
      { href: "/admin/qa-quality", title: "问答质检", icon: BarChart3 },
      { href: "/admin/sensitive-words", title: "敏感词管理", icon: ShieldAlert },
    ],
  },
];

const ROLE_COLORS: Record<string, { bg: string; text: string }> = {
  kb_admin: { bg: "border border-violet-400/20 bg-violet-500/20", text: "text-violet-200" },
  kb_reviewer: { bg: "border border-amber-400/20 bg-amber-500/20", text: "text-amber-200" },
  kb_editor: { bg: "border border-blue-400/20 bg-blue-500/20", text: "text-blue-200" },
  end_user: { bg: "border border-white/15 bg-white/10", text: "text-slate-300" },
};

function avatarPalette(id: number) {
  return AVATAR_PALETTES[id % AVATAR_PALETTES.length];
}

function getInitials(name?: string | null, username?: string): string {
  const src = name?.trim() || username || "?";
  if (/[\u4e00-\u9fff]/.test(src)) return src.slice(0, 1);
  return src
    .split(/\s+/)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function roleBadge(role: string) {
  const labels: Record<string, string> = {
    kb_admin: "管理员",
    kb_reviewer: "审核员",
    kb_editor: "编辑",
    end_user: "用户",
  };
  const color = ROLE_COLORS[role] ?? ROLE_COLORS.end_user;
  return { label: labels[role] ?? role, ...color };
}

function SessionLoadingScreen() {
  return (
    <div className="flex h-[100dvh] min-h-0 items-center justify-center bg-gray-950 text-white">
      <div className="rounded-2xl border border-white/10 bg-white/5 px-6 py-4 text-sm">
        正在恢复管理后台...
      </div>
    </div>
  );
}

function AdminLayoutContent({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const nextPath = `${pathname || "/admin"}${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
  const loginHref = `/login?next=${encodeURIComponent(nextPath)}`;
  const { currentUser, authChecked } = useAuthSession(loginHref, { requireAdmin: true });

  const [collapsedGroups, setCollapsedGroups] = useState<Record<number, boolean>>({});
  const toggleGroup = (idx: number) => {
    setCollapsedGroups((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  if (!authChecked || !currentUser) {
    return <SessionLoadingScreen />;
  }

  const badge = roleBadge(currentUser.role);
  const initials = getInitials(currentUser.full_name, currentUser.username);

  return (
    <TeamScopeProvider userId={currentUser.id}>
      <div className="flex h-[100dvh] min-h-0 overflow-hidden bg-gray-950 text-white">
        <aside className="flex h-full w-72 shrink-0 min-h-0 flex-col border-r border-white/10 bg-[#0f1115]">
          <div className="shrink-0 border-b border-white/10 px-5 py-5">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-500 shadow-lg shadow-blue-500/20">
                <Settings className="h-4.5 w-4.5 text-white" />
              </div>
              <div>
                <p className="text-base font-semibold leading-tight text-white">知识运营后台</p>
                <p className="mt-0.5 text-[11px] text-gray-500">Knowledge Ops Console</p>
              </div>
            </div>
          </div>

          <nav className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            <div className="space-y-6">
              {menuGroups.map((group, groupIdx) => {
                const isCollapsed = collapsedGroups[groupIdx];

                return (
                  <div key={groupIdx}>
                    <button
                      onClick={() => toggleGroup(groupIdx)}
                      className="mb-2 flex w-full items-center justify-between px-3 text-left text-xs font-medium text-gray-500 transition-colors hover:text-gray-300"
                    >
                      <span>{group.title}</span>
                      {isCollapsed ? (
                        <ChevronRight className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" />
                      )}
                    </button>
                    <div
                      className={`grid transition-[grid-template-rows,opacity] duration-200 ease-out ${
                        isCollapsed ? "grid-rows-[0fr] opacity-0" : "grid-rows-[1fr] opacity-100"
                      }`}
                    >
                      <div className="min-h-0 overflow-hidden">
                        <div className="space-y-0.5">
                          {group.items.map((item) => {
                            const Icon = item.icon;
                            const active =
                              pathname === item.href ||
                              (item.href !== "/admin" && pathname.startsWith(`${item.href}/`));

                            return (
                              <Link
                                key={item.href}
                                href={item.href}
                                className={`group relative flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm transition-all ${
                                  active
                                    ? "bg-blue-500/10 text-blue-400 font-medium before:absolute before:left-0 before:top-1/2 before:h-1/2 before:w-1 before:-translate-y-1/2 before:rounded-r-full before:bg-blue-500"
                                    : "text-gray-400 hover:bg-white/8 hover:text-white"
                                }`}
                              >
                                <Icon
                                  className={`h-4 w-4 shrink-0 transition-colors ${
                                    active
                                      ? "text-blue-400"
                                      : "text-gray-500 group-hover:text-gray-300"
                                  }`}
                                />
                                <span>{item.title}</span>
                              </Link>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </nav>

          <div className="shrink-0 border-t border-white/10 p-4">
            <div className="rounded-2xl border border-white/15 bg-white/[0.05] p-4 shadow-inner shadow-white/[0.02]">
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${avatarPalette(currentUser.id)}`}
                >
                  {initials}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-white">
                    {currentUser.full_name || currentUser.username}
                  </p>
                  <span
                    className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${badge.bg} ${badge.text}`}
                  >
                    {badge.label}
                  </span>
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <Link
                  href="/ask"
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-white/15 px-3 py-2 text-xs text-gray-300 transition-colors hover:border-white/20 hover:bg-white/[0.06] hover:text-white"
                >
                  进入问答
                </Link>
                <button
                  type="button"
                  onClick={() => clearAuthSession()}
                  className="flex items-center gap-1 rounded-xl border border-white/10 px-3 py-2 text-xs text-gray-400 transition-colors hover:border-white/20 hover:bg-white/[0.06] hover:text-white"
                  title="退出登录"
                >
                  <LogOut className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col bg-slate-50 text-slate-900">
          <TeamContextBar />
          <BackgroundTasksPanel documentsHref="/admin/documents" />
          <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        </main>
      </div>
    </TeamScopeProvider>
  );
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Suspense fallback={<SessionLoadingScreen />}>
      <AdminLayoutContent>{children}</AdminLayoutContent>
    </Suspense>
  );
}
