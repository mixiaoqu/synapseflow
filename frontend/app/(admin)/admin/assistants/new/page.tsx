"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bot, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  assistantsApi,
  type AssistantUpsertPayload,
} from "@/lib/api/assistants";
import {
  listKnowledgeBases,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import {
  listDocumentCategories,
  type DocumentCategory,
} from "@/lib/api/documentCategories";
import { cn } from "@/lib/utils";

interface FormState {
  name: string;
  slug: string;
  description: string;
  welcome_message: string;
  placeholder_text: string;
  persona_prompt: string;
  rule_template: string;
  suggested_prompts_text: string;
  is_active: boolean;
  knowledge_base_id: number | null;
  category_id: number | null;
  sort_order: number;
}

const ASSISTANT_TEMPLATE_PRESETS: Record<
  string,
  Pick<
    FormState,
    | "name"
    | "slug"
    | "description"
    | "welcome_message"
    | "placeholder_text"
    | "persona_prompt"
    | "rule_template"
    | "suggested_prompts_text"
  >
> = {
  "it-helpdesk": {
    name: "企业 IT 帮助台助手",
    slug: "it-helpdesk",
    description: "解答员工常见的 IT 设备、网络、账号和软件问题。",
    welcome_message: "你好，我可以协助你排查办公设备、网络、账号和常用软件问题。",
    placeholder_text: "描述你遇到的 IT 问题...",
    persona_prompt:
      "你是一名企业 IT 帮助台数字员工，回答要清晰、分步骤，并在信息不足时先询问设备、系统、网络环境和错误提示。",
    rule_template:
      "优先基于知识库回答。涉及账号权限、数据安全或设备维修时，提示用户联系 IT 工单渠道并补充必要信息。",
    suggested_prompts_text: [
      "VPN 连不上应该怎么排查？",
      "公司邮箱无法登录怎么办？",
      "新电脑需要安装哪些基础软件？",
    ].join("\n"),
  },
  "legal-review": {
    name: "法务合同审查助手",
    slug: "legal-review",
    description: "辅助审查标准合同条款，提示常见风险和补充材料。",
    welcome_message: "你好，我可以帮你初步梳理合同条款风险和需要法务确认的问题。",
    placeholder_text: "输入合同条款或审查问题...",
    persona_prompt:
      "你是一名法务合同审查数字员工，回答要谨慎、结构化，区分事实、风险提示和需要人工法务确认的事项。",
    rule_template:
      "不得给出最终法律结论。遇到高风险条款、金额、期限、违约责任、知识产权和数据合规时，提示升级给法务负责人。",
    suggested_prompts_text: [
      "这个保密条款有哪些风险？",
      "供应商合同付款条款需要注意什么？",
      "违约责任条款如何审查？",
    ].join("\n"),
  },
  onboarding: {
    name: "新员工入职向导",
    slug: "onboarding-guide",
    description: "引导新员工了解报到流程、福利政策和企业文化。",
    welcome_message: "欢迎加入团队，我可以帮你了解入职流程、福利和常见行政事项。",
    placeholder_text: "询问入职流程、福利或行政问题...",
    persona_prompt:
      "你是一名新员工入职向导，语气友好、准确，优先给出可执行步骤和相关材料位置。",
    rule_template:
      "优先基于知识库回答。涉及个人薪酬、合同、社保等敏感问题时，引导用户联系 HR 专员。",
    suggested_prompts_text: [
      "入职第一天需要完成哪些事项？",
      "如何申请办公设备？",
      "公司有哪些常用福利？",
    ].join("\n"),
  },
  "general-qa": {
    name: "通用知识问答助手",
    slug: "general-qa",
    description: "面向团队知识库做统一检索、总结和问答。",
    welcome_message: "你好，我可以根据团队知识库回答问题并整理关键信息。",
    placeholder_text: "输入你想查询的知识问题...",
    persona_prompt:
      "你是一名通用知识问答数字员工，回答要简洁、准确，并在需要时引用知识库中的关键信息。",
    rule_template:
      "无法从知识库确认的信息要明确说明不确定，不要编造。可给出下一步查询建议。",
    suggested_prompts_text: [
      "这个流程的关键步骤是什么？",
      "请总结这份制度的重点。",
      "这个问题应该参考哪些资料？",
    ].join("\n"),
  },
};

function createEmptyForm(): FormState {
  return {
    name: "",
    slug: "",
    description: "",
    welcome_message: "",
    placeholder_text: "",
    persona_prompt: "",
    rule_template: "",
    suggested_prompts_text: "",
    is_active: true,
    knowledge_base_id: null,
    category_id: null,
    sort_order: 0,
  };
}

function toPayload(form: FormState, teamId: number): AssistantUpsertPayload {
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
    persona_prompt: form.persona_prompt.trim() || null,
    rule_template: form.rule_template.trim() || null,
    suggested_prompts: form.suggested_prompts_text
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean),
    is_active: form.is_active,
    sort_order: form.sort_order,
  };
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default function NewAssistantPage() {
  const router = useRouter();
  const { teamId, selectedTeam } = useTeamScope();

  const [form, setForm] = useState<FormState>(createEmptyForm());
  const [templateApplied, setTemplateApplied] = useState(false);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [categories, setCategories] = useState<DocumentCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [kbsLoading, setKbsLoading] = useState(false);

  useEffect(() => {
    if (templateApplied) return;
    const templateId = new URLSearchParams(window.location.search).get("template");
    if (!templateId) return;

    const preset = ASSISTANT_TEMPLATE_PRESETS[templateId];
    if (!preset) return;

    setForm((current) => ({
      ...current,
      ...preset,
    }));
    setTemplateApplied(true);
  }, [templateApplied]);

  useEffect(() => {
    if (teamId == null) {
      setLoading(false);
      return;
    }

    void (async () => {
      setLoading(true);
      setKbsLoading(true);
      try {
        const kbs = await listKnowledgeBases(teamId);
        setKnowledgeBases(kbs);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "加载知识库失败");
      } finally {
        setLoading(false);
        setKbsLoading(false);
      }
    })();
  }, [teamId]);

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

  const handleSave = async () => {
    if (teamId == null) {
      toast.error("当前没有可用团队");
      return;
    }
    if (!form.name.trim()) {
      toast.error("请填写助手名称");
      return;
    }
    if (form.knowledge_base_id == null) {
      toast.error("请选择知识库");
      return;
    }

    setSaving(true);
    try {
      const created = await assistantsApi.create(toPayload(form, teamId));
      toast.success("助手已创建");
      router.push(`/admin/assistants/${created.id}/edit`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "创建助手失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center text-sm text-slate-500">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在加载...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f8fafc] px-6 py-8 md:px-8">
      <div className="mx-auto max-w-7xl space-y-8">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <a href="/admin/assistants" className="transition-colors hover:text-slate-900">
            Assistants
          </a>
          <Bot className="h-4 w-4" />
          <span className="text-slate-700">新建助手</span>
        </div>

        {/* Header */}
        <div className="rounded-[28px] border border-slate-200/80 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">新建助手</h1>
              <p className="mt-1 text-sm text-slate-500">
                为团队「{selectedTeam?.name}」创建新的助手
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => router.push("/admin/assistants")}
                className="inline-flex h-11 items-center rounded-2xl border border-slate-200 px-5 text-sm text-slate-700 transition-colors hover:bg-slate-50"
              >
                取消
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => void handleSave()}
                className="inline-flex h-11 items-center rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 px-5 text-sm font-medium text-white shadow-lg shadow-emerald-500/20 transition-all hover:-translate-y-0.5 hover:shadow-xl disabled:opacity-50"
              >
                {saving ? "创建中..." : "创建助手"}
              </button>
            </div>
          </div>
        </div>

        {/* Form Grid */}
        <div className="grid grid-cols-1 gap-8 xl:grid-cols-3">
          <div className="space-y-8 xl:col-span-2">
            {/* Basic Info */}
            <Card className="rounded-[28px] border-slate-200/80 shadow-sm">
              <CardHeader>
                <CardTitle>基础信息</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">名称 *</label>
                  <Input
                    value={form.name}
                    onChange={(event) =>
                      setForm((current) => {
                        const next = { ...current, name: event.target.value };
                        if (!current.slug || current.slug === slugify(current.name)) {
                          next.slug = slugify(next.name);
                        }
                        return next;
                      })
                    }
                    className="rounded-2xl"
                    placeholder="例如：售后支持助手"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">标识</label>
                  <Input
                    value={form.slug}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, slug: event.target.value }))
                    }
                    className="rounded-2xl font-mono"
                    placeholder="例如：support-assistant"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">描述</label>
                  <textarea
                    rows={3}
                    value={form.description}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, description: event.target.value }))
                    }
                    className="min-h-[100px] w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
                    placeholder="一句话说明这个助手适合回答什么问题"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Prompt Editor */}
            <Card className="rounded-[28px] border-slate-200/80 shadow-sm">
              <CardHeader>
                <CardTitle>Prompt 编辑器</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">人格 Prompt</label>
                  <textarea
                    value={form.persona_prompt}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, persona_prompt: event.target.value }))
                    }
                    className="min-h-[300px] w-full resize-y rounded-2xl border border-slate-200 bg-slate-50/70 p-4 font-mono text-sm leading-relaxed text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
                    placeholder="定义助手的身份、语气和回答风格"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">规则模板</label>
                  <textarea
                    rows={6}
                    value={form.rule_template}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, rule_template: event.target.value }))
                    }
                    className="w-full resize-y rounded-2xl border border-slate-200 bg-slate-50/70 p-4 font-mono text-sm leading-relaxed text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
                    placeholder="例如：优先引用知识库；找不到依据时明确说明"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Welcome Settings */}
            <Card className="rounded-[28px] border-slate-200/80 shadow-sm">
              <CardHeader>
                <CardTitle>开场白设置</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">欢迎语</label>
                  <textarea
                    rows={3}
                    value={form.welcome_message}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, welcome_message: event.target.value }))
                    }
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
                    placeholder="用户进入问答页后看到的欢迎文案"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">输入框提示</label>
                  <Input
                    value={form.placeholder_text}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, placeholder_text: event.target.value }))
                    }
                    className="rounded-2xl"
                    placeholder="例如：输入您的问题，按 Enter 发送"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">推荐问题</label>
                  <textarea
                    rows={4}
                    value={form.suggested_prompts_text}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        suggested_prompts_text: event.target.value,
                      }))
                    }
                    className="w-full resize-y rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
                    placeholder={"每行一个推荐问题\n例如：\n如何申请退换货？\n发票如何开具？"}
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Sidebar */}
          <div className="space-y-6">
            {/* Scope */}
            <Card className="rounded-[28px] border-slate-200/80 shadow-sm">
              <CardHeader>
                <CardTitle>绑定范围</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                  助手会自动归属当前团队「{selectedTeam?.name}」
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">知识库 *</label>
                  <select
                    value={form.knowledge_base_id ?? ""}
                    disabled={kbsLoading}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        knowledge_base_id: event.target.value ? Number(event.target.value) : null,
                        category_id: null,
                      }))
                    }
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
                  >
                    <option value="">
                      {kbsLoading ? "加载中..." : "请选择知识库"}
                    </option>
                    {knowledgeBases.map((kb) => (
                      <option key={kb.id} value={kb.id}>
                        {kb.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700">分类</label>
                  <select
                    value={form.category_id ?? ""}
                    disabled={form.knowledge_base_id == null}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        category_id: event.target.value ? Number(event.target.value) : null,
                      }))
                    }
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
                  >
                    <option value="">不限分类</option>
                    {categories.map((cat) => (
                      <option key={cat.id} value={cat.id}>
                        {cat.name}
                      </option>
                    ))}
                  </select>
                </div>
              </CardContent>
            </Card>

            {/* Status */}
            <Card className="rounded-[28px] border-slate-200/80 shadow-sm">
              <CardHeader>
                <CardTitle>状态</CardTitle>
              </CardHeader>
              <CardContent>
                <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, is_active: event.target.checked }))
                    }
                    className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-200"
                  />
                  <div>
                    <div className="text-sm font-medium text-slate-800">启用助手</div>
                    <div className="text-xs text-slate-500">关闭后不会出现在前台助手列表中</div>
                  </div>
                </label>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
