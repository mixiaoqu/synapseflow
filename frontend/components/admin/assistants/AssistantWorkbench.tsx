"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Bot,
  Brain,
  CheckCircle2,
  ChevronDown,
  Database,
  Loader2,
  MessageSquareText,
  Power,
  Save,
  SlidersHorizontal,
  Sparkles,
  Wand2,
} from "lucide-react";
import { toast } from "sonner";

import {
  AssistantTestChat,
  type AssistantTestDraft,
} from "@/components/admin/assistants/AssistantTestChat";
import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  assistantsApi,
  type AssistantModelOption,
  type AssistantProfile,
  type AssistantUpsertPayload,
} from "@/lib/api/assistants";
import {
  listDocumentCategories,
  type DocumentCategory,
} from "@/lib/api/documentCategories";
import {
  listKnowledgeBases,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import { cn } from "@/lib/utils";

export interface AssistantWorkbenchProps {
  mode: "create" | "edit";
  assistantId?: number | null;
}

interface AssistantFormState {
  name: string;
  slug: string;
  description: string;
  welcome_message: string;
  placeholder_text: string;
  llm_model_key: string | null;
  persona_prompt: string;
  rule_template: string;
  suggested_prompts_text: string;
  is_active: boolean;
  knowledge_base_id: number | null;
  category_id: number | null;
  sort_order: number;
}

type SectionKey = "basic" | "behavior" | "experience";

const TEMPLATE_PRESETS: Record<
  string,
  Pick<
    AssistantFormState,
    | "name"
    | "slug"
    | "description"
    | "welcome_message"
    | "placeholder_text"
    | "persona_prompt"
    | "rule_template"
    | "suggested_prompts_text"
  > & { title: string }
> = {
  "it-helpdesk": {
    title: "企业 IT 帮助台",
    name: "企业 IT 帮助台助手",
    slug: "it-helpdesk",
    description: "解答员工常见的设备、网络、账号和办公软件问题。",
    welcome_message: "你好，我可以协助你排查办公设备、网络、账号和常用软件问题。",
    placeholder_text: "描述你遇到的 IT 问题...",
    persona_prompt:
      "你是一名企业 IT 帮助台数字员工。回答要清晰、分步骤，信息不足时先询问设备、系统、网络环境和错误提示。",
    rule_template:
      "优先基于知识库回答。涉及账号权限、数据安全或设备维修时，引导用户提交 IT 工单并补充必要信息。",
    suggested_prompts_text: [
      "VPN 连不上应该怎么排查？",
      "公司邮箱无法登录怎么办？",
      "新电脑需要安装哪些基础软件？",
    ].join("\n"),
  },
  "legal-review": {
    title: "法务合同审查",
    name: "法务合同审查助手",
    slug: "legal-review",
    description: "辅助审查标准合同条款，提示常见风险和需要人工确认的事项。",
    welcome_message: "你好，我可以帮你初步梳理合同条款风险和需要法务确认的问题。",
    placeholder_text: "输入合同条款或审查问题...",
    persona_prompt:
      "你是一名法务合同审查数字员工。回答要谨慎、结构化，区分事实、风险提示和需要人工法务确认的事项。",
    rule_template:
      "不得给出最终法律结论。遇到高风险条款、金额、期限、违约责任、知识产权和数据合规问题时，提示升级给法务负责人。",
    suggested_prompts_text: [
      "这个保密条款有哪些风险？",
      "供应商合同付款条款需要注意什么？",
      "违约责任条款如何审查？",
    ].join("\n"),
  },
  onboarding: {
    title: "新员工入职向导",
    name: "新员工入职向导",
    slug: "onboarding-guide",
    description: "引导新员工了解报到流程、福利政策和常见行政事项。",
    welcome_message: "欢迎加入团队，我可以帮你了解入职流程、福利和常见行政事项。",
    placeholder_text: "询问入职流程、福利或行政问题...",
    persona_prompt:
      "你是一名新员工入职向导。语气友好、准确，优先给出可执行步骤和相关材料位置。",
    rule_template:
      "优先基于知识库回答。涉及个人薪酬、合同、社保等敏感问题时，引导用户联系 HR 专员。",
    suggested_prompts_text: [
      "入职第一天需要完成哪些事项？",
      "如何申请办公设备？",
      "公司有哪些常用福利？",
    ].join("\n"),
  },
  "general-qa": {
    title: "通用知识问答",
    name: "通用知识问答助手",
    slug: "general-qa",
    description: "面向团队知识库做统一检索、总结和问答。",
    welcome_message: "你好，我可以根据团队知识库回答问题并整理关键信息。",
    placeholder_text: "输入你想查询的知识问题...",
    persona_prompt:
      "你是一名通用知识问答数字员工。回答要简洁、准确，并在需要时引用知识库中的关键信息。",
    rule_template:
      "无法从知识库确认的信息要明确说明不确定，不要编造。可以给出下一步查询建议。",
    suggested_prompts_text: [
      "这个流程的关键步骤是什么？",
      "请总结这份制度的重点。",
      "这个问题应该参考哪些资料？",
    ].join("\n"),
  },
};

function createEmptyForm(): AssistantFormState {
  return {
    name: "",
    slug: "",
    description: "",
    welcome_message: "",
    placeholder_text: "",
    llm_model_key: null,
    persona_prompt: "",
    rule_template: "",
    suggested_prompts_text: "",
    is_active: true,
    knowledge_base_id: null,
    category_id: null,
    sort_order: 0,
  };
}

function toFormState(assistant: AssistantProfile): AssistantFormState {
  return {
    name: assistant.name,
    slug: assistant.slug,
    description: assistant.description ?? "",
    welcome_message: assistant.welcome_message ?? "",
    placeholder_text: assistant.placeholder_text ?? "",
    llm_model_key: assistant.llm_model_key ?? null,
    persona_prompt: assistant.persona_prompt ?? "",
    rule_template: assistant.rule_template ?? "",
    suggested_prompts_text: assistant.suggested_prompts.join("\n"),
    is_active: assistant.is_active,
    knowledge_base_id: assistant.knowledge_base_id,
    category_id: assistant.category_id ?? null,
    sort_order: assistant.sort_order,
  };
}

function parseSuggestedPrompts(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toPayload(form: AssistantFormState, teamId: number): AssistantUpsertPayload {
  if (form.knowledge_base_id == null) {
    throw new Error("请先选择知识库");
  }

  return {
    name: form.name.trim(),
    slug: form.slug.trim(),
    current_team_id: teamId,
    knowledge_base_id: form.knowledge_base_id,
    category_id: form.category_id,
    description: form.description.trim() || null,
    welcome_message: form.welcome_message.trim() || null,
    placeholder_text: form.placeholder_text.trim() || null,
    llm_model_key: form.llm_model_key,
    persona_prompt: form.persona_prompt.trim() || null,
    rule_template: form.rule_template.trim() || null,
    suggested_prompts: parseSuggestedPrompts(form.suggested_prompts_text),
    is_active: form.is_active,
    sort_order: Number.isFinite(form.sort_order) ? form.sort_order : 0,
  };
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function createSignature(form: AssistantFormState): string {
  return JSON.stringify(form);
}

function CollapsibleSection({
  id,
  title,
  description,
  icon: Icon,
  open,
  onToggle,
  action,
  children,
}: {
  id: SectionKey;
  title: string;
  description: string;
  icon: typeof Bot;
  open: boolean;
  onToggle: (id: SectionKey) => void;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card className="overflow-hidden rounded-lg border-slate-200 shadow-sm transition-shadow duration-300 hover:shadow-xl hover:shadow-slate-900/5">
      <CardHeader className="border-b border-slate-100 p-0">
        <div className="flex items-center gap-3 px-4 py-4">
          <button
            type="button"
            onClick={() => onToggle(id)}
            className="flex min-w-0 flex-1 items-center gap-3 text-left"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
              <Icon className="h-4 w-4" />
            </span>
            <span className="min-w-0">
              <CardTitle className="text-base font-semibold text-slate-900">{title}</CardTitle>
              <span className="mt-1 block truncate text-xs text-slate-500">{description}</span>
            </span>
          </button>
          {action}
          <button
            type="button"
            onClick={() => onToggle(id)}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
            title={open ? "折叠" : "展开"}
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} />
          </button>
        </div>
      </CardHeader>
      {open ? <CardContent className="space-y-5 p-4">{children}</CardContent> : null}
    </Card>
  );
}

function FieldLabel({ children, required }: { children: ReactNode; required?: boolean }) {
  return (
    <label className="text-sm font-medium text-slate-700">
      {children}
      {required ? <span className="ml-1 text-red-500">*</span> : null}
    </label>
  );
}

function PromptCodeTextarea({
  title,
  value,
  onChangeValue,
  placeholder,
  minRows,
  maxRows,
  pulse,
}: {
  title: string;
  value: string;
  onChangeValue: (value: string) => void;
  placeholder: string;
  minRows: number;
  maxRows: number;
  pulse: boolean;
}) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const computed = window.getComputedStyle(textarea);
    const lineHeight = Number.parseFloat(computed.lineHeight) || 24;
    const borderY =
      Number.parseFloat(computed.borderTopWidth) + Number.parseFloat(computed.borderBottomWidth);
    const minHeight = lineHeight * minRows + borderY;
    const maxHeight = lineHeight * maxRows + borderY;

    textarea.style.height = "auto";
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [maxRows, minRows, value]);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-slate-800 bg-slate-950 shadow-inner transition-all duration-500",
        pulse && "border-emerald-400 shadow-xl shadow-emerald-500/10",
      )}
    >
      <div className="flex items-center justify-between border-b border-white/10 bg-slate-900 px-3 py-2">
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-300" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
        </div>
        <span className="font-mono text-[11px] text-slate-400">{title}</span>
      </div>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => onChangeValue(event.target.value)}
        className={cn(
          "block w-full resize-none rounded-none border-0 bg-transparent p-4 font-mono text-sm leading-7 text-emerald-50 shadow-none outline-none transition-[height,color] duration-300 placeholder:text-slate-500 selection:bg-emerald-400/20",
        )}
        placeholder={placeholder}
      />
    </div>
  );
}

