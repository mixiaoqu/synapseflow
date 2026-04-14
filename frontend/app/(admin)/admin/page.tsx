import Link from "next/link";
import {
  Database,
  BookOpen,
  CheckSquare,
  BarChart3,
  ShieldAlert,
  Building2,
  Users,
} from "lucide-react";

const cards = [
  {
    href: "/admin/documents",
    title: "文档管理",
    desc: "上传资料、维护内容、查看索引状态与失败重试。",
    icon: Database,
    color: "bg-blue-50 text-blue-600",
  },
  {
    href: "/admin/knowledge-bases",
    title: "知识库管理",
    desc: "统一管理知识库范围、文档规模和内容承载情况。",
    icon: BookOpen,
    color: "bg-violet-50 text-violet-600",
  },
  {
    href: "/admin/review",
    title: "审核发布",
    desc: "处理内容状态流转，控制哪些知识可以被前台问答命中。",
    icon: CheckSquare,
    color: "bg-emerald-50 text-emerald-600",
  },
  {
    href: "/admin/qa-quality",
    title: "问答质检",
    desc: "查看用户问题、回答状态、反馈和知识缺口。",
    icon: BarChart3,
    color: "bg-amber-50 text-amber-600",
  },
  {
    href: "/admin/sensitive-words",
    title: "敏感词管理",
    desc: "维护全局和团队词库，并配置问答输入的敏感词拦截策略。",
    icon: ShieldAlert,
    color: "bg-red-50 text-red-500",
  },
  {
    href: "/admin/teams",
    title: "团队管理",
    desc: "维护组织团队、团队编码以及团队成员分工。",
    icon: Building2,
    color: "bg-cyan-50 text-cyan-600",
  },
  {
    href: "/admin/users",
    title: "用户管理",
    desc: "创建账号、调整角色并控制账号启停状态。",
    icon: Users,
    color: "bg-fuchsia-50 text-fuchsia-600",
  },
];

export default function AdminHomePage() {
  return (
    <div className="px-6 py-8 sm:px-8">
      <div className="max-w-5xl">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          知识运营后台
        </h1>
        <p className="mt-2 text-sm leading-7 text-slate-600">
          统一管理知识内容、审核发布流程，以及面向终端用户的问答质量。
        </p>

        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {cards.map((card) => {
            const Icon = card.icon;
            return (
              <Link
                key={card.href}
                href={card.href}
                className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-slate-300 hover:shadow-md"
              >
                <div className="flex items-start gap-4">
                  <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${card.color}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-base font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">
                      {card.title}
                    </h2>
                    <p className="mt-1.5 text-sm leading-6 text-slate-500">
                      {card.desc}
                    </p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
