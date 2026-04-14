"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Plus,
  Search,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  Upload,
  WandSparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  checkSensitiveWords,
  createSensitiveWord,
  deleteSensitiveWord,
  getSensitiveWordSettings,
  importSensitiveWords,
  listSensitiveWords,
  updateSensitiveWord,
  updateSensitiveWordSettings,
  type SensitiveWordCheckResult,
  type SensitiveWordItem,
  type SensitiveWordSettings,
} from "@/lib/api/sensitiveWords";
import { listTeams, type TeamItem } from "@/lib/api/teams";
import { isKbAdmin } from "@/lib/auth/roles";
import { getStoredUser } from "@/lib/auth/session";

type WordDraft = { word: string; category: string; enabled: boolean; remark: string };
type ImportDraft = { category: string; enabled: boolean; wordsText: string };

const EMPTY_WORD_DRAFT: WordDraft = { word: "", category: "", enabled: true, remark: "" };
const EMPTY_IMPORT_DRAFT: ImportDraft = { category: "", enabled: true, wordsText: "" };
const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
const SEARCH_DEBOUNCE_MS = 350;

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-slate-500">{label}</label>
      {children}
    </div>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function ScopeBadge({ team }: { team?: TeamItem | null }) {
  return (
    <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
      {team ? `团队级: ${team.name}` : "全局词库"}
    </span>
  );
}

