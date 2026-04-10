import Link from "next/link";

const cards = [
  {
    href: "/kb-chat",
    icon: "📚",
    title: "知识库问答",
    desc: "面向普通用户的知识检索与流式问答。",
  },
  {
    href: "/kb-curation",
    icon: "🧭",
    title: "知识库治理",
    desc: "面向管理员的多轮评估、修订建议与治理闭环。",
  },
  {
    href: "/revision",
    icon: "📝",
    title: "文档修订",
    desc: "根据建议生成文档补充与修订内容。",
  },
  {
    href: "/documents",
    icon: "🗂️",
    title: "文档库",
    desc: "统一管理集合、文档与索引状态。",
  },
  {
    href: "/prototype",
    icon: "🧩",
    title: "原型生成",
    desc: "将需求描述自动转成界面原型。",
  },
];

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <div className="container mx-auto px-4 py-16">
        <div className="mb-16 text-center">
          <h1 className="mb-4 text-5xl font-bold text-gray-900">企业知识库系统</h1>
          <p className="mx-auto max-w-2xl text-xl text-gray-600">
            选择一个工作场景，开始知识问答、知识治理或文档协作。
          </p>
        </div>

        <div className="mx-auto grid max-w-6xl gap-8 md:grid-cols-2 xl:grid-cols-3">
          {cards.map((card) => (
            <Link key={card.href} href={card.href}>
              <div className="cursor-pointer rounded-lg bg-white p-8 shadow-lg transition-shadow hover:shadow-xl">
                <div className="mb-4 text-4xl">{card.icon}</div>
                <h2 className="mb-3 text-2xl font-semibold">{card.title}</h2>
                <p className="text-gray-600">{card.desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
