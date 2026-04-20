"use client";

import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  BookOpenText,
  Braces,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Clock3,
  FileSearch,
  Filter,
  Loader2,
  MessageSquareText,
  Plus,
  SearchCheck,
  Sparkles,
  ThumbsDown,
  Wrench,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  askApi,
  type AskDiagnosticDoc,
  type AskLogDetail,
  type AskLogItem,
  type AskLogListFilters,
  type AskRetrievalFunnel,
} from "@/lib/api/endpoints/ask";

const DEFAULT_LATENCY_THRESHOLD_MS = 5000;
const QA_REVIEW_LABELS = [
  "检索失败",
  "检索命中但答案未引用",
  "答案有依据但表达差",
  "答案正确但不完整",
  "幻觉/无依据扩写",
  "知识库缺内容",
  "问题超出范围",
] as const;

type QaPanelFilters = {
  limit: number;
  teamId: string;
  knowledgeBaseId: string;
  categoryId: string;
  answerStatus: string;
  retrievalStatus: string;
  feedbackValue: string;
  startDate: string;
  endDate: string;
  zeroHitsOnly: boolean;
  highLatencyOnly: boolean;
  highLatencyThresholdMs: number;
  queryKeyword: string;
};

const DEFAULT_FILTERS: QaPanelFilters = {
  limit: 50,
  teamId: "",
  knowledgeBaseId: "",
  categoryId: "",
  answerStatus: "",
  retrievalStatus: "",
  feedbackValue: "",
  startDate: "",
  endDate: "",
  zeroHitsOnly: false,
  highLatencyOnly: false,
  highLatencyThresholdMs: DEFAULT_LATENCY_THRESHOLD_MS,
  queryKeyword: "",
};

function formatTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatLatency(ms?: number | null) {
  if (ms == null) return "-";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function formatScopePath(item: {
  team_name?: string | null;
  knowledge_base_name?: string | null;
  category_name?: string | null;
}) {
  return [item.team_name, item.knowledge_base_name, item.category_name]
    .filter((v) => String(v || "").trim())
    .join(" · ");
}

function formatHitsAndLatency(item: { retrieved_count: number; latency_ms?: number | null }) {
  return `${item.retrieved_count} 条 · ${formatLatency(item.latency_ms)}`;
}

function shouldClampAnswer(answer: string) {
  const n = (answer || "").trim();
  return n.length > 180 || n.split("\n").length > 3;
}

/* ---- Answer status ---- */
const ANSWER_CONFIG: Record<string, { label: string; style: string }> = {
  answered:    { label: "已回答",   style: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  partial:    { label: "部分回答", style: "bg-amber-50 text-amber-700 border-amber-200" },
  insufficient:{ label: "依据不足", style: "bg-slate-100 text-slate-700 border-slate-200" },
  error:      { label: "异常",     style: "bg-rose-50 text-rose-700 border-rose-200" },
};
function getAnswerConfig(s?: string | null) {
  return ANSWER_CONFIG[s || ""] ?? { label: "未知", style: "bg-slate-100 text-slate-600 border-slate-200" };
}

/* ---- Retrieval status ---- */
const RETRIEVAL_CONFIG: Record<string, { label: string; style: string }> = {
  ok:                  { label: "已检索",  style: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  no_hits:             { label: "未命中",  style: "bg-amber-50 text-amber-700 border-amber-200" },
  empty_knowledge_base: { label: "无知识",  style: "bg-slate-100 text-slate-600 border-slate-200" },
  empty_collection:     { label: "无知识",  style: "bg-slate-100 text-slate-600 border-slate-200" },
};
function getRetrievalConfig(s?: string | null) {
  return RETRIEVAL_CONFIG[s || ""] ?? { label: "未知", style: "bg-slate-100 text-slate-600 border-slate-200" };
}

/* ---- Conclusion ---- */
function deriveConclusion(detail: AskLogDetail) {
  if (detail.retrieval_status === "empty_knowledge_base" || detail.retrieval_status === "empty_collection")
    return { tone: "neutral" as const, title: "当前范围暂无可用知识", summary: "这次回答缺少可检索的已索引内容，优先检查知识库或分类下是否有可用文档。", nextAction: "先补充文档并完成索引，再回到这条记录复测。" };
  if (detail.retrieval_status === "no_hits")
    return { tone: "warning" as const, title: "检索没有命中相关内容", summary: "问题已经发起检索，但当前范围内没有召回到足够相关的文档片段。", nextAction: "检查问题表述、同义词覆盖和分类范围是否过窄。" };
  if (detail.answer_status === "error")
    return { tone: "warning" as const, title: "回答链路出现异常", summary: "这次回答没有正常完成，当前记录更适合先排查模型调用或服务执行是否异常。", nextAction: "优先查看回答阶段日志，确认模型调用、超时或上下文长度是否存在问题。" };
  if (detail.answer_status === "partial" || detail.answer_status === "insufficient")
    return { tone: "warning" as const, title: "回答仍不够完整", summary: "虽然本次完成了检索或回答，但系统状态显示这条回复并没有充分解决问题。", nextAction: "补充该主题内容，或扩大当前检索范围后再次验证。" };
  if (detail.feedback_value === "not_helpful")
    return { tone: "warning" as const, title: "用户认为回答不够有帮助", summary: "系统检索到了参考内容，但用户反馈说明答案覆盖度或表达方式仍有问题。", nextAction: "结合用户备注检查答案是否真正覆盖问题，再决定是补知识还是优化回答策略。" };
  if (detail.feedback_value === "helpful")
    return { tone: "positive" as const, title: "用户反馈本次回答有效", summary: "这条记录拿到了明确正反馈，可以作为较稳定的可用问答样本继续抽查。", nextAction: "如需沉淀优秀案例，可进一步检查检索片段和范围配置是否具有复用价值。" };
  return { tone: "neutral" as const, title: "建议继续抽查", summary: "当前只能确认问答完成了基本流程，但还不能仅凭片段或上下文判断答案质量。", nextAction: "结合用户反馈、问题类型和回答内容继续复核。" };
}

const CONCL_TONE = {
  positive: "border-emerald-300 bg-emerald-50 text-emerald-900",
  warning:  "border-amber-300   bg-amber-50   text-amber-900",
  neutral:  "border-slate-200  bg-slate-50  text-slate-900",
};

/* ---- Feedback badge ---- */
function FeedbackBadge({ value }: { value?: string | null }) {
  if (!value) return null;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${value === "helpful" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
      {value === "helpful" ? "👍 有帮助" : "👎 待改进"}
    </span>
  );
}

/* ---- Info grid ---- */
function InfoGrid({ items }: { items: Array<{ label: string; value: string | number | null | undefined }> }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {items.map((item) => (
        <div key={item.label} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{item.label}</p>
          <p className="mt-1 text-sm font-medium text-slate-800">{item.value ?? "—"}</p>
        </div>
      ))}
    </div>
  );
}

/* ---- FunnelCard: horizontal bar chart ---- */
function FunnelCard({ funnel }: { funnel: AskRetrievalFunnel | null | undefined }) {
  if (!funnel || funnel.stages.length === 0) {
    return <p className="text-xs text-slate-400">暂无漏斗数据</p>;
  }
  const max = Math.max(...funnel.stages.map((s) => s.chunk_count), 1);
  return (
    <div className="space-y-1.5">
      {funnel.stages.map((stage, i) => {
        const pct = Math.max((stage.chunk_count / max) * 100, 8);
        const prev = funnel.stages[i - 1]?.chunk_count;
        const delta = prev != null ? stage.chunk_count - prev : null;
        const dStyle = delta == null ? "bg-slate-100 text-slate-500" : delta < 0 ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600";
        return (
          <div key={stage.key} className="flex items-center gap-2.5">
            <div className="w-24 shrink-0 text-xs font-medium text-slate-600">{stage.label}</div>
            <div className="h-6 flex-1 min-w-0 rounded-full bg-slate-100">
              <div
                className="flex h-full items-center justify-end rounded-full bg-gradient-to-l from-slate-600 to-slate-400 pr-2 text-[10px] font-medium text-white transition-all"
                style={{ width: `${pct}%`, minWidth: "20px" }}
              >
                {stage.chunk_count}
              </div>
            </div>
            {delta != null && (
              <span className={`w-10 shrink-0 rounded-full px-1.5 py-0.5 text-center text-[10px] font-medium ${dStyle}`}>
                {delta > 0 ? `+${delta}` : delta}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ---- DocCard: expandable with similarity bar ---- */
function DocCard({ doc, expanded, onToggle }: { doc: AskDiagnosticDoc; expanded: boolean; onToggle: () => void }) {
  const score = typeof doc.metadata.score === "number" ? doc.metadata.score : null;
  const rerank = typeof doc.metadata.rerank_score === "number" ? doc.metadata.rerank_score : null;
  const barPct = score != null ? Math.round(Math.min(score, 1) * 100) : null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50"
        onClick={onToggle}
      >
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">#{doc.rank}</span>
          {doc.metadata.document_title && (
            <span className="rounded-full bg-white px-2 py-0.5 text-[10px] text-slate-600">{doc.metadata.document_title}</span>
          )}
          {rerank != null && (
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] text-blue-600">rerank {rerank.toFixed(3)}</span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {barPct != null && (
            <div className="flex items-center gap-1.5">
              <div className="h-1.5 w-14 rounded-full bg-slate-100">
                <div className="h-1.5 rounded-full bg-blue-400 transition-all" style={{ width: `${barPct}%` }} />
              </div>
              <span className="text-[10px] text-slate-400">{score!.toFixed(3)}</span>
            </div>
          )}
          {expanded ? <ChevronUp className="h-3.5 w-3.5 text-slate-400" /> : <ChevronDown className="h-3.5 w-3.5 text-slate-400" />}
        </div>
      </button>
      {expanded && (
        <div className="border-t border-slate-100 px-4 py-3">
          <p className="line-clamp-4 whitespace-pre-wrap text-xs leading-relaxed text-slate-600">{doc.content || "暂无片段内容"}</p>
          {doc.metadata.source_path && (
            <p className="mt-2 text-[10px] text-slate-400">来源：{doc.metadata.source_path}</p>
          )}
        </div>
      )}
    </div>
  );
}

function toLogListFilters(f: QaPanelFilters): AskLogListFilters {
  return {
    limit: f.limit,
    team_id:              f.teamId              ? Number(f.teamId)            : null,
    knowledge_base_id:     f.knowledgeBaseId     ? Number(f.knowledgeBaseId)  : null,
    category_id:          f.categoryId          ? Number(f.categoryId)       : null,
    answer_status:        f.answerStatus       || null,
    retrieval_status:     f.retrievalStatus    || null,
    feedback_value:       f.feedbackValue      || null,
    start_date:           f.startDate           || null,
    end_date:             f.endDate            || null,
    zero_hits_only:       f.zeroHitsOnly,
    high_latency_only:    f.highLatencyOnly,
    high_latency_threshold_ms: f.highLatencyThresholdMs,
    query_keyword:        f.queryKeyword.trim() || null,
  };
}

function buildFilterOptions(items: AskLogItem[]) {
  const teams = new Map<number, string>();
  const kbs   = new Map<number, string>();
  const cats  = new Map<number, string>();
  for (const item of items) {
    if (item.team_id != null) teams.set(item.team_id, item.team_name || `团队 ${item.team_id}`);
    if (item.knowledge_base_id != null) kbs.set(item.knowledge_base_id, item.knowledge_base_name || `KB ${item.knowledge_base_id}`);
    if (item.category_id != null) cats.set(item.category_id, item.category_name || `分类 ${item.category_id}`);
  }
  const sort = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name, "zh-CN");
  return {
    teams: [...teams.entries()].map(([id, name]) => ({ id, name })).sort(sort),
    kbs:   [...kbs.entries()].map(([id, name]) => ({ id, name })).sort(sort),
    cats:  [...cats.entries()].map(([id, name]) => ({ id, name })).sort(sort),
  };
}

export default function AdminQaQualityPage() {
  const [items, setItems] = useState<AskLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [seed, setSeed] = useState<AskLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedLogId, setSelectedLogId] = useState<number | null>(null);
  const [detail, setDetail] = useState<AskLogDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [reviewLabelDraft, setReviewLabelDraft] = useState("");
  const [reviewNoteDraft, setReviewNoteDraft] = useState("");
  const [reviewSaving, setReviewSaving] = useState(false);
  const [expandedAnswers, setExpandedAnswers] = useState<Record<string, boolean>>({});
  const [filters, setFilters] = useState<QaPanelFilters>(DEFAULT_FILTERS);
  const [searchInput, setSearchInput] = useState("");

  const loadSeed = async () => {
    try { const r = await askApi.listLogs({ limit: 200 }); setSeed(r.items); } catch { setSeed([]); }
  };
  const loadLogs = async (f: QaPanelFilters) => {
    setLoading(true);
    try { const r = await askApi.listLogs(toLogListFilters(f)); setItems(r.items); setTotal(r.total); } finally { setLoading(false); }
  };
  useEffect(() => { void loadSeed(); }, []);
  useEffect(() => { void loadLogs(filters); }, [filters]);

  const loadDetail = (logId: number) => {
    setDetailLoading(true);
    setDetailError(null);
    setDetail(null);
    setReviewLabelDraft(""); setReviewNoteDraft("");
    setExpandedAnswers({});
    askApi.getLogDetail(logId).then((d) => {
      setDetail(d);
      setReviewLabelDraft(d.review_label || "");
      setReviewNoteDraft(d.review_note || "");
    }).catch((error) => {
      setDetailError(error instanceof Error ? error.message : "诊断详情加载失败");
    }).finally(() => setDetailLoading(false));
  };

  const summary = useMemo(() => {
    const n = items.length;
    const neg = items.filter((i) => i.feedback_value === "not_helpful").length;
    const ins = items.filter((i) => i.answer_status === "insufficient").length;
    const nh  = items.filter((i) => i.retrieval_status === "no_hits").length;
    const hl  = filters.highLatencyThresholdMs;
    const hlc = items.filter((i) => i.latency_ms != null && i.latency_ms >= hl).length;
    const avg = n > 0 ? (items.reduce((s, i) => s + (i.retrieved_count ?? 0), 0) / n).toFixed(1) : "0";
    return { total: n, negRate: n > 0 ? `${((neg / n) * 100).toFixed(1)}%` : "—",
      noHitsRate: n > 0 ? `${((nh / n) * 100).toFixed(1)}%` : "—",
      avgHits: avg, neg, nh, ins, hlc };
  }, [items, filters.highLatencyThresholdMs]);

  const filterOptions = useMemo(() => buildFilterOptions(seed.length > 0 ? seed : items), [items, seed]);
  const activeCount = [
    filters.teamId, filters.knowledgeBaseId, filters.categoryId,
    filters.answerStatus, filters.retrievalStatus, filters.feedbackValue,
    filters.startDate, filters.endDate, filters.queryKeyword.trim(),
    filters.zeroHitsOnly ? "1" : "", filters.highLatencyOnly ? "1" : "",
  ].filter(Boolean).length;

  const conclusion = detail ? deriveConclusion(detail) : null;

  const setFilter = <K extends keyof QaPanelFilters>(k: K, v: QaPanelFilters[K]) =>
    setFilters((f) => ({ ...f, [k]: v }));

  const saveReview = async () => {
    if (!detail) return;
    setReviewSaving(true);
    try {
      await askApi.reviewLog(detail.id, { review_label: reviewLabelDraft || null, review_note: reviewNoteDraft.trim() || null });
      const d = await askApi.getLogDetail(detail.id);
      setDetail(d);
      setReviewLabelDraft(d.review_label || ""); setReviewNoteDraft(d.review_note || "");
      void loadLogs(filters); void loadSeed();
    } catch {} finally { setReviewSaving(false); }
  };

  const closeDetail = () => {
    setSelectedLogId(null);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(false);
  };

  const toggleDoc = (id: string) =>
    setExpandedAnswers((p) => ({ ...p, [id]: !p[id] }));

  const expandAllDocs = () => {
    const map: Record<string, boolean> = {};
    detail?.retrieved_docs.forEach((_, i) => { map[`${i}`] = true; });
    setExpandedAnswers(map);
  };

  return (
    <div className="relative h-full overflow-hidden bg-slate-50">
      <div className="h-full overflow-y-auto px-5 py-6 sm:px-7">
        <div className="mx-auto max-w-5xl">

          {/* Header */}
          <div className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">问答质检</h1>
              <p className="mt-1.5 text-sm text-slate-500">定位知识缺口、检索问题与回答质量，追踪闭环改进。</p>
            </div>
            <span className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-500">
              共 {total} 条
            </span>
          </div>

          {/* Stats */}
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100">
                <MessageSquareText className="h-5 w-5 text-slate-500" />
              </div>
              <div><p className="text-2xl font-semibold text-slate-900">{summary.total}</p><p className="text-xs text-slate-400">当前结果</p></div>
            </div>
            <div className="flex items-center gap-3 rounded-2xl border border-amber-200 bg-white px-4 py-4 shadow-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50">
                <ThumbsDown className="h-5 w-5 text-amber-500" />
              </div>
              <div><p className="text-2xl font-semibold text-amber-700">{summary.negRate}</p><p className="text-xs text-slate-400">负反馈率</p></div>
            </div>
            <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50">
                <X className="h-5 w-5 text-rose-500" />
              </div>
              <div><p className="text-2xl font-semibold text-rose-700">{summary.noHitsRate}</p><p className="text-xs text-slate-400">未命中率</p></div>
            </div>
            <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
                <FileSearch className="h-5 w-5 text-blue-500" />
              </div>
              <div><p className="text-2xl font-semibold text-slate-900">{summary.avgHits}</p><p className="text-xs text-slate-400">平均命中数</p></div>
            </div>
          </div>

          {/* Filter panel */}
          <div className="sticky top-0 z-10 mt-5 rounded-2xl border border-slate-200 bg-white/95 px-5 py-4 shadow-sm backdrop-blur">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-800">筛选条件</h2>
                {activeCount > 0 && (
                  <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{activeCount} 个</span>
                )}
              </div>
              {activeCount > 0 && (
                <button type="button" onClick={() => { setFilters(DEFAULT_FILTERS); setSearchInput(""); }} className="text-xs text-slate-400 transition hover:text-slate-600">重置</button>
              )}
            </div>
            {/* Row 1: 5 dropdowns */}
            <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
              {[
                { label: "团队",     value: filters.teamId,         opts: filterOptions.teams, getLabel: (o: { id: number; name: string }) => o.name, getKey: (o: { id: number }) => String(o.id), placeholder: "全部团队" },
                { label: "知识库",   value: filters.knowledgeBaseId, opts: filterOptions.kbs,   getLabel: (o: { id: number; name: string }) => o.name, getKey: (o: { id: number }) => String(o.id), placeholder: "全部知识库" },
                { label: "分类",     value: filters.categoryId,       opts: filterOptions.cats,  getLabel: (o: { id: number; name: string }) => o.name, getKey: (o: { id: number }) => String(o.id), placeholder: "全部分类" },
                { label: "回答状态",  value: filters.answerStatus,      opts: Object.entries(ANSWER_CONFIG),    getLabel: ([, v]: [string, { label: string }]) => v.label,    getKey: ([k]: [string, { label: string }]) => k,    placeholder: "全部", static: true },
                { label: "检索状态",  value: filters.retrievalStatus,   opts: Object.entries(RETRIEVAL_CONFIG), getLabel: ([, v]: [string, { label: string }]) => v.label, getKey: ([k]: [string, { label: string }]) => k,   placeholder: "全部", static: true },
              ].map((col) => (
                <label key={col.label} className="flex flex-col gap-1">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">{col.label}</span>
                  <select
                    value={col.value}
                    onChange={(e) => setFilter(col.label === "团队" ? "teamId" as any : col.label === "知识库" ? "knowledgeBaseId" as any : col.label === "分类" ? "categoryId" as any : col.label === "回答状态" ? "answerStatus" as any : "retrievalStatus" as any, e.target.value as any)}
                    className="w-full cursor-pointer rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                  >
                    <option value="">{col.placeholder}</option>
                    {col.opts.map((o: any) => <option key={col.getKey(o)} value={col.getKey(o)}>{col.getLabel(o)}</option>)}
                  </select>
                </label>
              ))}
            </div>
            {/* Row 2: keyword + date + quick toggles */}
            <div className="mt-2 flex flex-wrap items-end gap-2">
              {/* Keyword */}
              <div className="flex min-w-0 flex-1 items-end gap-1.5">
                <div className="flex flex-1 flex-col gap-1">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">关键词</span>
                  <input
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") setFilters((f) => ({ ...f, queryKeyword: searchInput.trim() })); }}
                    placeholder="搜索问题内容…"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                  />
                </div>
                <button type="button" onClick={() => setFilters((f) => ({ ...f, queryKeyword: searchInput.trim() }))}
                  className="shrink-0 rounded-xl border border-slate-200 px-3 py-2 text-sm transition hover:bg-slate-50">搜索</button>
              </div>
              {/* Date */}
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">日期</span>
                <div className="flex items-center gap-1">
                  <input type="date" value={filters.startDate} onChange={(e) => setFilter("startDate", e.target.value)}
                    className="w-32 cursor-pointer rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-slate-400" />
                  <span className="text-slate-400">—</span>
                  <input type="date" value={filters.endDate} onChange={(e) => setFilter("endDate", e.target.value)}
                    className="w-32 cursor-pointer rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-slate-400" />
                </div>
              </div>
              {/* Toggles */}
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">快捷</span>
                <div className="flex items-center gap-1.5">
                  <button type="button" onClick={() => setFilter("zeroHitsOnly", !filters.zeroHitsOnly)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${filters.zeroHitsOnly ? "border-slate-800 bg-slate-800 text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}>命中=0</button>
                  <button type="button" onClick={() => setFilter("highLatencyOnly", !filters.highLatencyOnly)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${filters.highLatencyOnly ? "border-slate-800 bg-slate-800 text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}>高延迟</button>
                  <button type="button" onClick={() => setFilter("feedbackValue", filters.feedbackValue === "not_helpful" ? "" : "not_helpful")}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${filters.feedbackValue === "not_helpful" ? "border-amber-500 bg-amber-500 text-white" : "border-amber-200 bg-white text-amber-700 hover:bg-amber-50"}`}>
                    <ThumbsDown className="mr-1 inline h-3 w-3" />待改进
                  </button>
                  <span className="flex items-center gap-1 rounded-full border border-transparent px-2 py-1.5 text-xs text-slate-400">
                    阈值<input type="number" min={100} step={100} value={filters.highLatencyThresholdMs}
                      onChange={(e) => setFilter("highLatencyThresholdMs", Math.max(100, Number(e.target.value) || DEFAULT_LATENCY_THRESHOLD_MS))}
                      className="w-16 rounded-lg border border-slate-200 bg-white px-1.5 py-1 text-xs outline-none" />ms
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* List header */}
          <div className="mt-5 flex items-center justify-between text-xs text-slate-400">
            <p>显示 1–{items.length} 条，共 {total} 条</p>
            <p>按创建时间倒序</p>
          </div>

          {/* List */}
          <div className="mt-3 space-y-3">
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex gap-4"><div className="h-4 w-8 rounded bg-slate-100" /><div className="flex-1 space-y-2"><div className="h-4 w-3/4 rounded bg-slate-100" /><div className="h-3 w-full rounded bg-slate-50" /><div className="h-3 w-1/2 rounded bg-slate-50" /></div></div>
                </div>
              ))
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white py-16 text-sm text-slate-500">
                <MessageSquareText className="mb-3 h-8 w-8 text-slate-300" />暂无匹配的问答记录
              </div>
            ) : items.map((item, index) => {
              const ac  = getAnswerConfig(item.answer_status);
              const rc  = getRetrievalConfig(item.retrieval_status);
              const scope = formatScopePath(item);
              const hasReview = Boolean(item.review_label || item.suggested_review_label);
              const clamp  = shouldClampAnswer(item.answer_text);
              const exp    = Boolean(expandedAnswers[item.id]);
              return (
                <div key={item.id}
                  className={`cursor-pointer rounded-2xl border bg-white p-5 shadow-sm transition-all hover:border-slate-300 hover:shadow-md ${selectedLogId === item.id ? "border-blue-300 ring-1 ring-blue-100" : "border-slate-200"}`}
                  onClick={() => { setSelectedLogId(item.id); loadDetail(item.id); }}
                >
                  {/* Row 1: # | core badges | feedback | review label | meta */}
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <span className="shrink-0 text-xs font-medium text-slate-300">#{index + 1}</span>
                    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${ac.style}`}>
                      <span className="h-1.5 w-1.5 rounded-full bg-current" />{ac.label}
                    </span>
                    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${rc.style}`}>
                      <span className="h-1.5 w-1.5 rounded-full bg-current" />{rc.label}
                    </span>
                    <FeedbackBadge value={item.feedback_value} />
                    {item.review_label ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-slate-800 bg-slate-800 px-2 py-0.5 text-xs font-medium text-white">✓ {item.review_label}</span>
                    ) : item.suggested_review_label ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs text-slate-600">◆ {item.suggested_review_label}</span>
                    ) : null}
                    <span className="ml-auto text-[11px] text-slate-400">{scope}</span>
                    <span className="text-[11px] text-slate-400">{item.retrieved_count} 条</span>
                    <span className="text-[11px] text-slate-400">{formatLatency(item.latency_ms)}</span>
                    <span className="text-[11px] text-slate-400">{formatTime(item.created_at)}</span>
                  </div>
                  {/* Query */}
                  <p className="mt-3 truncate text-sm font-medium text-slate-800">{item.query}</p>
                  {/* Answer preview */}
                  <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-slate-500">{item.answer_text}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Detail drawer */}
      {selectedLogId && (
        <div className="absolute inset-0 z-20 flex">
          <div className="flex-1 bg-slate-900/15 backdrop-blur-[1px]" onClick={closeDetail} />
          <aside className="flex w-full max-w-3xl flex-col border-l border-slate-200 bg-white shadow-2xl">
            {/* Drawer header */}
            <div className="flex items-center justify-between gap-4 border-b border-slate-100 px-5 py-4">
              <div className="flex min-w-0 items-center gap-2.5">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-blue-50">
                  <SearchCheck className="h-4 w-4 text-blue-600" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-slate-400">问答诊断详情</p>
                  <p className="truncate text-sm font-semibold text-slate-800">
                    {items.find((i) => i.id === selectedLogId)?.query?.slice(0, 50) ?? `#${selectedLogId}`}
                  </p>
                </div>
              </div>
              <button type="button" onClick={closeDetail}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-400 transition hover:bg-slate-50 hover:text-slate-600">
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Drawer body */}
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
              {detailLoading ? (
                <div className="flex items-center gap-3 rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" />正在加载诊断详情…
                </div>
              ) : detailError ? (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-6 text-sm text-rose-700">
                  <p className="font-medium text-rose-900">诊断详情加载失败</p>
                  <p className="mt-1 leading-relaxed">{detailError}</p>
                </div>
              ) : detail && conclusion ? (
                <div className="space-y-4">

                  {/* 1. Diagnostic conclusion (TOP) */}
                  <div className={`rounded-2xl border p-4 ${CONCL_TONE[conclusion.tone]}`}>
                    <div className="mb-3 flex flex-wrap items-center gap-1.5">
                      <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${getAnswerConfig(detail.answer_status).style}`}>
                        <span className="h-1.5 w-1.5 rounded-full bg-current" />
                        {getAnswerConfig(detail.answer_status).label}
                      </span>
                      <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${getRetrievalConfig(detail.retrieval_status).style}`}>
                        <span className="h-1.5 w-1.5 rounded-full bg-current" />
                        {getRetrievalConfig(detail.retrieval_status).label}
                      </span>
                      <span className="inline-flex items-center gap-1 rounded-full border border-transparent bg-white/70 px-2 py-0.5 text-xs text-slate-600">
                        <Clock3 className="h-3 w-3" />{formatLatency(detail.latency_ms)}
                      </span>
                      <FeedbackBadge value={detail.feedback_value} />
                    </div>
                    <h3 className="text-base font-semibold text-inherit">诊断结论：{conclusion.title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed opacity-80">{conclusion.summary}</p>
                    <div className="mt-3 rounded-xl border border-white/40 bg-white/60 px-3 py-2.5 text-sm">
                      <span className="font-medium text-inherit">建议动作：</span>
                      <span className="ml-1 opacity-80">{conclusion.nextAction}</span>
                    </div>
                  </div>

                  {/* 2. Q&A + Scope (side by side) */}
                  <div className="grid gap-3 lg:grid-cols-2">
                    <div className="space-y-3">
                      <div className="rounded-xl border border-slate-200 bg-white p-4">
                        <div className="mb-2.5 flex items-center gap-2">
                          <MessageSquareText className="h-4 w-4 text-slate-400" />
                          <span className="text-xs font-semibold text-slate-700">用户问题</span>
                        </div>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{detail.query}</p>
                      </div>
                      <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                        <div className="mb-2.5 flex items-center gap-2">
                          <SearchCheck className="h-4 w-4 text-slate-400" />
                          <span className="text-xs font-semibold text-slate-700">最终答案</span>
                        </div>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-600">{detail.answer_text || "暂无回答"}</p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div className="rounded-xl border border-slate-200 bg-white p-4">
                        <div className="mb-3 flex items-center gap-2">
                          <BookOpenText className="h-4 w-4 text-slate-400" />
                          <span className="text-xs font-semibold text-slate-700">请求范围</span>
                        </div>
                        <InfoGrid items={[
                          { label: "团队",   value: detail.team_name || `ID ${detail.team_id}` },
                          { label: "知识库", value: detail.knowledge_base_name || `ID ${detail.knowledge_base_id}` },
                          { label: "分类",   value: detail.category_name || `ID ${detail.category_id}` },
                          { label: "会话",   value: detail.session_id },
                        ]} />
                      </div>
                      <div className="rounded-xl border border-slate-200 bg-white p-4">
                        <div className="mb-2.5 flex items-center gap-2">
                          <FileSearch className="h-4 w-4 text-slate-400" />
                          <span className="text-xs font-semibold text-slate-700">检索状态</span>
                        </div>
                        <div className="space-y-2">
                          <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs">
                            命中文档片段 <strong className="text-slate-800">{detail.retrieved_count}</strong> 条
                          </div>
                          <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-500">
                            {detail.retrieval_status_reason || "暂无说明"}
                          </div>
                          {detail.feedback_note && (
                            <div className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                              用户备注：{detail.feedback_note}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 3. QA label (button group) */}
                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-slate-400" />
                      <span className="text-xs font-semibold text-slate-700">质检标签</span>
                      {detail.suggested_review_label && !detail.review_label && (
                        <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] text-blue-600">
                          建议：{detail.suggested_review_label}
                        </span>
                      )}
                    </div>
                    <div className="mb-3 flex flex-wrap gap-1.5">
                      <button
                        type="button"
                        onClick={() => setReviewLabelDraft("")}
                        className={`rounded-full border px-2.5 py-1 text-xs transition ${!reviewLabelDraft ? "border-slate-800 bg-slate-800 text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
                      >
                        暂不标记
                      </button>
                      {QA_REVIEW_LABELS.map((label) => (
                        <button
                          key={label}
                          type="button"
                          onClick={() => setReviewLabelDraft(label)}
                          className={`rounded-full border px-2.5 py-1 text-xs transition ${reviewLabelDraft === label ? "border-blue-500 bg-blue-50 text-blue-700 ring-1 ring-blue-200" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <textarea
                      value={reviewNoteDraft}
                      onChange={(e) => setReviewNoteDraft(e.target.value)}
                      rows={3}
                      placeholder="补充判断依据，以及后续应该补文档、调检索还是调 Prompt…"
                      className="w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm leading-relaxed text-slate-800 outline-none transition focus:border-slate-400"
                    />
                    <div className="mt-2.5 flex items-center justify-between">
                      <p className="text-xs text-slate-400">
                        {detail.reviewed_at ? `已标记于 ${formatTime(detail.reviewed_at)}` : "尚未标记"}
                      </p>
                      <button
                        type="button"
                        disabled={reviewSaving}
                        onClick={() => void saveReview()}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
                      >
                        {reviewSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                        保存标签
                      </button>
                    </div>
                  </div>

                  {/* 4. Retrieval funnel (horizontal bars) */}
                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <Filter className="h-4 w-4 text-slate-400" />
                      <span className="text-xs font-semibold text-slate-700">检索过程</span>
                    </div>
                    <FunnelCard funnel={detail.retrieval_funnel} />
                    {(detail.retrieval_funnel?.rewritten_queries || detail.retrieval_queries).length > 0 && (
                      <div className="mt-3 space-y-1.5">
                        <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">改写查询</p>
                        {(detail.retrieval_funnel?.rewritten_queries || detail.retrieval_queries).map((q, i) => (
                          <div key={i} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs">
                            <span className="text-slate-700">{typeof q === "string" ? q : q.query}</span>
                            {typeof q !== "string" && (
                              <span className="rounded-full bg-white px-1.5 py-0.5 text-[10px] text-slate-500">{q.chunk_count} 召回</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* 5. Retrieved docs (expandable cards) */}
                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <BookOpenText className="h-4 w-4 text-slate-400" />
                        <span className="text-xs font-semibold text-slate-700">参考片段</span>
                        <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">{detail.retrieved_docs.length} 条</span>
                      </div>
                      {detail.retrieved_docs.length > 0 && (
                        <button type="button" onClick={expandAllDocs} className="text-xs text-blue-600 hover:text-blue-700">全部展开</button>
                      )}
                    </div>
                    {detail.retrieved_docs.length > 0 ? (
                      <div className="space-y-2">
                        {detail.retrieved_docs.map((doc, i) => (
                          <DocCard
                            key={`${doc.rank}-${i}`}
                            doc={doc}
                            expanded={Boolean(expandedAnswers[`${doc.rank}-${i}`])}
                            onToggle={() => toggleDoc(`${doc.rank}-${i}`)}
                          />
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400">暂无参考片段</p>
                    )}
                  </div>

                  {/* 6. Conversation context */}
                  {detail.conversation_context.length > 0 && (
                    <div className="rounded-xl border border-slate-200 bg-white p-4">
                      <div className="mb-3 flex items-center gap-2">
                        <MessageSquareText className="h-4 w-4 text-slate-400" />
                        <span className="text-xs font-semibold text-slate-700">会话上下文</span>
                      </div>
                      <div className="space-y-2">
                        {detail.conversation_context.map((msg, i) => (
                          <div key={i} className={`rounded-lg border px-3 py-2.5 ${msg.is_current_turn ? "border-emerald-200 bg-emerald-50/50" : "border-slate-100 bg-slate-50"}`}>
                            <div className="mb-1 flex items-center justify-between text-[10px] text-slate-400">
                              <span>{msg.role}</span><span>{formatTime(msg.created_at)}</span>
                            </div>
                            <p className="text-xs leading-relaxed text-slate-600">{msg.content}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 7. Technical details (collapsed) */}
                  <details className="group rounded-xl border border-slate-200 bg-white">
                    <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Braces className="h-4 w-4 text-slate-400" />
                        <span className="text-xs font-medium text-slate-500">技术细节</span>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] text-slate-400 transition group-open:bg-slate-800 group-open:text-white">展开</span>
                    </summary>
                    <div className="border-t border-slate-100 px-4 py-4">
                      <InfoGrid items={[
                        { label: "日志 ID", value: detail.id },
                        { label: "用户 ID", value: detail.user_id },
                        { label: "回答状态", value: detail.answer_status },
                        { label: "检索状态", value: detail.retrieval_status },
                        { label: "命中片段", value: detail.retrieved_count },
                        { label: "保留片段", value: detail.retrieved_docs.length },
                        { label: "反馈",    value: detail.feedback_value || "—" },
                        { label: "延迟",    value: formatLatency(detail.latency_ms) },
                      ]} />
                      {detail.answer_context && (
                        <div className="mt-3">
                          <p className="mb-2 text-xs font-medium text-slate-500">原始上下文</p>
                          <pre className="max-h-48 overflow-auto rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
                            {detail.answer_context}
                          </pre>
                        </div>
                      )}
                    </div>
                  </details>

                </div>
              ) : null}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