function PaginationBar(props: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(props.total / props.pageSize));
  const start = props.total === 0 ? 0 : (props.page - 1) * props.pageSize + 1;
  const end = Math.min(props.total, props.page * props.pageSize);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-5 py-4">
      <div className="text-xs text-slate-400">
        {props.total === 0 ? "暂无数据" : `显示 ${start}-${end} / ${props.total}`}
      </div>
      <div className="flex items-center gap-2">
        <select
          value={props.pageSize}
          onChange={(e) => props.onPageSizeChange(Number(e.target.value))}
          className="h-9 rounded-xl border border-slate-200 bg-white px-3 text-xs outline-none transition focus:border-slate-400"
        >
          {PAGE_SIZE_OPTIONS.map((option) => (
            <option key={option} value={option}>
              每页 {option} 条
            </option>
          ))}
        </select>
        <div className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white p-1">
          <button
            type="button"
            disabled={props.page <= 1}
            onClick={() => props.onPageChange(props.page - 1)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="px-2 text-xs text-slate-500">
            第 {props.page} / {totalPages} 页
          </span>
          <button
            type="button"
            disabled={props.page >= totalPages}
            onClick={() => props.onPageChange(props.page + 1)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AdminSensitiveWordsPage() {
  const currentUser = getStoredUser();
  const canEdit = isKbAdmin(currentUser?.role);
  const [teams, setTeams] = useState<TeamItem[]>([]);
  const [selectedScope, setSelectedScope] = useState("global");
  const [settings, setSettings] = useState<SensitiveWordSettings>({ enabled: true, block_query: true, block_document_publish: false });
  const [words, setWords] = useState<SensitiveWordItem[]>([]);
  const [totalWords, setTotalWords] = useState(0);
  const [enabledWords, setEnabledWords] = useState(0);
  const [disabledWords, setDisabledWords] = useState(0);
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [savingWord, setSavingWord] = useState(false);
  const [deletingWordId, setDeletingWordId] = useState<number | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<number | null>(null);
  const [checking, setChecking] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [debouncedKeyword, setDebouncedKeyword] = useState("");
  const [enabledFilter, setEnabledFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<SensitiveWordItem | null>(null);
  const [draft, setDraft] = useState<WordDraft>(EMPTY_WORD_DRAFT);
  const [importDraft, setImportDraft] = useState<ImportDraft>(EMPTY_IMPORT_DRAFT);
  const [checkText, setCheckText] = useState("");
  const [checkResult, setCheckResult] = useState<SensitiveWordCheckResult | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const selectedTeamId = selectedScope === "global" ? null : Number(selectedScope);
  const selectedTeam = useMemo(() => teams.find((item) => item.id === selectedTeamId) ?? null, [selectedTeamId, teams]);
  const summary = useMemo(
    () => ({ total: totalWords, enabledCount: enabledWords, disabledCount: disabledWords }),
    [disabledWords, enabledWords, totalWords],
  );
  const totalPages = Math.max(1, Math.ceil(totalWords / pageSize));

  async function loadScopeData(teamId: number | null, nextKeyword: string, nextEnabledFilter: string) {
    setLoading(true);
    try {
      const [nextSettings, nextWords] = await Promise.all([
        getSensitiveWordSettings(teamId),
        listSensitiveWords({
          teamId,
          keyword: nextKeyword.trim() || undefined,
          enabled: nextEnabledFilter === "all" ? null : nextEnabledFilter === "enabled",
          page,
          pageSize,
        }),
      ]);
      setSettings(nextSettings);
      setWords(nextWords.items);
      setTotalWords(nextWords.total);
      setEnabledWords(nextWords.enabled_count);
      setDisabledWords(nextWords.disabled_count);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载敏感词配置失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedKeyword(keyword), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [keyword]);

  useEffect(() => {
    const loadInitial = async () => {
      try {
        setTeams(await listTeams());
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "加载团队列表失败");
      }
    };
    void loadInitial();
  }, []);

  useEffect(() => {
    setPage(1);
    setPendingDeleteId(null);
  }, [selectedTeamId, debouncedKeyword, enabledFilter]);

  useEffect(() => {
    void loadScopeData(selectedTeamId, debouncedKeyword, enabledFilter);
  }, [selectedTeamId, debouncedKeyword, enabledFilter, page, pageSize]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const openCreate = () => {
    setDraft(EMPTY_WORD_DRAFT);
    setEditingItem(null);
    setCreateOpen(true);
  };

  const openEdit = (item: SensitiveWordItem) => {
    setEditingItem(item);
    setDraft({ word: item.word, category: item.category || "", enabled: item.enabled, remark: item.remark || "" });
    setCreateOpen(true);
  };

  const closeModal = () => {
    setCreateOpen(false);
    setEditingItem(null);
    setDraft(EMPTY_WORD_DRAFT);
  };

  const handleSaveSettings = async () => {
    if (!canEdit) return;
    setSavingSettings(true);
    try {
      const next = await updateSensitiveWordSettings(
        { enabled: settings.enabled, block_query: settings.block_query, block_document_publish: settings.block_document_publish },
        selectedTeamId,
      );
      setSettings(next);
      toast.success("策略配置已保存");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存策略失败");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleSaveWord = async () => {
    if (!canEdit) return;
    if (!draft.word.trim()) {
      toast.error("请先填写敏感词");
      return;
    }
    setSavingWord(true);
    try {
      if (editingItem) {
        await updateSensitiveWord(editingItem.id, {
          word: draft.word.trim(),
          category: draft.category.trim() || null,
          enabled: draft.enabled,
          remark: draft.remark.trim() || null,
        });
        toast.success("敏感词已更新");
      } else {
        await createSensitiveWord({
          team_id: selectedTeamId,
          word: draft.word.trim(),
          category: draft.category.trim() || null,
          enabled: draft.enabled,
          remark: draft.remark.trim() || null,
        });
        toast.success("敏感词已创建");
      }
      closeModal();
      await loadScopeData(selectedTeamId, debouncedKeyword, enabledFilter);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存敏感词失败");
    } finally {
      setSavingWord(false);
    }
  };

  const handleDelete = async (item: SensitiveWordItem) => {
    if (!canEdit) return;
    setDeletingWordId(item.id);
    try {
      await deleteSensitiveWord(item.id);
      toast.success("敏感词已删除");
      setPendingDeleteId(null);
      await loadScopeData(selectedTeamId, debouncedKeyword, enabledFilter);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除敏感词失败");
    } finally {
      setDeletingWordId(null);
    }
  };

  const handleImport = async () => {
    if (!canEdit) return;
    if (!importDraft.wordsText.trim()) {
      toast.error("请先输入待导入词条");
      return;
    }
    setSavingWord(true);
    try {
      const result = await importSensitiveWords({
        team_id: selectedTeamId,
        words_text: importDraft.wordsText,
        category: importDraft.category.trim() || null,
        enabled: importDraft.enabled,
      });
      toast.success(`导入完成，新增 ${result.created_count} 条，跳过 ${result.skipped_count} 条`);
      setImportDraft(EMPTY_IMPORT_DRAFT);
      setImportOpen(false);
      await loadScopeData(selectedTeamId, debouncedKeyword, enabledFilter);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "批量导入失败");
    } finally {
      setSavingWord(false);
    }
  };

  const handleCheck = async () => {
    if (!checkText.trim()) {
      toast.error("请先输入要检测的文本");
      return;
    }
    setChecking(true);
    try {
      setCheckResult(await checkSensitiveWords({ text: checkText, team_id: selectedTeamId, scene: "query" }));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "检测失败");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="px-6 py-8 sm:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-900">敏感词管理</h1>
            <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-500">
              管理全局和团队级敏感词词库，控制问答输入拦截策略。当前规则会统一作用于
              `/ask`、`/kb-chat` 和后台问答预览入口。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <ScopeBadge team={selectedTeam} />
            {!canEdit && (
              <span className="rounded-full bg-amber-50 px-3 py-1 text-xs text-amber-700">当前账号为只读</span>
            )}
          </div>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-[1.3fr_1fr]">
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-slate-900">作用域与策略</p>
                <p className="mt-1 text-xs leading-6 text-slate-500">
                  可分别维护全局词库和团队词库，团队级配置适合补充更细的业务限制。
                </p>
              </div>
              <select
                value={selectedScope}
                onChange={(e) => setSelectedScope(e.target.value)}
                className="h-10 min-w-[220px] rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-slate-400"
              >
                <option value="global">全局词库</option>
                {teams.map((team) => (
                  <option key={team.id} value={String(team.id)}>
                    {team.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <div className="rounded-2xl bg-slate-50 px-4 py-4">
                <p className="text-xs text-slate-500">词条总数</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">{summary.total}</p>
              </div>
              <div className="rounded-2xl bg-emerald-50 px-4 py-4">
                <p className="text-xs text-emerald-600">启用中</p>
                <p className="mt-2 text-2xl font-semibold text-emerald-700">{summary.enabledCount}</p>
              </div>
              <div className="rounded-2xl bg-slate-100 px-4 py-4">
                <p className="text-xs text-slate-500">停用中</p>
                <p className="mt-2 text-2xl font-semibold text-slate-700">{summary.disabledCount}</p>
              </div>
            </div>

            <div className="mt-5 grid gap-3 rounded-2xl border border-slate-200 p-4 md:grid-cols-3">
              <label className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={settings.enabled}
                  onChange={(e) => setSettings((prev) => ({ ...prev, enabled: e.target.checked }))}
                  disabled={!canEdit}
                />
                启用敏感词能力
              </label>
              <label className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={settings.block_query}
                  onChange={(e) => setSettings((prev) => ({ ...prev, block_query: e.target.checked }))}
                  disabled={!canEdit}
                />
                拦截问答输入
              </label>
              <label className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={settings.block_document_publish}
                  onChange={(e) =>
                    setSettings((prev) => ({ ...prev, block_document_publish: e.target.checked }))
                  }
                  disabled={!canEdit}
                />
                拦截文档发布
              </label>
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-slate-400">最近更新：{formatDate(settings.updated_at || settings.created_at)}</p>
              {canEdit && (
                <Button type="button" className="gap-2 rounded-2xl" disabled={savingSettings} onClick={() => void handleSaveSettings()}>
                  {savingSettings ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                  保存策略
                </Button>
              )}
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-50">
                <WandSparkles className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900">文本试拦截</p>
                <p className="mt-1 text-xs leading-6 text-slate-500">用当前作用域规则预检测一段文本，快速确认是否会被问答入口拦截。</p>
              </div>
            </div>
            <textarea
              value={checkText}
              onChange={(e) => setCheckText(e.target.value)}
              rows={6}
              placeholder="输入一段文本进行检测"
              className="mt-4 w-full resize-none rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-slate-400"
            />
            <div className="mt-4 flex items-center justify-between gap-3">
              <Button type="button" variant="outline" className="gap-2 rounded-2xl" disabled={checking} onClick={() => void handleCheck()}>
                {checking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                立即检测
              </Button>
              {checkResult && (
                <span className={`rounded-full px-3 py-1 text-xs ${checkResult.blocked ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"}`}>
                  {checkResult.blocked ? "将被拦截" : "可正常通过"}
                </span>
              )}
            </div>
            {checkResult && (
              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                <p className="font-medium text-slate-900">{checkResult.blocked ? "命中敏感词" : "未命中敏感词"}</p>
                <p className="mt-2 text-xs leading-6 text-slate-500">{checkResult.reason || "当前文本未命中规则"}</p>
                {checkResult.matched_words.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {checkResult.matched_words.map((word) => (
                      <span key={word} className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-700 ring-1 ring-slate-200">
                        {word}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>
        </div>

        <section className="mt-6 rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-4">
            <div className="relative min-w-[260px] flex-1">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="搜索敏感词或分类"
                className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50/60 pl-10 pr-20 text-sm outline-none transition focus:border-slate-300 focus:bg-white"
              />
              {keyword !== debouncedKeyword && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400">搜索中...</div>
              )}
            </div>
            <select
              value={enabledFilter}
              onChange={(e) => setEnabledFilter(e.target.value)}
              className="h-10 min-w-[130px] rounded-xl border border-slate-200 bg-slate-50/60 px-3 text-sm outline-none transition focus:border-slate-300 focus:bg-white"
            >
              <option value="all">全部状态</option>
              <option value="enabled">仅启用</option>
              <option value="disabled">仅停用</option>
            </select>
            {canEdit && (
              <>
                <Button type="button" variant="outline" className="gap-2 rounded-2xl" onClick={() => setImportOpen(true)}>
                  <Upload className="h-4 w-4" />
                  批量导入
                </Button>
                <Button type="button" className="gap-2 rounded-2xl" onClick={openCreate}>
                  <Plus className="h-4 w-4" />
                  新增词条
                </Button>
              </>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left">
                  <th className="px-5 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">词条</th>
                  <th className="px-5 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">分类</th>
                  <th className="px-5 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">状态</th>
                  <th className="px-5 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">备注</th>
                  <th className="px-5 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">更新时间</th>
                  <th className="px-5 py-3 text-xs font-medium uppercase tracking-wider text-slate-400">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-12 text-center text-sm text-slate-400">正在加载敏感词配置...</td>
                  </tr>
                ) : words.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-14 text-center">
                      <div className="mx-auto flex max-w-xs flex-col items-center">
                        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100">
                          <ShieldAlert className="h-6 w-6 text-slate-400" />
                        </div>
                        <p className="mt-4 font-medium text-slate-700">当前筛选结果为空</p>
                        <p className="mt-1 text-sm text-slate-400">
                          {canEdit ? "可以新增词条、调整筛选条件，或切换到其他作用域。" : "可以调整筛选条件，或等待管理员配置。"}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  words.map((item) => {
                    const confirmingDelete = pendingDeleteId === item.id;
                    const deleting = deletingWordId === item.id;
                    return (
                      <tr key={item.id} className="hover:bg-slate-50/60">
                        <td className="px-5 py-4">
                          <div>
                            <p className="font-medium text-slate-900">{item.word}</p>
                            <p className="mt-1 text-xs text-slate-400">{item.normalized_word}</p>
                          </div>
                        </td>
                        <td className="px-5 py-4 text-slate-600">{item.category || "未分类"}</td>
                        <td className="px-5 py-4">
                          <span className={`rounded-full px-2.5 py-1 text-xs ${item.enabled ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
                            {item.enabled ? "启用" : "停用"}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-slate-500">{item.remark || "-"}</td>
                        <td className="px-5 py-4 text-xs text-slate-400">{formatDate(item.updated_at)}</td>
                        <td className="px-5 py-4">
                          {confirmingDelete ? (
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-1 text-xs text-rose-700">
                                <AlertTriangle className="h-3.5 w-3.5" />
                                确认删除？
                              </span>
                              <Button type="button" variant="destructive" className="h-8 rounded-xl px-3 text-xs" disabled={deleting} onClick={() => void handleDelete(item)}>
                                {deleting ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Trash2 className="mr-1 h-3.5 w-3.5" />}
                                删除
                              </Button>
                              <Button type="button" variant="outline" className="h-8 rounded-xl px-3 text-xs" disabled={deleting} onClick={() => setPendingDeleteId(null)}>
                                取消
                              </Button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              <Button type="button" variant="outline" className="h-8 rounded-xl px-3 text-xs" onClick={() => openEdit(item)} disabled={!canEdit}>
                                编辑
                              </Button>
                              <Button type="button" variant="destructive" className="h-8 rounded-xl px-3 text-xs" onClick={() => setPendingDeleteId(item.id)} disabled={!canEdit}>
                                <Trash2 className="mr-1 h-3.5 w-3.5" />
                                删除
                              </Button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          <PaginationBar
            page={page}
            pageSize={pageSize}
            total={totalWords}
            onPageChange={setPage}
            onPageSizeChange={(nextPageSize) => {
              setPageSize(nextPageSize);
              setPage(1);
            }}
          />
        </section>

        {createOpen && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
            onClick={(e) => {
              if (e.target === e.currentTarget) closeModal();
            }}
          >
            <div className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white shadow-2xl">
              <div className="flex items-start justify-between border-b border-slate-100 px-6 py-5">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">{editingItem ? "编辑敏感词" : "新增敏感词"}</h2>
                  <div className="mt-2">
                    <ScopeBadge team={selectedTeam} />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={closeModal}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="space-y-4 px-6 py-5">
                <FormField label="敏感词">
                  <input
                    value={draft.word}
                    onChange={(e) => setDraft((prev) => ({ ...prev, word: e.target.value }))}
                    placeholder="例如：内部路线图"
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none transition focus:border-slate-400"
                  />
                </FormField>
                <FormField label="分类">
                  <input
                    value={draft.category}
                    onChange={(e) => setDraft((prev) => ({ ...prev, category: e.target.value }))}
                    placeholder="例如：商业机密"
                    className="h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none transition focus:border-slate-400"
                  />
                </FormField>
                <FormField label="备注">
                  <textarea
                    value={draft.remark}
                    onChange={(e) => setDraft((prev) => ({ ...prev, remark: e.target.value }))}
                    rows={3}
                    placeholder="补充说明"
                    className="w-full resize-none rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none transition focus:border-slate-400"
                  />
                </FormField>
                <label className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={draft.enabled}
                    onChange={(e) => setDraft((prev) => ({ ...prev, enabled: e.target.checked }))}
                  />
                  保存后立即启用
                </label>
              </div>
              <div className="flex items-center justify-end gap-3 border-t border-slate-100 px-6 py-4">
                <Button type="button" variant="outline" className="rounded-xl" onClick={closeModal}>
                  取消
                </Button>
                <Button type="button" className="gap-2 rounded-xl" disabled={savingWord} onClick={() => void handleSaveWord()}>
                  {savingWord && <Loader2 className="h-4 w-4 animate-spin" />}
                  保存
                </Button>
              </div>
            </div>
          </div>
        )}

        {importOpen && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                setImportOpen(false);
                setImportDraft(EMPTY_IMPORT_DRAFT);
              }
            }}
          >
            <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white shadow-2xl">
              <div className="flex items-start justify-between border-b border-slate-100 px-6 py-5">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">批量导入敏感词</h2>
                  <p className="mt-1 text-xs text-slate-400">每行一个词条，导入时会自动去重。</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setImportOpen(false);
                    setImportDraft(EMPTY_IMPORT_DRAFT);
                  }}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="space-y-4 px-6 py-5">
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField label="分类">
                    <input
                      value={importDraft.category}
                      onChange={(e) => setImportDraft((prev) => ({ ...prev, category: e.target.value }))}
                      placeholder="例如：合规"
                      className="h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none transition focus:border-slate-400"
                    />
                  </FormField>
                  <label className="mt-6 flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={importDraft.enabled}
                      onChange={(e) => setImportDraft((prev) => ({ ...prev, enabled: e.target.checked }))}
                    />
                    导入后启用
                  </label>
                </div>
                <FormField label="词条内容">
                  <textarea
                    value={importDraft.wordsText}
                    onChange={(e) => setImportDraft((prev) => ({ ...prev, wordsText: e.target.value }))}
                    rows={10}
                    placeholder={"内部路线图\n客户手机号\n未公开报价"}
                    className="w-full resize-none rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-slate-400"
                  />
                </FormField>
              </div>
              <div className="flex items-center justify-end gap-3 border-t border-slate-100 px-6 py-4">
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-xl"
                  onClick={() => {
                    setImportOpen(false);
                    setImportDraft(EMPTY_IMPORT_DRAFT);
                  }}
                >
                  取消
                </Button>
                <Button type="button" className="gap-2 rounded-xl" disabled={savingWord} onClick={() => void handleImport()}>
                  {savingWord && <Loader2 className="h-4 w-4 animate-spin" />}
                  开始导入
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
