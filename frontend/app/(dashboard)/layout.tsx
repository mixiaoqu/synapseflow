"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { LogOut, MoreHorizontal } from "lucide-react";

import { BackgroundTasksPanel } from "@/components/tasks/BackgroundTasksPanel";
import { authApi } from "@/lib/api/endpoints/auth";
import {
  AUTH_CHANGED_EVENT,
  clearAuthSession,
  getAccessToken,
  getStoredUser,
  setAuthSession,
  type AuthUser,
} from "@/lib/auth/session";

const navItems = [
  { href: "/kb-chat", icon: "📚", title: "知识库问答", desc: "面向用户的单轮问答" },
  { href: "/kb-curation", icon: "🧭", title: "知识库治理", desc: "面向管理员的多轮评估" },
  { href: "/revision", icon: "📝", title: "文档修订", desc: "基于建议生成修订内容" },
  { href: "/documents", icon: "🗂️", title: "文档库", desc: "上传、检索与管理文档" },
  { href: "/prototype", icon: "🧩", title: "原型生成", desc: "从需求自动生成界面原型" },
  { href: "/assistant-lab", icon: "🤖", title: "项目助手", desc: "按项目与端模拟不同助手的回答" },
];

function SessionLoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-900 text-white">
      <div className="rounded-2xl border border-white/10 bg-white/5 px-6 py-4 text-sm">
        正在恢复登录状态...
      </div>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const userDisplayName = useMemo(() => {
    if (!currentUser) return "";
    const fullName = currentUser.full_name?.trim();
    return fullName || currentUser.username;
  }, [currentUser]);
  const userInitial = useMemo(() => {
    const source = userDisplayName || currentUser?.username || "";
    return source.charAt(0).toUpperCase();
  }, [currentUser?.username, userDisplayName]);

  const loginHref = useMemo(() => {
    const next = pathname || "/kb-chat";
    return `/login?next=${encodeURIComponent(next)}`;
  }, [pathname]);

  const redirectToLogin = useCallback(() => {
    router.replace(loginHref);
  }, [loginHref, router]);
  const handleLogout = useCallback(() => {
    clearAuthSession();
    router.replace("/login");
  }, [router]);

  const syncSession = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setCurrentUser(null);
      setAuthChecked(true);
      redirectToLogin();
      return;
    }

    const storedUser = getStoredUser();
    if (storedUser) {
      setCurrentUser(storedUser);
    }

    try {
      const user = await authApi.me();
      setAuthSession(token, user, false);
      setCurrentUser(user);
    } catch {
      clearAuthSession();
      setCurrentUser(null);
      redirectToLogin();
    } finally {
      setAuthChecked(true);
    }
  }, [redirectToLogin]);

  useEffect(() => {
    void syncSession();
  }, [syncSession]);

  useEffect(() => {
    const handleAuthChanged = () => {
      void syncSession();
    };

    window.addEventListener(AUTH_CHANGED_EVENT, handleAuthChanged);
    return () => {
      window.removeEventListener(AUTH_CHANGED_EVENT, handleAuthChanged);
    };
  }, [syncSession]);

  if (!authChecked || !currentUser) {
    return <SessionLoadingScreen />;
  }

  return (
    <div className="flex h-screen bg-slate-50">
      <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 p-6">
          <Link href="/">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-purple-700 text-white shadow-lg shadow-indigo-600/25">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900">知识库系统</h2>
                <p className="text-xs text-slate-500">协作工作台</p>
              </div>
            </div>
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto p-3">
          <div className="space-y-1">
            {navItems.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/" && pathname.startsWith(`${item.href}/`));

              return (
                <Link key={item.href} href={item.href} prefetch={true}>
                  <div
                    className={`group rounded-xl px-3 py-3 transition-all ${
                      isActive
                        ? "bg-gradient-to-r from-indigo-50 to-purple-50 shadow-sm ring-1 ring-indigo-100"
                        : "hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xl transition-transform group-hover:scale-110">{item.icon}</span>
                      <div className="min-w-0 flex-1">
                        <div className={`text-sm font-medium ${isActive ? "text-indigo-900" : "text-slate-700"}`}>
                          {item.title}
                        </div>
                        <div className={`text-xs ${isActive ? "text-indigo-600" : "text-slate-500"}`}>
                          {item.desc}
                        </div>
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </nav>

        <div className="shrink-0 border-t border-slate-200 p-4">
          <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-3 shadow-sm">
            <div className="flex items-start justify-between gap-2">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-sm font-semibold text-white shadow-md shadow-indigo-600/25">
                  {userInitial}
                </div>
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-slate-900">{userDisplayName}</div>
                  <div className="mt-0.5 truncate text-xs text-slate-500">{currentUser.email}</div>
                </div>
              </div>
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <button
                    type="button"
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/50"
                    aria-label="打开账号菜单"
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content
                    side="top"
                    align="end"
                    sideOffset={8}
                    className="z-50 min-w-[128px] rounded-xl border border-slate-200 bg-white p-1.5 text-sm shadow-xl"
                  >
                    <DropdownMenu.Item
                      onSelect={handleLogout}
                      className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2 text-red-600 outline-none transition-colors hover:bg-red-50 focus:bg-red-50"
                    >
                      <LogOut className="h-4 w-4" />
                      退出登录
                    </DropdownMenu.Item>
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            </div>
          </div>
        </div>
      </aside>

      <main className="relative flex min-h-0 flex-1 flex-col overflow-auto">
        <BackgroundTasksPanel />
        {children}
      </main>
    </div>
  );
}
