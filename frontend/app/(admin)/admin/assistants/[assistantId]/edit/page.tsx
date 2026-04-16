"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Bot, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { useTeamScope } from "@/components/kb-chat/AskTeamScopeProvider";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import {
  assistantsApi,
  type AssistantProfile,
  type AssistantUpsertPayload,
} from "@/lib/api/assistants";

interface EditFormState {
  name: string;
  slug: string;
  description: string;
  welcome_message: string;
  placeholder_text: string;
  persona_prompt: string;
  rule_template: string;
  suggested_prompts_text: string;
  is_active: boolean;
  knowledge_base_id: number;
  category_id: number | null;
  sort_order: number;
}

interface ModelTuningState {
  provider: string;
  model: string;
  temperature: number;
  topP: number;
  maxTokens: number;
}

function toFormState(assistant: AssistantProfile): EditFormState {
  return {
    name: assistant.name,
    slug: assistant.slug,
    description: assistant.description ?? "",
    welcome_message: assistant.welcome_message ?? "",
    placeholder_text: assistant.placeholder_text ?? "",
    persona_prompt: assistant.persona_prompt ?? "",
    rule_template: assistant.rule_template ?? "",
    suggested_prompts_text: assistant.suggested_prompts.join("\n"),
    is_active: assistant.is_active,
    knowledge_base_id: assistant.knowledge_base_id,
    category_id: assistant.category_id ?? null,
    sort_order: assistant.sort_order,
  };
}

