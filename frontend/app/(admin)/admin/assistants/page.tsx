"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Loader2,
  Pencil,
  Plus,
  Search,
  TestTube2,
  ToggleLeft,
  ToggleRight,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { useTeamScope } from "@/components/kb-chat/AskTeamScopeProvider";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  assistantsApi,
  type AssistantProfile,
  type AssistantSummary,
  type AssistantUpsertPayload,
} from "@/lib/api/assistants";
import { listKnowledgeBases } from "@/lib/api/knowledgeBases";
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
    knowledge_base_id: assistant.knowledge_base_id,
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
  if (form.knowledge_base_id == null) {
    throw new Error("请先选择知识库");
  }

  return {
    name: form.name.trim(),
    slug: form.slug.trim(),
    current_team_id: currentTeamId,
    knowledge_base_id: form.knowledge_base_id,
    category_id: form.category_id,
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

export default function AdminAssistantsPage() {
  const router = useRouter();
  const { teamId, selectedTeam } = useTeamScope();

  const [assistants, setAssistants] = useState<AssistantSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [activeFilter, setActiveFilter] = useState<
    "all" | "active" | "inactive"
  >("all");

  const filteredAssistants = useMemo(() => {
    const keyword = searchKeyword.trim().toLowerCase();

    return assistants.filter((assistant) => {
      const matchesKeyword =
        !keyword ||
        assistant.name.toLowerCase().includes(keyword) ||
        assistant.slug.toLowerCase().includes(keyword) ||
        (assistant.description ?? "").toLowerCase().includes(keyword) ||
        (assistant.knowledge_base_name ?? "").toLowerCase().includes(keyword);

      const matchesFilter =
        activeFilter === "all" ||
        (activeFilter === "active" && assistant.is_active) ||
        (activeFilter === "inactive" && !assistant.is_active);

      return matchesKeyword && matchesFilter;
    });
  }, [activeFilter, assistants, searchKeyword]);

  useEffect(() => {
    if (teamId == null) {
      setAssistants([]);
      setLoading(false);
      return;
    }

    void (async () => {
      setLoading(true);
      try {
        const [assistantItems] = await Promise.all([
          assistantsApi.list({ team_id: teamId }),
          listKnowledgeBases(teamId),
        ]);
        setAssistants(assistantItems);
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

  const openCreateDrawer = () => {
    router.push("/admin/assistants/new");
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
    router.push(`/admin/assistants/${assistantId}/test`);
  };

  const handleOpenEditPage = (assistantId: number) => {
    router.push(`/admin/assistants/${assistantId}/edit`);
  };

  return (
    <div className="min-h-screen bg-[#f8fafc] px-6 py-8 md:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="overflow-hidden rounded-[32px] border border-slate-200/80 bg-white shadow-sm">
          <div className="bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_28%),linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] p-6">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-3">
                <div className="text-xs font-medium uppercase tracking-[0.22em] text-emerald-600">
                  Assistants
                </div>
                <div>
                  <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
                    助手管理工作台
                  </h1>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                    为当前团队创建、筛选和维护助手，列表页聚焦概览，详情页继续做深度配置与测试。
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={openCreateDrawer}
                disabled={teamId == null}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-5 text-sm font-medium text-white shadow-lg shadow-emerald-500/20 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                新建助手
              </button>
            </div>
          </div>
        </section>

        <section className="rounded-[32px] border border-slate-200/80 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 border-b border-slate-100 pb-5 lg:flex-row lg:items-center lg:justify-between">
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
              <Badge className="h-10 rounded-2xl bg-slate-100 px-4 text-slate-600 hover:bg-slate-100">
                当前团队：{selectedTeam?.name ?? "未选择"}
              </Badge>
            </div>

            <div className="flex items-center gap-3">
              <select
                value={activeFilter}
                onChange={(event) =>
                  setActiveFilter(
                    event.target.value as "all" | "active" | "inactive",
                  )
                }
                className="h-11 min-w-[140px] rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
              >
                <option value="all">全部状态</option>
                <option value="active">已启用</option>
                <option value="inactive">已停用</option>
              </select>
            </div>
          </div>

          {loading ? (
            <div className="flex min-h-[320px] items-center justify-center text-sm text-slate-500">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              正在加载助手列表...
            </div>
          ) : filteredAssistants.length === 0 ? (
            <div className="flex min-h-[320px] flex-col items-center justify-center text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-slate-100 text-slate-400">
                <span className="text-lg font-semibold">A</span>
              </div>
              <h2 className="mt-4 text-lg font-semibold text-slate-900">
                没有匹配的助手
              </h2>
              <p className="mt-2 max-w-md text-sm text-slate-500">
                你可以调整搜索或筛选条件，也可以直接创建新的助手。
              </p>
            </div>
          ) : (
            <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
              {filteredAssistants.map((assistant) => (
                <Card
                  key={assistant.id}
                  onClick={() => handleOpenEditPage(assistant.id)}
                  className="group relative flex cursor-pointer flex-col overflow-hidden rounded-[28px] border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#fbfdff_100%)] transition-all duration-200 hover:-translate-y-1 hover:border-emerald-300/60 hover:shadow-xl"
                >
                  <CardHeader className="space-y-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <div
                          className={cn(
                            "flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border text-lg font-semibold shadow-sm",
                            assistant.is_active
                              ? "border-emerald-200 bg-emerald-50 text-emerald-600"
                              : "border-slate-200 bg-slate-100 text-slate-500",
                          )}
                        >
                          {getAssistantInitial(assistant.name)}
                        </div>
                        <div className="min-w-0">
                          <CardTitle className="truncate text-lg font-semibold text-slate-900">
                            {assistant.name}
                          </CardTitle>
                          <p className="mt-1 truncate text-xs uppercase tracking-[0.18em] text-slate-400">
                            {assistant.slug}
                          </p>
                        </div>
                      </div>

                      <Badge
                        className={cn(
                          "shrink-0 rounded-full px-2.5 py-1 text-xs",
                          assistant.is_active
                            ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-50"
                            : "bg-slate-100 text-slate-500 hover:bg-slate-100",
                        )}
                      >
                        {assistant.is_active ? "Active" : "Draft"}
                      </Badge>
                    </div>
                  </CardHeader>

                  <CardContent className="flex flex-1 flex-col justify-between gap-5">
                    <div>
                      <p className="mt-1 h-10 line-clamp-2 text-sm leading-5 text-slate-500">
                        {assistant.description ||
                          assistant.welcome_message ||
                          "暂无描述信息"}
                      </p>
                    </div>

                    <div className="space-y-4">
                      <div className="flex flex-wrap gap-2">
                        <Badge
                          variant="secondary"
                          className="rounded-full bg-blue-50 text-xs text-blue-700 hover:bg-blue-50"
                        >
                          {assistant.knowledge_base_name || "未绑定知识库"}
                        </Badge>
                        {assistant.category_name ? (
                          <Badge
                            variant="secondary"
                            className="rounded-full bg-slate-100 text-xs text-slate-600 hover:bg-slate-100"
                          >
                            {assistant.category_name}
                          </Badge>
                        ) : null}
                      </div>

                      <div className="flex items-center justify-between border-t border-slate-100 pt-4 text-xs text-slate-400">
                        <span>
                          更新于 {formatDateTime(assistant.updated_at)}
                        </span>
                        <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleOpenEditPage(assistant.id);
                            }}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                            title="编辑"
                          >
                            <Pencil className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleTest(assistant.id);
                            }}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-emerald-50 hover:text-emerald-600"
                            title="测试"
                          >
                            <TestTube2 className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              void handleToggleActive(
                                assistant.id,
                                !assistant.is_active,
                              );
                            }}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                            title={assistant.is_active ? "停用" : "启用"}
                          >
                            {assistant.is_active ? (
                              <ToggleRight className="h-4 w-4 text-emerald-500" />
                            ) : (
                              <ToggleLeft className="h-4 w-4" />
                            )}
                          </button>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              void handleQuickDelete(assistant.id);
                            }}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
                            title="删除"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
