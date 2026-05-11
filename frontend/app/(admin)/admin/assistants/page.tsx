"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AssistantTestChat } from "@/components/admin/assistants/AssistantTestChat";
import {
  AdminPage,
  AdminPageContent,
  AdminPageHeader,
} from "@/components/admin/layout/AdminPage";
import {
  Activity,
  BarChart3,
  Brain,
  Copy,
  Database,
  FileText,
  Loader2,
  MoreHorizontal,
  Power,
  PowerOff,
  Plus,
  Search,
  Settings,
  Sparkles,
  Target,
  TestTube2,
  ThumbsUp,
  Trash2,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  assistantsApi,
  type AssistantModelOption,
  type AssistantProfile,
  type AssistantSummary,
  type AssistantUpsertPayload,
} from "@/lib/api/assistants";
import { cn } from "@/lib/utils";

interface AssistantFormState {
  name: string;
  slug: string;
  knowledge_base_id: number | null;
  category_id: number | null;
  description: string;
  welcome_message: string;
  placeholder_text: string;
  persona_prompt: string;
  rule_template: string;
  suggested_prompts_text: string;
  is_active: boolean;
  sort_order: number;
}

function createEmptyForm(sortOrder = 0): AssistantFormState {
  return {
    name: "",
    slug: "",
    knowledge_base_id: null,
    category_id: null,
    description: "",
    welcome_message: "",
    placeholder_text: "",
    persona_prompt: "",
    rule_template: "",
    suggested_prompts_text: "",
    is_active: true,
    sort_order: sortOrder,
  };
}

function toFormState(assistant: AssistantProfile): AssistantFormState {
  return {
    name: assistant.name,
    slug: assistant.slug,
    knowledge_base_id: assistant.knowledge_base_id ?? null,
    category_id: assistant.category_id ?? null,
    description: assistant.description ?? "",
    welcome_message: assistant.welcome_message ?? "",
    placeholder_text: assistant.placeholder_text ?? "",
    persona_prompt: assistant.persona_prompt ?? "",
    rule_template: assistant.rule_template ?? "",
    suggested_prompts_text: assistant.suggested_prompts.join("\n"),
    is_active: assistant.is_active,
    sort_order: assistant.sort_order,
  };
}

function toPayload(
  form: AssistantFormState,
  currentTeamId: number,
): AssistantUpsertPayload {
  return {
    name: form.name.trim(),
    slug: form.slug.trim(),
    current_team_id: currentTeamId,
    description: form.description.trim() || null,
    welcome_message: form.welcome_message.trim() || null,
    placeholder_text: form.placeholder_text.trim() || null,
    persona_prompt: form.persona_prompt.trim() || null,
    rule_template: form.rule_template.trim() || null,
    suggested_prompts: form.suggested_prompts_text
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean),
    is_active: form.is_active,
    sort_order: Number.isFinite(form.sort_order) ? form.sort_order : 0,
  };
}

