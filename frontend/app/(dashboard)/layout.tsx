'use client';

/**
 * Dashboard布局
 */
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const navItems = [
  { href: '/kb-qa', icon: '📚', title: '知识库问答', desc: '单轮流式' },
  { href: '/qa', icon: '💬', title: '迭代问答', desc: '多轮评估' },
  { href: '/revision', icon: '📝', title: '文档修订', desc: '用户建议驱动' },
  { href: '/documents', icon: '📁', title: '文档库', desc: '上传与管理' },
  { href: '/prototype', icon: '🎨', title: '文档转原型', desc: '自动生成UI' },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen">
      {/* 左侧导航栏 */}
      <aside className="w-64 bg-gray-900 text-white flex flex-col shrink-0">
        <div className="p-6 border-b border-gray-800">
          <Link href="/">
            <h2 className="text-xl font-bold">SynapseFlow</h2>
          </Link>
          <p className="text-xs text-gray-400 mt-1">智能体协作系统</p>
        </div>

        <nav className="flex-1 p-4 overflow-y-auto">
          <div className="space-y-2">
            {navItems.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== '/' && pathname.startsWith(item.href + '/'));
              return (
                <Link key={item.href} href={item.href}>
                  <div
                    className={`px-4 py-3 rounded-lg transition-colors border-l-2 ${
                      isActive
                        ? 'bg-gray-800 border-blue-500'
                        : 'border-transparent hover:bg-gray-800'
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

        <div className="p-4 border-t border-gray-800 text-xs text-gray-400 shrink-0">
          <div>v0.1.0</div>
          <div className="mt-1">LangGraph Multi-Agent</div>
        </div>
      </aside>

      {/* 主内容区 */}
      <main className="flex min-h-0 flex-1 flex-col overflow-auto">
        {children}
      </main>
    </div>
  );
}
