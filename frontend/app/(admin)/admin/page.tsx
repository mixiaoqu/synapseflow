import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Bot,
  Building2,
  CheckSquare,
  ShieldAlert,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type CardItem = {
  href: string;
  title: string;
  desc: string;
  icon: LucideIcon;
  color: string;
};

type Section = {
  step: string;
  title: string;
  desc: string;
  items: CardItem[];
};

const sections: Section[] = [
  {
    step: "01",
    title: "构建知识资产",
    desc: "先把知识库和文档内容状态整理清楚，问答质量才有稳定输入。",
    items: [
      {
        href: "/admin/documents",
        title: "知识库管理",
        desc: "创建和维护知识库，上传资料，查看最近文档、索引状态与异常处理情况。",
        icon: BookOpen,
        color: "bg-blue-50 text-blue-600",
      },
      {
        href: "/admin/review",
        title: "审核发布",
        desc: "控制哪些内容可以进入前台问答链路，收口内容上线流程。",
        icon: CheckSquare,
        color: "bg-emerald-50 text-emerald-600",
      },
    ],
  },
  {
    step: "02",
    title: "配置问答运行",
    desc: "知识资产准备好之后，再配置助手和输入防线，决定前台问答如何工作。",
    items: [
      {
        href: "/admin/assistants",
        title: "助手管理",
        desc: "配置问答助手的人设、提示词、知识范围和可用状态。",
        icon: Bot,
        color: "bg-indigo-50 text-indigo-600",
      },
      {
        href: "/admin/sensitive-words",
        title: "敏感词管理",
        desc: "维护全局和团队词库，为问答输入建立统一拦截策略。",
        icon: ShieldAlert,
        color: "bg-red-50 text-red-500",
      },
    ],
  },
  {
    step: "03",
    title: "观察质量与治理权限",
    desc: "上线后持续看问答效果，并用团队与账号权限把运营边界控制住。",
    items: [
      {
        href: "/admin/qa-quality",
        title: "问答质检",
        desc: "查看用户问题、回答表现、反馈结果和知识缺口，定位改进点。",
        icon: BarChart3,
        color: "bg-amber-50 text-amber-600",
      },
      {
        href: "/admin/teams",
        title: "团队管理",
        desc: "维护团队信息、团队编码和团队之间的数据隔离边界。",
        icon: Building2,
        color: "bg-cyan-50 text-cyan-600",
      },
      {
        href: "/admin/users",
        title: "用户管理",
        desc: "创建账号、调整角色，并控制账户启停状态与后台访问权限。",
        icon: Users,
        color: "bg-fuchsia-50 text-fuchsia-600",
      },
    ],
  },
];

function CardGrid({ items }: { items: CardItem[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {items.map((card) => {
        const Icon = card.icon;
        return (
          <Link
            key={card.href}
            href={card.href}
            className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-slate-300 hover:shadow-md"
          >
            <div className="flex items-start gap-4">
              <div
                className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${card.color}`}
              >
                <Icon className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-base font-semibold text-slate-900 transition-colors group-hover:text-blue-600">
                    {card.title}
                  </h2>
                  <ArrowRight className="h-4 w-4 shrink-0 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-slate-400" />
                </div>
                <p className="mt-1.5 text-sm leading-6 text-slate-500">{card.desc}</p>
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}

function SectionBlock({ section }: { section: Section }) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-slate-50/70 p-6 sm:p-7">
      <div className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
            Step {section.step}
          </div>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
            {section.title}
          </h2>
        </div>
        <p className="max-w-2xl text-sm leading-7 text-slate-600">{section.desc}</p>
      </div>

      <div className="mt-6">
        <CardGrid items={section.items} />
      </div>
    </section>
  );
}

export default function AdminHomePage() {
  return (
    <div className="px-6 py-8 sm:px-8">
      <div className="max-w-6xl">
        <div className="max-w-3xl">
          <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
            Knowledge Ops
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            知识运营后台
          </h1>
          <p className="hidden">
            当前后台聚焦问答运营主链路。页面按“知识资产准备 → 问答配置 → 质量观察与权限治理”的顺序组织，避免重复入口并降低操作歧义。
          </p>
          <p className="mt-4 text-sm leading-7 text-slate-600">
            在这里查看知识库运营相关功能入口，并继续处理日常管理工作。
          </p>
        </div>

        <div className="mt-8 space-y-6">
          {sections.map((section) => (
            <SectionBlock key={section.step} section={section} />
          ))}
        </div>
      </div>
    </div>
  );
}
