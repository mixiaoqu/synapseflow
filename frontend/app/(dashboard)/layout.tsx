"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { LogOut, MoreHorizontal } from "lucide-react";

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
    <div className="flex h-screen">
      <aside className="flex w-64 shrink-0 flex-col bg-gray-900 text-white">
        <div className="border-b border-gray-800 p-6">
          <Link href="/">
            <h2 className="text-xl font-bold">SynapseFlow</h2>
          </Link>
          <p className="mt-1 text-xs text-gray-400">面向知识治理的协作工作台</p>
        </div>

        <nav className="flex-1 overflow-y-auto p-4">
          <div className="space-y-2">
            {navItems.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/" && pathname.startsWith(`${item.href}/`));

              return (
                <Link key={item.href} href={item.href}>
                  <div
                    className={`rounded-lg border-l-2 px-4 py-3 transition-colors ${
                      isActive
                        ? "border-blue-500 bg-gray-800"
                        : "border-transparent hover:bg-gray-800"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xl">{item.icon}</span>
                      <div>
                        <div className="font-medium">{item.title}</div>
                        <div className="text-xs text-gray-400">{item.desc}</div>
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </nav>

        <div className="shrink-0 border-t border-gray-800 p-4">
          <div className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-800 to-gray-900 p-3 shadow-[0_10px_25px_-15px_rgba(59,130,246,0.6)]">
            <div className="flex items-start justify-between gap-2">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-500/20 text-sm font-semibold text-blue-200 ring-1 ring-blue-400/30">
                  {userInitial}
                </div>
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-white">{userDisplayName}</div>
                  <div className="mt-0.5 truncate text-xs text-gray-400">{currentUser.email}</div>
                </div>
              </div>
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <button
                    type="button"
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-gray-400 transition-colors hover:bg-gray-700/80 hover:text-gray-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400/50"
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
                    className="z-50 min-w-[128px] rounded-lg border border-gray-700 bg-gray-900 p-1.5 text-sm shadow-xl"
                  >
                    <DropdownMenu.Item
                      onSelect={handleLogout}
                      className="flex cursor-pointer select-none items-center gap-2 rounded-md px-2.5 py-2 text-red-300 outline-none transition-colors hover:bg-red-500/15 hover:text-red-200 focus:bg-red-500/15 focus:text-red-200"
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

      <main className="flex min-h-0 flex-1 flex-col overflow-auto">{children}</main>
    </div>
  );
}
