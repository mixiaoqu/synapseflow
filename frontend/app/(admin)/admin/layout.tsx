"use client";

export const dynamic = "force-dynamic";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  Bot,
  Building2,
  CheckSquare,
  ChevronRight,
  Database,
  Home,
  LogOut,
  Settings,
  ShieldAlert,
  Users,
} from "lucide-react";

import { TeamScopeProvider } from "@/components/kb-chat/AskTeamScopeProvider";
import { BackgroundTasksPanel } from "@/components/tasks/BackgroundTasksPanel";
import { TeamScopeSwitcher } from "@/components/teams/TeamScopeSwitcher";
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

const ROLE_COLORS: Record<string, { bg: string; text: string }> = {
  kb_admin: { bg: "bg-violet-50", text: "text-violet-700" },
  kb_reviewer: { bg: "bg-amber-50", text: "text-amber-700" },
  kb_editor: { bg: "bg-blue-50", text: "text-blue-700" },
  end_user: { bg: "bg-slate-100", text: "text-slate-600" },
};

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

const navItems = [
  { href: "/admin", title: "后台首页", icon: Home },
  { href: "/admin/documents", title: "文档管理", icon: Database },
  { href: "/admin/knowledge-bases", title: "知识库管理", icon: BookOpen },
  { href: "/admin/assistants", title: "助手管理", icon: Bot },
  { href: "/admin/review", title: "审核发布", icon: CheckSquare },
  { href: "/admin/qa-quality", title: "问答质检", icon: BarChart3 },
  { href: "/admin/sensitive-words", title: "敏感词管理", icon: ShieldAlert },
  { href: "/admin/teams", title: "团队管理", icon: Building2 },
  { href: "/admin/users", title: "用户管理", icon: Users },
];

function SessionLoadingScreen() {
  return (
    <div className="flex h-[100dvh] min-h-0 items-center justify-center bg-gray-950 text-white">
      <div className="rounded-2xl border border-white/10 bg-white/5 px-6 py-4 text-sm">
        正在恢复管理后台...
      </div>
    </div>
  );
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const nextPath = `${pathname || "/admin"}${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
  const loginHref = `/login?next=${encodeURIComponent(nextPath)}`;
  const { currentUser, authChecked } = useAuthSession(loginHref, { requireAdmin: true });

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
                <p className="text-base font-semibold leading-tight text-white">知识库管理后台</p>
                <p className="mt-0.5 text-[11px] text-gray-500">Knowledge Ops Console</p>
              </div>
            </div>
            <div className="mt-4">
              <TeamScopeSwitcher className="w-full min-w-0" />
            </div>
          </div>

          <nav className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            <div className="space-y-0.5">
              {navItems.map((item) => {
                const Icon = item.icon;
                const active =
                  pathname === item.href ||
                  (item.href !== "/admin" && pathname.startsWith(`${item.href}/`));

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`group flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm transition-all ${
                      active
                        ? "bg-white text-gray-900 font-medium shadow-sm"
                        : "text-gray-400 hover:bg-white/8 hover:text-white"
                    }`}
                  >
                    <Icon
                      className={`h-4 w-4 shrink-0 transition-colors ${
                        active ? "text-gray-700" : "text-gray-500 group-hover:text-gray-300"
                      }`}
                    />
                    <span>{item.title}</span>
                    {active ? <ChevronRight className="ml-auto h-3.5 w-3.5 text-gray-400" /> : null}
                  </Link>
                );
              })}
            </div>
          </nav>

          <div className="shrink-0 border-t border-white/10 p-4">
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
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
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-white/10 px-3 py-2 text-xs text-gray-300 transition-colors hover:bg-white/8 hover:text-white"
                >
                  进入问答
                </Link>
                <button
                  type="button"
                  onClick={() => clearAuthSession()}
                  className="flex items-center gap-1 rounded-xl border border-red-500/20 px-3 py-2 text-xs text-red-400 transition-colors hover:bg-red-500/10 hover:text-red-300"
                >
                  <LogOut className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
        </aside>

        <main className="min-w-0 flex-1 bg-gradient-to-b from-slate-50 to-white text-slate-900">
          <BackgroundTasksPanel documentsHref="/admin/documents" />
          <div className="h-full min-h-0 overflow-y-auto">{children}</div>
        </main>
      </div>
    </TeamScopeProvider>
  );
}