export function AssistantWorkbench({ mode, assistantId }: AssistantWorkbenchProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { teamId, selectedTeam } = useTeamScope();
  const templateId = searchParams.get("template");

  const [assistant, setAssistant] = useState<AssistantProfile | null>(null);
  const [form, setForm] = useState<AssistantFormState>(() => createEmptyForm());
  const [baseline, setBaseline] = useState(() => createSignature(createEmptyForm()));
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [categories, setCategories] = useState<DocumentCategory[]>([]);
  const [modelOptions, setModelOptions] = useState<AssistantModelOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [openSections, setOpenSections] = useState<Record<SectionKey, boolean>>({
    basic: true,
    behavior: true,
    experience: true,
  });
  const [activePresetId, setActivePresetId] = useState<string | null>(null);

  const isExisting = assistant != null;
  const dirty = createSignature(form) !== baseline;
  const selectedKnowledgeBase = knowledgeBases.find((item) => item.id === form.knowledge_base_id);
  const selectedModel =
    modelOptions.find((item) => item.key === form.llm_model_key) ?? modelOptions[0] ?? null;

  const previewDraft = useMemo<AssistantTestDraft>(() => {
    return {
      name: form.name.trim() || "未命名助手",
      current_team_id: teamId ?? 0,
      knowledge_base_id: form.knowledge_base_id ?? 0,
      category_id: form.category_id,
      description: form.description.trim() || null,
      welcome_message: form.welcome_message.trim() || null,
      placeholder_text: form.placeholder_text.trim() || null,
      llm_model_key: form.llm_model_key,
      persona_prompt: form.persona_prompt.trim() || null,
      rule_template: form.rule_template.trim() || null,
      suggested_prompts: parseSuggestedPrompts(form.suggested_prompts_text),
      is_active: form.is_active,
      sort_order: form.sort_order,
      include_unpublished: true,
    };
  }, [form, teamId]);
  const previewReady = teamId != null && form.knowledge_base_id != null;

  useEffect(() => {
    if (teamId == null) {
      setKnowledgeBases([]);
      setLoading(false);
      return;
    }

    void (async () => {
      setLoading(true);
      try {
        const [kbItems, modelOptionsResponse, detail] = await Promise.all([
          listKnowledgeBases(teamId),
          assistantsApi.listModelOptions(),
          mode === "edit" && assistantId ? assistantsApi.get(assistantId) : Promise.resolve(null),
        ]);

        setKnowledgeBases(kbItems);
        setModelOptions(modelOptionsResponse.items);

        if (detail) {
          const nextForm = toFormState(detail);
          setAssistant(detail);
          setForm(nextForm);
          setBaseline(createSignature(nextForm));
          return;
        }

        const preset = templateId ? TEMPLATE_PRESETS[templateId] : null;
        const defaultModelKey = modelOptionsResponse.items[0]?.key ?? null;
        const nextForm = preset
          ? { ...createEmptyForm(), llm_model_key: defaultModelKey, ...preset }
          : { ...createEmptyForm(), llm_model_key: defaultModelKey };
        setAssistant(null);
        setForm(nextForm);
        setBaseline(createSignature(createEmptyForm()));
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "加载助手配置失败");
      } finally {
        setLoading(false);
      }
    })();
  }, [assistantId, mode, teamId, templateId]);

  useEffect(() => {
    const knowledgeBaseId = form.knowledge_base_id;
    if (knowledgeBaseId == null) {
      setCategories([]);
      return;
    }

    void (async () => {
      try {
        setCategories(await listDocumentCategories(knowledgeBaseId));
      } catch {
        setCategories([]);
      }
    })();
  }, [form.knowledge_base_id]);

  const updateForm = (patch: Partial<AssistantFormState>) => {
    setForm((current) => ({ ...current, ...patch }));
  };

  const toggleSection = (section: SectionKey) => {
    setOpenSections((current) => ({ ...current, [section]: !current[section] }));
  };

  const applyPreset = (presetId: string) => {
    const preset = TEMPLATE_PRESETS[presetId];
    if (!preset) return;
    setActivePresetId(presetId);
    setForm((current) => ({
      ...current,
      ...preset,
      knowledge_base_id: current.knowledge_base_id,
      category_id: current.category_id,
      is_active: current.is_active,
      sort_order: current.sort_order,
    }));
    setOpenSections((current) => ({ ...current, behavior: true, experience: true }));
    toast.success("预设模板已导入");
    window.setTimeout(() => setActivePresetId(null), 900);
  };

  const handleSave = async () => {
    if (teamId == null) {
      toast.error("当前没有可用团队");
      return;
    }
    if (!form.name.trim()) {
      toast.error("请填写助手名称");
      return;
    }
    if (!form.slug.trim()) {
      toast.error("请填写助手标识");
      return;
    }
    if (form.knowledge_base_id == null) {
      toast.error("请选择知识库");
      return;
    }

    setSaving(true);
    try {
      const payload = toPayload(form, teamId);
      const saved = isExisting
        ? await assistantsApi.update(assistant.id, payload)
        : await assistantsApi.create(payload);
      const nextForm = toFormState(saved);
      setAssistant(saved);
      setForm(nextForm);
      setBaseline(createSignature(nextForm));
      toast.success(isExisting ? "助手配置已保存" : "助手已创建");

      if (!isExisting) {
        router.replace(`/admin/assistants/${saved.id}/edit`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在加载助手工作台...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="flex min-h-[72px] items-center justify-between gap-4 px-5 py-3 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => router.push("/admin/assistants")}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
              title="返回"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-xl font-semibold text-slate-900">
                  {form.name.trim() || (isExisting ? "未命名助手" : "新建助手")}
                </h1>
                {dirty ? (
                  <Badge className="shrink-0 bg-amber-50 text-amber-700 hover:bg-amber-50">
                    未保存
                  </Badge>
                ) : (
                  <Badge className="shrink-0 bg-emerald-50 text-emerald-700 hover:bg-emerald-50">
                    已同步
                  </Badge>
                )}
              </div>
              <p className="mt-1 truncate text-xs text-slate-500">
                {selectedTeam?.name ?? "未选择团队"} · {selectedKnowledgeBase?.name ?? "未绑定知识库"}
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-3">
            <button
              type="button"
              onClick={() => updateForm({ is_active: !form.is_active })}
              className={cn(
                "inline-flex h-10 items-center gap-2 rounded-lg border px-3 text-sm font-medium transition-colors",
                form.is_active
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                  : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50",
              )}
            >
              <Power className="h-4 w-4" />
              {form.is_active ? "启用" : "停用"}
            </button>
            <Button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving || teamId == null}
              className="h-10 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-600 px-4 text-white shadow-sm shadow-emerald-500/20 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-emerald-500/25"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              保存
            </Button>
          </div>
        </div>
      </header>

      <main className="grid gap-6 px-5 py-6 lg:px-8 xl:grid-cols-[minmax(0,1fr)_460px]">
        <section className="min-w-0 space-y-4">
          {mode === "create" ? (
            <div className="overflow-hidden rounded-lg border border-emerald-100 bg-white shadow-sm shadow-emerald-500/5 transition-shadow duration-300 hover:shadow-xl hover:shadow-emerald-500/10">
              <div className="border-b border-emerald-100/70 bg-gradient-to-r from-emerald-50 to-teal-50 px-4 py-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-emerald-600" />
                  <h2 className="text-sm font-semibold text-slate-900">推荐模板</h2>
                </div>
              </div>
              <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-4">
                {Object.entries(TEMPLATE_PRESETS).map(([key, preset]) => {
                  const active = activePresetId === key;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => applyPreset(key)}
                      className={cn(
                        "group rounded-lg border bg-white p-3 text-left shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-xl hover:shadow-emerald-500/10",
                        active &&
                          "scale-[1.02] border-emerald-300 bg-emerald-50 shadow-xl shadow-emerald-500/15",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <Badge className="bg-teal-50 text-teal-700 transition-colors group-hover:bg-teal-100">
                          模板
                        </Badge>
                        <Wand2
                          className={cn(
                            "h-4 w-4 text-slate-300 transition-colors group-hover:text-emerald-500",
                            active && "text-emerald-500",
                          )}
                        />
                      </div>
                      <div className="mt-3 text-sm font-semibold text-slate-900">
                        {preset.title}
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
                        {preset.description}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          <CollapsibleSection
            id="basic"
            title="基础设定"
            description="名称、描述、知识库和分类范围"
            icon={Database}
            open={openSections.basic}
            onToggle={toggleSection}
          >
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <FieldLabel required>名称</FieldLabel>
                <Input
                  value={form.name}
                  onChange={(event) => {
                    const nextName = event.target.value;
                    setForm((current) => {
                      const next = { ...current, name: nextName };
                      if (!current.slug || current.slug === slugify(current.name)) {
                        next.slug = slugify(nextName);
                      }
                      return next;
                    });
                  }}
                  className="h-11 rounded-lg border-slate-200"
                  placeholder="例如：售后支持助手"
                />
              </div>
              <div className="space-y-2">
                <FieldLabel required>标识</FieldLabel>
                <Input
                  value={form.slug}
                  onChange={(event) => updateForm({ slug: event.target.value })}
                  className="h-11 rounded-lg border-slate-200 font-mono"
                  placeholder="support-assistant"
                />
              </div>
            </div>

            <div className="space-y-2">
              <FieldLabel>描述</FieldLabel>
              <Textarea
                rows={3}
                value={form.description}
                onChange={(event) => updateForm({ description: event.target.value })}
                className="min-h-[96px] rounded-lg border-slate-200 text-sm"
                placeholder="一句话说明这个助手适合回答什么问题"
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <FieldLabel required>关联知识库</FieldLabel>
                <select
                  value={form.knowledge_base_id ?? ""}
                  onChange={(event) =>
                    updateForm({
                      knowledge_base_id: event.target.value ? Number(event.target.value) : null,
                      category_id: null,
                    })
                  }
                  className="h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-2 focus:ring-emerald-100"
                >
                  <option value="">请选择知识库</option>
                  {knowledgeBases.map((kb) => (
                    <option key={kb.id} value={kb.id}>
                      {kb.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <FieldLabel>限定分类</FieldLabel>
                <select
                  value={form.category_id ?? ""}
                  disabled={form.knowledge_base_id == null}
                  onChange={(event) =>
                    updateForm({
                      category_id: event.target.value ? Number(event.target.value) : null,
                    })
                  }
                  className="h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-2 focus:ring-emerald-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                >
                  <option value="">不限分类</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </CollapsibleSection>

          <CollapsibleSection
            id="behavior"
            title="行为定义"
            description="人格 Prompt 和回答规则模板"
            icon={Brain}
            open={openSections.behavior}
            onToggle={toggleSection}
            action={
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    className="hidden h-8 shrink-0 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 sm:inline-flex"
                  >
                    <Wand2 className="h-3.5 w-3.5" />
                    导入预设
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuLabel>预设模板</DropdownMenuLabel>
                  {Object.entries(TEMPLATE_PRESETS).map(([key, preset]) => (
                    <DropdownMenuItem key={key} onSelect={() => applyPreset(key)}>
                      {preset.title}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            }
          >
            <div className="space-y-2">
              <FieldLabel>人格 Prompt</FieldLabel>
              <PromptCodeTextarea
                title="persona.prompt"
                value={form.persona_prompt}
                onChangeValue={(value) => updateForm({ persona_prompt: value })}
                minRows={8}
                maxRows={22}
                pulse={activePresetId != null}
                placeholder="定义助手的身份、语气、边界和回答风格"
              />
            </div>
            <div className="space-y-2">
              <FieldLabel>规则模板</FieldLabel>
              <PromptCodeTextarea
                title="rules.template"
                value={form.rule_template}
                onChangeValue={(value) => updateForm({ rule_template: value })}
                minRows={5}
                maxRows={16}
                pulse={activePresetId != null}
                placeholder="例如：优先引用知识库；找不到依据时明确说明不确定"
              />
            </div>
          </CollapsibleSection>

          <CollapsibleSection
            id="experience"
            title="交互体验"
            description="欢迎语、输入框提示和推荐问题"
            icon={MessageSquareText}
            open={openSections.experience}
            onToggle={toggleSection}
          >
            <div className="space-y-2">
              <FieldLabel>欢迎语</FieldLabel>
              <Textarea
                rows={3}
                value={form.welcome_message}
                onChange={(event) => updateForm({ welcome_message: event.target.value })}
                className="rounded-lg border-slate-200 text-sm"
                placeholder="用户打开问答窗口时看到的第一句话"
              />
            </div>
            <div className="space-y-2">
              <FieldLabel>输入框提示</FieldLabel>
              <Input
                value={form.placeholder_text}
                onChange={(event) => updateForm({ placeholder_text: event.target.value })}
                className="h-11 rounded-lg border-slate-200"
                placeholder="例如：输入你的问题，按 Enter 发送"
              />
            </div>
            <div className="space-y-2">
              <FieldLabel>推荐问题</FieldLabel>
              <Textarea
                rows={5}
                value={form.suggested_prompts_text}
                onChange={(event) => updateForm({ suggested_prompts_text: event.target.value })}
                className="resize-y rounded-lg border-slate-200 text-sm"
                placeholder={"每行一个推荐问题\n例如：\n如何申请退换货？\n发票如何开具？"}
              />
            </div>
          </CollapsibleSection>
        </section>

        <aside className="min-h-0 xl:sticky xl:top-[96px] xl:h-[calc(100vh-120px)]">
          <div className="flex h-full min-h-[720px] flex-col gap-4 xl:min-h-0">
            <Card className="shrink-0 rounded-lg border-slate-200 shadow-sm transition-shadow duration-300 hover:shadow-xl hover:shadow-slate-900/5">
              <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-slate-100 p-4">
                <div className="flex items-center gap-2">
                  <SlidersHorizontal className="h-4 w-4 text-slate-500" />
                  <CardTitle className="text-base font-semibold text-slate-900">
                    模型与参数
                  </CardTitle>
                </div>
                <Badge className="bg-slate-100 text-slate-600 hover:bg-slate-100">
                  {selectedModel?.provider ?? "System"}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-4 p-4">
                <div className="space-y-2">
                  <FieldLabel>模型</FieldLabel>
                  <select
                    value={form.llm_model_key ?? ""}
                    onChange={(event) =>
                      updateForm({ llm_model_key: event.target.value || null })
                    }
                    className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none focus:border-emerald-300 focus:ring-2 focus:ring-emerald-100"
                  >
                    <option value="">使用系统默认</option>
                    {modelOptions.map((item) => (
                      <option key={item.key} value={item.key}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-4 shadow-sm">
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-slate-900">
                      {selectedModel?.name ?? "系统默认模型"}
                    </p>
                    <p className="text-sm text-slate-600">
                      {selectedModel
                        ? `${selectedModel.provider} / ${selectedModel.model}`
                        : "未单独指定时，回退到 system_roles.generation"}
                    </p>
                  </div>
                  <div className="mt-3 rounded-lg border border-emerald-100 bg-white px-3 py-2 text-xs leading-5 text-slate-500">
                    助手问答优先使用当前绑定的模型资产。未选择时，后端回退到系统默认的
                    {" "}
                    generation
                    {" "}
                    映射。
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="min-h-0 flex-1 overflow-hidden rounded-lg border-slate-200 shadow-sm transition-shadow duration-300 hover:shadow-xl hover:shadow-slate-900/5">
              <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-slate-100 p-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-teal-600" />
                  <CardTitle className="text-base font-semibold text-slate-900">
                    预览与测试
                  </CardTitle>
                </div>
                {previewReady ? (
                  <Badge className="bg-teal-50 text-teal-700 hover:bg-teal-50">
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    可测试
                  </Badge>
                ) : (
                  <Badge className="bg-slate-100 text-slate-500 hover:bg-slate-100">
                    待绑定
                  </Badge>
                )}
              </CardHeader>
              <CardContent className="h-[560px] p-0 xl:h-[calc(100%-57px)]">
                <AssistantTestChat
                  assistantId={assistant?.id ?? null}
                  draft={previewDraft}
                  className="h-full"
                />
              </CardContent>
            </Card>
          </div>
        </aside>
      </main>
    </div>
  );
}