function toPayload(form: EditFormState, teamId: number): AssistantUpsertPayload {
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

const MODEL_OPTIONS = [
  { provider: "OpenAI", model: "gpt-4.1-mini" },
  { provider: "OpenAI", model: "gpt-4.1" },
  { provider: "Anthropic", model: "claude-3-5-sonnet" },
];

export default function AssistantEditPage() {
  const params = useParams<{ assistantId: string }>();
  const { teamId } = useTeamScope();
  const assistantId = Number(params.assistantId);

  const [assistant, setAssistant] = useState<AssistantProfile | null>(null);
  const [form, setForm] = useState<EditFormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tuning, setTuning] = useState<ModelTuningState>({
    provider: "OpenAI",
    model: "gpt-4.1-mini",
    temperature: 0.7,
    topP: 0.9,
    maxTokens: 2048,
  });

  useEffect(() => {
    if (!Number.isFinite(assistantId) || assistantId <= 0) {
      setLoading(false);
      return;
    }

    void (async () => {
      setLoading(true);
      try {
        const detail = await assistantsApi.get(assistantId);
        setAssistant(detail);
        setForm(toFormState(detail));
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "加载助手配置失败");
      } finally {
        setLoading(false);
      }
    })();
  }, [assistantId]);

  const selectedModelGroup = useMemo(
    () => MODEL_OPTIONS.find((item) => item.model === tuning.model),
    [tuning.model],
  );

  const handleSave = async () => {
    if (!form || teamId == null || !assistant) {
      toast.error("当前无法保存，请确认团队上下文是否完整");
      return;
    }

    setSaving(true);
    try {
      const updated = await assistantsApi.update(assistant.id, toPayload(form, teamId));
      setAssistant(updated);
      setForm(toFormState(updated));
      toast.success("助手配置已保存");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存助手配置失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading || !form) {
    return (
      <div className="flex min-h-[400px] items-center justify-center text-sm text-slate-500">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在加载配置页...
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-8 xl:grid-cols-3">
      <div className="space-y-8 xl:col-span-2">
        <Card className="rounded-[28px] border-slate-200/80 shadow-sm">
          <CardHeader>
            <CardTitle>基础信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">名称</label>
              <Input
                value={form.name}
                onChange={(event) =>
                  setForm((current) => (current ? { ...current, name: event.target.value } : current))
                }
                className="rounded-2xl"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">描述</label>
              <textarea
                rows={4}
                value={form.description}
                onChange={(event) =>
                  setForm((current) =>
                    current ? { ...current, description: event.target.value } : current,
                  )
                }
                className="min-h-[120px] w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
              />
            </div>
          </CardContent>
        </Card>

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
                  setForm((current) =>
                    current ? { ...current, persona_prompt: event.target.value } : current,
                  )
                }
                className="min-h-[400px] w-full resize-y rounded-2xl border border-slate-200 bg-slate-50/70 p-4 font-mono text-sm leading-relaxed text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">规则模板</label>
              <textarea
                rows={8}
                value={form.rule_template}
                onChange={(event) =>
                  setForm((current) =>
                    current ? { ...current, rule_template: event.target.value } : current,
                  )
                }
                className="w-full resize-y rounded-2xl border border-slate-200 bg-slate-50/70 p-4 font-mono text-sm leading-relaxed text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
              />
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-[28px] border-slate-200/80 shadow-sm">
          <CardHeader>
            <CardTitle>开场白设置</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">欢迎语</label>
              <textarea
                rows={4}
                value={form.welcome_message}
                onChange={(event) =>
                  setForm((current) =>
                    current ? { ...current, welcome_message: event.target.value } : current,
                  )
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">输入框提示</label>
              <Input
                value={form.placeholder_text}
                onChange={(event) =>
                  setForm((current) =>
                    current ? { ...current, placeholder_text: event.target.value } : current,
                  )
                }
                className="rounded-2xl"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">推荐问题</label>
              <textarea
                rows={5}
                value={form.suggested_prompts_text}
                onChange={(event) =>
                  setForm((current) =>
                    current ? { ...current, suggested_prompts_text: event.target.value } : current,
                  )
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6 xl:col-span-1">
        <div className="space-y-6 xl:sticky xl:top-24">
          <Card className="rounded-[28px] border-slate-200/80 shadow-sm">
            <CardHeader>
              <CardTitle>模型与参数</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">模型选择</label>
                <select
                  value={tuning.model}
                  onChange={(event) => {
                    const nextModel = event.target.value;
                    const nextGroup =
                      MODEL_OPTIONS.find((item) => item.model === nextModel) ?? MODEL_OPTIONS[0];
                    setTuning((current) => ({
                      ...current,
                      model: nextGroup.model,
                      provider: nextGroup.provider,
                    }));
                  }}
                  className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition-all focus:border-emerald-300 focus:ring-4 focus:ring-emerald-50"
                >
                  {MODEL_OPTIONS.map((item) => (
                    <option key={item.model} value={item.model}>
                      {item.provider} / {item.model}
                    </option>
                  ))}
                </select>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Sparkles className="h-3.5 w-3.5" />
                  当前厂商：{selectedModelGroup?.provider ?? tuning.provider}
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-700">Temperature</span>
                  <span className="text-sm text-slate-500">{tuning.temperature.toFixed(1)}</span>
                </div>
                <Slider
                  min={0}
                  max={1}
                  step={0.1}
                  value={[tuning.temperature]}
                  onValueChange={([value]) =>
                    setTuning((current) => ({ ...current, temperature: value }))
                  }
                />
                <p className="text-xs text-slate-500">控制回答的发散程度，越高越灵活。</p>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-700">Top P</span>
                  <span className="text-sm text-slate-500">{tuning.topP.toFixed(1)}</span>
                </div>
                <Slider
                  min={0}
                  max={1}
                  step={0.1}
                  value={[tuning.topP]}
                  onValueChange={([value]) =>
                    setTuning((current) => ({ ...current, topP: value }))
                  }
                />
                <p className="text-xs text-slate-500">控制采样范围，越低越保守。</p>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-700">Max Tokens</span>
                  <span className="text-sm text-slate-500">{tuning.maxTokens}</span>
                </div>
                <Slider
                  min={256}
                  max={4096}
                  step={128}
                  value={[tuning.maxTokens]}
                  onValueChange={([value]) =>
                    setTuning((current) => ({ ...current, maxTokens: value }))
                  }
                />
                <p className="text-xs text-slate-500">限制单次回答长度，避免过短或过长。</p>
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-[28px] border-slate-200/80 shadow-sm">
            <CardHeader>
              <CardTitle>保存状态</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Bot className="h-4 w-4 text-emerald-600" />
                {assistant?.knowledge_base_name ?? "未绑定知识库"}
              </div>
              <Badge
                className={
                  assistant?.is_active
                    ? "w-fit bg-emerald-50 text-emerald-700 hover:bg-emerald-50"
                    : "w-fit bg-slate-100 text-slate-500 hover:bg-slate-100"
                }
              >
                {assistant?.is_active ? "已启用" : "已停用"}
              </Badge>
              <p className="text-xs text-slate-500">
                模型和采样参数面板当前用于配置预览，真正持久化的仍是助手资料、欢迎语和 Prompt。
              </p>
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saving}
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-5 text-sm font-medium text-white shadow-lg shadow-emerald-500/20 transition-all hover:-translate-y-0.5 hover:shadow-xl disabled:opacity-50"
              >
                {saving ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    保存中...
                  </>
                ) : (
                  "保存配置"
                )}
              </button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