function formatDateTime(value?: string | null): string {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function getAssistantInitial(name: string): string {
  const trimmed = name.trim();
  return trimmed ? trimmed.slice(0, 1).toUpperCase() : "A";
}

type AssistantStatusFilter = "all" | "active" | "inactive";
type AssistantSortMode = "sort_order" | "activity" | "updated" | "created";

interface AssistantMockMetrics {
  todayCalls: number;
  weekCalls: number;
  hitRate: number;
  feedbackRate: number;
}

const AVATAR_PRESETS = [
  {
    icon: Sparkles,
    className: "from-emerald-400 via-teal-500 to-cyan-500 text-white",
  },
  {
    icon: Brain,
    className: "from-blue-400 via-indigo-500 to-violet-500 text-white",
  },
  {
    icon: Target,
    className: "from-rose-400 via-pink-500 to-orange-400 text-white",
  },
  {
    icon: Database,
    className: "from-amber-300 via-lime-400 to-emerald-500 text-slate-900",
  },
  {
    icon: Activity,
    className: "from-sky-300 via-cyan-400 to-teal-500 text-slate-900",
  },
];

const ASSISTANT_TEMPLATES = [
  {
    id: "it-helpdesk",
    title: "企业 IT 帮助台助手",
    desc: "解答员工常见的 IT 设备、网络、账号和软件问题。",
    category: "内部效能",
  },
  {
    id: "legal-review",
    title: "法务合同审查助手",
    desc: "辅助审查标准合同条款，提示常见风险和补充材料。",
    category: "法务合规",
  },
  {
    id: "onboarding",
    title: "新员工入职向导",
    desc: "引导新员工了解报到流程、福利政策和企业文化。",
    category: "员工体验",
  },
  {
    id: "general-qa",
    title: "通用知识问答助手",
    desc: "面向团队知识库做统一检索、总结和问答。",
    category: "知识问答",
  },
];

function hashAssistant(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function getMockMetrics(assistant: AssistantSummary): AssistantMockMetrics {
  const seed = hashAssistant(`${assistant.id}:${assistant.slug}:${assistant.updated_at}`);
  return {
    todayCalls: 18 + (seed % 186),
    weekCalls: 140 + (seed % 1280),
    hitRate: 72 + (seed % 24),
    feedbackRate: 68 + ((seed >> 3) % 28),
  };
}

function getAvatarPreset(assistant: AssistantSummary) {
  const seed = hashAssistant(`${assistant.id}:${assistant.name}`);
  return AVATAR_PRESETS[seed % AVATAR_PRESETS.length];
}

function getAssistantModelMeta(
  assistant: AssistantSummary,
  modelOptions: AssistantModelOption[],
) {
  if (!assistant.llm_model_key) {
    return {
      label: "系统默认",
      className: "bg-slate-100 text-slate-600 hover:bg-slate-100",
      title: "未单独指定模型，使用系统默认 generation 映射",
    };
  }

  const matched = modelOptions.find((item) => item.key === assistant.llm_model_key);
  if (matched) {
    return {
      label: matched.name,
      className: "bg-violet-50 text-violet-700 hover:bg-violet-50",
      title: `${matched.provider} / ${matched.model}`,
    };
  }

  return {
    label: assistant.llm_model_key,
    className: "bg-amber-50 text-amber-700 hover:bg-amber-50",
    title: "该模型配置当前未在可选列表中返回",
  };
}

export default function AdminAssistantsPage() {
  const router = useRouter();
  const { teamId, selectedTeam } = useTeamScope();

  const [assistants, setAssistants] = useState<AssistantSummary[]>([]);
  const [modelOptions, setModelOptions] = useState<AssistantModelOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [activeFilter, setActiveFilter] = useState<AssistantStatusFilter>("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sortMode, setSortMode] = useState<AssistantSortMode>("sort_order");
  const [testingAssistantId, setTestingAssistantId] = useState<number | null>(null);

  const categoryOptions = useMemo(() => {
    const counts = new Map<string, number>();
    assistants.forEach((assistant) => {
      const category = assistant.category_name?.trim() || "未分类";
      counts.set(category, (counts.get(category) ?? 0) + 1);
    });
    return Array.from(counts.entries()).sort(([left], [right]) =>
      left.localeCompare(right, "zh-CN"),
    );
  }, [assistants]);

  const visibleAssistants = useMemo(() => {
    const keyword = searchKeyword.trim().toLowerCase();

    return assistants
      .filter((assistant) => {
        const matchesKeyword =
          !keyword ||
          assistant.name.toLowerCase().includes(keyword) ||
          assistant.slug.toLowerCase().includes(keyword) ||
          (assistant.description ?? "").toLowerCase().includes(keyword) ||
          (assistant.knowledge_base_name ?? "").toLowerCase().includes(keyword);

        const matchesStatus =
          activeFilter === "all" ||
          (activeFilter === "active" && assistant.is_active) ||
          (activeFilter === "inactive" && !assistant.is_active);

        const categoryName = assistant.category_name?.trim() || "未分类";
        const matchesCategory =
          categoryFilter === "all" || categoryFilter === categoryName;

        return matchesKeyword && matchesStatus && matchesCategory;
      })
      .sort((left, right) => {
        if (sortMode === "activity") {
          return getMockMetrics(right).weekCalls - getMockMetrics(left).weekCalls;
        }
        if (sortMode === "updated") {
          return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
        }
        if (sortMode === "created") {
          return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
        }
        return left.sort_order - right.sort_order || left.id - right.id;
      });
  }, [activeFilter, assistants, categoryFilter, searchKeyword, sortMode]);

  const boardMetrics = useMemo(() => {
    const total = assistants.length;
    const active = assistants.filter((assistant) => assistant.is_active).length;
    const calls = assistants.reduce(
      (sum, assistant) => sum + getMockMetrics(assistant).weekCalls,
      0,
    );
    const feedback =
      total === 0
        ? 0
        : Math.round(
            assistants.reduce(
              (sum, assistant) => sum + getMockMetrics(assistant).feedbackRate,
              0,
            ) / total,
          );

    return {
      calls,
      activeRate: total === 0 ? 0 : Math.round((active / total) * 100),
      feedback,
      knowledgeBases: new Set(
        assistants.map((assistant) => assistant.knowledge_base_id).filter(Boolean),
      ).size,
    };
  }, [assistants]);

  useEffect(() => {
    if (teamId == null) {
      setAssistants([]);
      setLoading(false);
      return;
    }

    void (async () => {
      setLoading(true);
      try {
        const [assistantItems, modelOptionsResponse] = await Promise.all([
          assistantsApi.list({ team_id: teamId }),
          assistantsApi.listModelOptions(),
        ]);
        setAssistants(assistantItems);
        setModelOptions(modelOptionsResponse.items);
      } catch (error) {
        toast.error(
          error instanceof Error ? error.message : "加载助手列表失败",
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [teamId]);

  const reloadAssistants = async () => {
    if (teamId == null) return;
    setAssistants(await assistantsApi.list({ team_id: teamId }));
  };

  const openCreateDrawer = (templateId?: string) => {
    router.push(
      templateId
        ? `/admin/assistants/new?template=${encodeURIComponent(templateId)}`
        : "/admin/assistants/new",
    );
  };

  const handleToggleActive = async (
    assistantId: number,
    nextActive: boolean,
  ) => {
    if (teamId == null) return;

    try {
      const detail = await assistantsApi.get(assistantId);
      const payload = toPayload(
        { ...toFormState(detail), is_active: nextActive },
        teamId,
      );
      await assistantsApi.update(assistantId, payload);
      await reloadAssistants();
      toast.success(nextActive ? "助手已启用" : "助手已停用");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "切换状态失败");
    }
  };

  const handleQuickDelete = async (assistantId: number) => {
    if (!window.confirm("确认删除这个助手吗？")) {
      return;
    }

    try {
      await assistantsApi.delete(assistantId, { force: true });
      toast.success("助手已删除");
      await reloadAssistants();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除助手失败");
    }
  };

  const handleTest = (assistantId: number) => {
    setTestingAssistantId(assistantId);
  };

  const handleOpenEditPage = (assistantId: number) => {
    router.push(`/admin/assistants/${assistantId}/edit`);
  };

  const handleDuplicate = async (assistantId: number) => {
    if (teamId == null) return;

    try {
      const detail = await assistantsApi.get(assistantId);
      const created = await assistantsApi.create({
        ...toPayload(toFormState(detail), teamId),
        name: `${detail.name} 副本`,
        slug: `${detail.slug}-copy-${Date.now().toString(36)}`,
        sort_order: detail.sort_order + 1,
        is_active: false,
      });
      toast.success("助手副本已创建");
      router.push(`/admin/assistants/${created.id}/edit`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "复制助手失败");
    }
  };

  return (
    <>
      <AdminPage>
        <AdminPageHeader
          eyebrow="AI Workforce"
          title="我的助手团队"
          description="管理连接不同知识库、承担不同任务的数字员工，快速配置、测试和调度它们的工作状态。"
          actions={
            <button
              type="button"
              onClick={() => openCreateDrawer()}
              disabled={teamId == null}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              新建助手
            </button>
          }
        />

        <div className="inline-flex h-9 w-fit items-center gap-2 rounded-full border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 shadow-sm">
          <Users className="h-3.5 w-3.5" />
          当前工作区：{selectedTeam?.name ?? "未选择团队"}
        </div>

        <div className="grid gap-3 md:grid-cols-4">
              {[
                {
                  label: "本周总调用",
                  value: boardMetrics.calls.toLocaleString("zh-CN"),
                  hint: "模拟统计",
                  icon: Activity,
                },
                {
                  label: "活跃助手占比",
                  value: `${boardMetrics.activeRate}%`,
                  hint: `${assistants.filter((assistant) => assistant.is_active).length}/${assistants.length || 0} 在线`,
                  icon: BarChart3,
                },
                {
                  label: "平均点赞率",
                  value: `${boardMetrics.feedback}%`,
                  hint: "模拟反馈",
                  icon: ThumbsUp,
                },
                {
                  label: "连接知识库",
                  value: String(boardMetrics.knowledgeBases),
                  hint: "已绑定记忆源",
                  icon: Database,
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="rounded-2xl border border-slate-200/80 bg-white/80 p-4 shadow-sm backdrop-blur"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-500">{item.label}</span>
                    <item.icon className="h-4 w-4 text-emerald-600" />
                  </div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                    {item.value}
                  </div>
                  <div className="mt-1 text-xs text-slate-400">{item.hint}</div>
                </div>
              ))}
        </div>

        <AdminPageContent className="p-5">
          <div className="flex flex-col gap-4 border-b border-slate-100 pb-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="relative w-full max-w-md">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                  value={searchKeyword}
                  onChange={(event) => setSearchKeyword(event.target.value)}
                  placeholder="搜索助手名称、标识或知识库..."
                  className="h-11 rounded-2xl border-slate-200 bg-slate-50 pl-10"
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={activeFilter}
                  onChange={(event) =>
                    setActiveFilter(event.target.value as AssistantStatusFilter)
                  }
                  className="h-11 min-w-[132px] rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
                >
                  <option value="all">全部状态</option>
                  <option value="active">已发布</option>
                  <option value="inactive">休眠中</option>
                </select>
                <select
                  value={sortMode}
                  onChange={(event) =>
                    setSortMode(event.target.value as AssistantSortMode)
                  }
                  className="h-11 min-w-[150px] rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
                >
                  <option value="sort_order">按展示顺序</option>
                  <option value="activity">按活跃度</option>
                  <option value="updated">按最近更新</option>
                  <option value="created">按创建时间</option>
                </select>
              </div>
            </div>

            <div className="flex gap-2 overflow-x-auto pb-1">
              <button
                type="button"
                onClick={() => setCategoryFilter("all")}
                className={cn(
                  "shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                  categoryFilter === "all"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700",
                )}
              >
                全部分类 {assistants.length}
              </button>
              {categoryOptions.map(([category, count]) => (
                <button
                  key={category}
                  type="button"
                  onClick={() => setCategoryFilter(category)}
                  className={cn(
                    "shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                    categoryFilter === category
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700",
                  )}
                >
                  {category} {count}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="flex min-h-[320px] items-center justify-center text-sm text-slate-500">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              正在加载助手列表...
            </div>
          ) : visibleAssistants.length === 0 &&
            searchKeyword === "" &&
            activeFilter === "all" &&
            categoryFilter === "all" ? (
            <div className="mt-6">
              <div className="flex flex-col items-center justify-center text-center py-12">
                <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-slate-100 text-slate-400">
                  <span className="text-lg font-semibold">A</span>
                </div>
                <h2 className="mt-4 text-lg font-semibold text-slate-900">
                  还没有任何助手
                </h2>
                <p className="mt-2 max-w-md text-sm text-slate-500 mb-6">
                  你可以从模板开始创建，或直接新建一个空白助手。
                </p>
                <button
                  type="button"
                  onClick={() => openCreateDrawer()}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-emerald-500 px-5 text-sm font-medium text-white transition-colors hover:bg-emerald-600"
                >
                  <Plus className="h-4 w-4" />
                  立即创建助手
                </button>
              </div>
              <div className="mt-8">
                <h3 className="text-sm font-medium text-slate-900 mb-4">或者从模板开始：</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {ASSISTANT_TEMPLATES.map((tpl) => (
                    <div key={tpl.id} className="rounded-2xl border border-slate-200 bg-white p-5 transition-all hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-md cursor-pointer" onClick={() => openCreateDrawer(tpl.id)}>
                      <div className="flex items-center gap-3 mb-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-slate-700 font-medium">
                          {getAssistantInitial(tpl.title)}
                        </div>
                        <h4 className="font-medium text-slate-900">{tpl.title}</h4>
                      </div>
                      <div className="mb-2 text-[11px] font-medium text-emerald-600">{tpl.category}</div>
                      <p className="text-xs text-slate-500 line-clamp-2">{tpl.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : visibleAssistants.length === 0 ? (
            <div className="flex min-h-[320px] flex-col items-center justify-center text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-slate-100 text-slate-400">
                <Search className="h-6 w-6" />
              </div>
              <h2 className="mt-4 text-lg font-semibold text-slate-900">
                没有匹配的助手
              </h2>
              <p className="mt-2 max-w-md text-sm text-slate-500 mb-6">
                你可以调整搜索或筛选条件。
              </p>
              <button
                type="button"
                onClick={() => {
                  setSearchKeyword("");
                  setActiveFilter("all");
                  setCategoryFilter("all");
                }}
                className="inline-flex h-10 items-center justify-center rounded-xl border border-slate-200 bg-white px-5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
              >
                清除所有筛选
              </button>
            </div>
          ) : (
            <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
              {visibleAssistants.map((assistant) => {
                const metrics = getMockMetrics(assistant);
                const avatar = getAvatarPreset(assistant);
                const AvatarIcon = avatar.icon;
                const modelMeta = getAssistantModelMeta(assistant, modelOptions);

                return (
                  <Card
                    key={assistant.id}
                    onClick={() => handleOpenEditPage(assistant.id)}
                    className={cn(
                      "group relative flex cursor-pointer flex-col overflow-hidden rounded-[28px] border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#fbfdff_100%)] shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-emerald-300/60 hover:shadow-xl",
                      !assistant.is_active &&
                        "opacity-75 saturate-50 after:pointer-events-none after:absolute after:inset-0 after:bg-white/35",
                    )}
                  >
                    <CardHeader className="space-y-4 pb-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-3">
                          <Avatar
                            className={cn(
                              "h-14 w-14 shrink-0 rounded-2xl border shadow-sm",
                              assistant.is_active ? "border-emerald-200" : "border-slate-200",
                            )}
                          >
                            <AvatarFallback
                              className={cn(
                                "rounded-2xl bg-gradient-to-br",
                                avatar.className,
                              )}
                            >
                              <AvatarIcon className="h-6 w-6" />
                            </AvatarFallback>
                          </Avatar>
                          <div className="min-w-0">
                            <CardTitle
                              className={cn(
                                "truncate text-lg font-semibold text-slate-900",
                                !assistant.is_active && "text-slate-500",
                              )}
                            >
                              {assistant.name}
                            </CardTitle>
                            <p className="mt-1 truncate text-xs uppercase tracking-[0.18em] text-slate-400">
                              {assistant.slug}
                            </p>
                          </div>
                        </div>

                        <div className="flex shrink-0 items-center gap-1.5 rounded-full bg-white px-2.5 py-1 text-xs text-slate-500 shadow-sm ring-1 ring-slate-200">
                          <span
                            className={cn(
                              "h-2 w-2 rounded-full",
                              assistant.is_active
                                ? "animate-pulse bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.12)]"
                                : "bg-slate-300",
                            )}
                          />
                          {assistant.is_active ? "已发布" : "休眠"}
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent className="flex flex-1 flex-col justify-between gap-5">
                      <p className="h-[60px] line-clamp-3 text-sm leading-5 text-slate-500">
                        {assistant.description ||
                          assistant.welcome_message ||
                          "这个数字员工还没有填写职责说明。"}
                      </p>

                      <div className="space-y-3">
                        <div className="grid gap-2">
                          <div
                            className={cn(
                              "flex items-center gap-2 rounded-2xl border px-3 py-2 text-xs",
                              assistant.knowledge_base_name
                                ? "border-blue-100 bg-blue-50 text-blue-700"
                                : "border-amber-200 bg-amber-50 text-amber-700 border-dashed",
                            )}
                          >
                            <Brain className="h-3.5 w-3.5" />
                            <span className="truncate">
                              知识库：{assistant.knowledge_base_name || "未绑定知识库"}
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <Badge
                              variant="secondary"
                              className="gap-1 rounded-full bg-slate-100 text-xs text-slate-600 hover:bg-slate-100"
                            >
                              <Target className="h-3 w-3" />
                              {assistant.category_name || "未分类"}
                            </Badge>
                            <Badge
                              variant="secondary"
                              className={cn(
                                "gap-1 rounded-full text-xs",
                                modelMeta.className,
                              )}
                              title={modelMeta.title}
                            >
                              <Sparkles className="h-3 w-3" />
                              {modelMeta.label}
                            </Badge>
                          </div>
                        </div>

                        <div className="flex items-center justify-between border-t border-slate-100 pt-4">
                          <div className="space-y-1 text-xs text-slate-500">
                            <div className="flex items-center gap-2">
                              <Activity className="h-3.5 w-3.5 text-emerald-600" />
                              今日调用：{metrics.todayCalls} 次
                            </div>
                            <div className="flex items-center gap-2">
                              <BarChart3 className="h-3.5 w-3.5 text-blue-600" />
                              命中率：{metrics.hitRate}%
                            </div>
                          </div>

                          <div className="relative z-10 flex items-center gap-1">
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                handleOpenEditPage(assistant.id);
                              }}
                              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                              title="配置"
                            >
                              <Settings className="h-4 w-4" />
                            </button>
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                handleTest(assistant.id);
                              }}
                              className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500 text-white shadow-lg shadow-emerald-500/20 transition-all hover:-translate-y-0.5 hover:bg-emerald-600 hover:shadow-emerald-500/35"
                              title="测试"
                            >
                              <TestTube2 className="h-4 w-4" />
                            </button>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <button
                                  type="button"
                                  onClick={(event) => event.stopPropagation()}
                                  className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                                  title="更多"
                                >
                                  <MoreHorizontal className="h-4 w-4" />
                                </button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-44">
                                <DropdownMenuLabel>更多操作</DropdownMenuLabel>
                                <DropdownMenuItem
                                  onSelect={() =>
                                    router.push(`/admin/qa-quality?assistant_id=${assistant.id}`)
                                  }
                                >
                                  <FileText className="h-4 w-4" />
                                  查看日志
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onSelect={() => void handleDuplicate(assistant.id)}
                                >
                                  <Copy className="h-4 w-4" />
                                  复制/克隆
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  onSelect={() =>
                                    void handleToggleActive(
                                      assistant.id,
                                      !assistant.is_active,
                                    )
                                  }
                                >
                                  {assistant.is_active ? (
                                    <PowerOff className="h-4 w-4" />
                                  ) : (
                                    <Power className="h-4 w-4" />
                                  )}
                                  {assistant.is_active ? "停用" : "启用"}
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  className="text-red-600 focus:text-red-600"
                                  onSelect={() => void handleQuickDelete(assistant.id)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                  删除
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </AdminPageContent>
      </AdminPage>
      <Sheet
        open={testingAssistantId != null}
        onOpenChange={(open) => {
          if (!open) setTestingAssistantId(null);
        }}
      >
        <SheetContent
          side="right"
          className="flex w-full max-w-full flex-col overflow-hidden p-0 sm:max-w-2xl lg:max-w-3xl"
        >
          <SheetHeader className="border-b border-slate-200 bg-white px-5 py-4 pr-12">
            <SheetTitle>测试助手</SheetTitle>
          </SheetHeader>
          <div className="min-h-0 flex-1 overflow-hidden">
            {testingAssistantId != null ? (
              <AssistantTestChat assistantId={testingAssistantId} />
            ) : null}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
