"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/kb-chat", icon: "📚", title: "知识库问答", desc: "面向用户的单轮问答" },
  { href: "/kb-curation", icon: "🧭", title: "知识库治理", desc: "面向管理员的多轮评估" },
  { href: "/revision", icon: "📝", title: "文档修订", desc: "基于建议生成修订内容" },
  { href: "/documents", icon: "🗂️", title: "文档库", desc: "上传、检索与管理文档" },
  { href: "/prototype", icon: "🧩", title: "原型生成", desc: "从需求自动生成界面原型" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

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

        <div className="shrink-0 border-t border-gray-800 p-4 text-xs text-gray-400">
          <div>v0.1.0</div>
          <div className="mt-1">LangGraph Multi-Agent Workspace</div>
        </div>
      </aside>

      <main className="flex min-h-0 flex-1 flex-col overflow-auto">{children}</main>
    </div>
  );
}
