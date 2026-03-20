"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight } from "lucide-react";
import { listCollections, type CollectionWithCount } from "@/lib/api/collections";
import { reindexAll } from "@/lib/api/documents";
import { Toaster, toast } from "sonner";

const API_BASE =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) ||
  "http://localhost:8000";

const PASS_SCORE = 0.75;

interface IterationRecord {
  round: number;
  question: string;
  original_question?: string;
  answer: string;
  score: number;
  passed: boolean;
  reason?: string;
  suggestion?: string;
}

interface RetrievedDoc {
  content: string;
  metadata?: {
    document_id?: number;
    document_title?: string;
    chunk_index?: number;
    score?: number;
    rerank_score?: number;
  };
}

interface DocumentIssue {
  round?: number;
  type?: string;
  document_title?: string; // 需修改的文档名，LLM 从【文档：xxx】中指定
  description?: string;
  modification_suggestion?: string;
}

interface QAResult {
  answer: string;
  confidence_score: number;
  iteration: number;
  retrieved_docs: RetrievedDoc[];
  iteration_history: IterationRecord[];
  document_issues?: DocumentIssue[];
}

/** 从 retrieved_docs 提取去重文档名列表 */
function getUniqueDocumentNames(docs: RetrievedDoc[]): string[] {
  const names = new Map<number, string>();
  docs.forEach((d) => {
    const id = d.metadata?.document_id;
    const title = d.metadata?.document_title;
    if (id != null && title && !names.has(id)) {
      names.set(id, title);
    }
  });
  return Array.from(names.values());
}

/** 获取该轮关联的 document_issues */
function getRoundDocumentIssues(
  round: number,
  documentIssues: DocumentIssue[]
): DocumentIssue[] {
  if (!documentIssues?.length) return [];
  return documentIssues.filter((i) => i.round === round);
}

export default function QAPage() {
  const [query, setQuery] = useState("");
  const [maxIterations, setMaxIterations] = useState(3);
  const [collectionId, setCollectionId] = useState<number | null>(null);
  const [collections, setCollections] = useState<CollectionWithCount[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QAResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);

  const loadCollections = useCallback(async () => {
    try {
      const list = await listCollections();
      setCollections(list);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadCollections();
  }, [loadCollections]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE}/api/v1/qa/invoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          max_iterations: maxIterations,
          collection_id: collectionId && collectionId > 0 ? collectionId : null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "请求失败");
      }

      setResult({
        answer: data.answer,
        confidence_score: data.confidence_score,
        iteration: data.iteration,
        retrieved_docs: data.retrieved_docs || [],
        iteration_history: data.iteration_history || [],
        document_issues: data.document_issues || [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "发生错误，请重试");
    } finally {
      setLoading(false);
    }
  };

  const docNames = result ? getUniqueDocumentNames(result.retrieved_docs) : [];

  /** 折叠状态：Set 中为展开的轮次，默认全展开 */
  const [expandedRounds, setExpandedRounds] = useState<Set<number>>(new Set());
  useEffect(() => {
    if (result?.iteration_history?.length) {
      setExpandedRounds(new Set(result.iteration_history.map((r) => r.round)));
    }
  }, [result?.iteration_history]);
  const toggleRound = (round: number) => {
    setExpandedRounds((prev) => {
      const next = new Set(prev);
      if (next.has(round)) next.delete(round);
      else next.add(round);
      return next;
    });
  };
  const expandAll = () => {
    if (result?.iteration_history?.length) {
      setExpandedRounds(new Set(result.iteration_history.map((r) => r.round)));
    }
  };
  const collapseAll = () => setExpandedRounds(new Set());

  const handleReindex = async () => {
    setReindexing(true);
    try {
      const res = await reindexAll();
      toast.success(res.message || `已重索引 ${res.indexed} 篇文档`);
      if (res.indexed > 0) {
        toast.info("请重新提问以获取检索结果");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "重建索引失败");
    } finally {
      setReindexing(false);
    }
  };

  return (
    <div className="min-h-full flex flex-col bg-gray-50">
      <Toaster position="top-right" />
      <div className="bg-white border-b px-6 py-4 shrink-0">
        <h1 className="text-2xl font-bold text-gray-900">迭代问答</h1>
        <p className="text-sm text-gray-500 mt-1">
          知识库 Q&A，自动优化提问与答案质量
        </p>
      </div>

      <div className="flex-1 grid grid-cols-2 gap-4 p-4 min-h-0">
        {/* 左侧：输入 + 迭代历史 */}
        <div className="flex flex-col gap-4 min-h-0 overflow-hidden">
          <Card className="shrink-0">
            <CardHeader>
              <CardTitle className="text-base">输入问题</CardTitle>
              <p className="text-xs text-gray-500">
                支持复杂问题，系统会自动优化与迭代
              </p>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-3">
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="w-full p-3 border rounded-lg text-sm min-h-[100px] resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="例如：智友前端开发规范中组件命名的要求是什么？"
                  disabled={loading}
                />
                <div className="flex gap-3 flex-wrap">
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-gray-500">检索集合</label>
                    <select
                      value={collectionId ?? ""}
                      onChange={(e) =>
                        setCollectionId(
                          e.target.value ? Number(e.target.value) : null
                        )
                      }
                      className="text-sm border rounded px-2 py-1 min-w-[120px]"
                      disabled={loading}
                    >
                      <option value="">全部知识库</option>
                      {collections.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} ({c.document_count})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-gray-500">最大轮次</label>
                    <select
                      value={maxIterations}
                      onChange={(e) =>
                        setMaxIterations(Number(e.target.value))
                      }
                      className="text-sm border rounded px-2 py-1"
                      disabled={loading}
                    >
                      {[1, 2, 3, 4, 5].map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="submit"
                    disabled={loading || !query.trim()}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
                  >
                    {loading ? "处理中..." : "提问"}
                  </button>
                </div>
              </form>
            </CardContent>
          </Card>

          <Card className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">迭代历史</CardTitle>
                {result?.iteration_history?.length ? (
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs h-7"
                      onClick={expandAll}
                    >
                      全部展开
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs h-7"
                      onClick={collapseAll}
                    >
                      全部折叠
                    </Button>
                  </div>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto pt-0">
              {!result && !loading && (
                <p className="text-sm text-gray-400 py-8 text-center">
                  提问后将显示每轮迭代记录
                </p>
              )}
              {loading && (
                <p className="text-sm text-gray-500 py-8 text-center">
                  正在检索与评估…
                </p>
              )}
              {result?.iteration_history?.length ? (
                <div className="space-y-4">
                  {result.iteration_history.map((r, idx) =>
                    r.passed ? (
                      /* 达标轮次 */
                      <div
                        key={r.round}
                        className="relative rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50/80 to-white shadow-sm overflow-hidden"
                      >
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-emerald-500" />
                        <div className="pl-4 pr-4 py-3">
                          <button
                            type="button"
                            onClick={() => toggleRound(r.round)}
                            className="flex w-full items-center justify-between gap-2 mb-0 text-left hover:opacity-90 transition-opacity"
                          >
                            <span className="flex items-center gap-1.5 text-sm font-semibold text-emerald-800">
                              {expandedRounds.has(r.round) ? (
                                <ChevronDown className="h-4 w-4 shrink-0" />
                              ) : (
                                <ChevronRight className="h-4 w-4 shrink-0" />
                              )}
                              第 {r.round} 轮
                            </span>
                            <Badge className="bg-emerald-600 hover:bg-emerald-600 shrink-0">
                              ✓ 达标 {r.score.toFixed(2)}
                            </Badge>
                          </button>
                          {expandedRounds.has(r.round) ? (
                            <div className="mt-3">
                              <div className="rounded-lg bg-white/70 px-3 py-2 mb-3">
                                <p className="text-xs text-emerald-700/80 mb-0.5">问题</p>
                                <p className="text-sm text-gray-800 select-text leading-relaxed">
                                  {r.question}
                                </p>
                              </div>
                              <div className="rounded-lg bg-white/60 px-3 py-2">
                                <p className="text-xs text-emerald-700/80 mb-1">答案</p>
                                <p className="text-sm text-gray-700 whitespace-pre-wrap select-text leading-relaxed">
                                  {r.answer}
                                </p>
                              </div>
                            </div>
                          ) : (
                            <p className="text-xs text-emerald-600 truncate mt-2">{r.question}</p>
                          )}
                        </div>
                      </div>
                    ) : (
                      /* 未达标轮次 */
                      <div
                        key={r.round}
                        className="relative rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50/60 to-white shadow-sm overflow-hidden"
                      >
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-amber-500" />
                        <div className="pl-4 pr-4 py-3">
                          <button
                            type="button"
                            onClick={() => toggleRound(r.round)}
                            className="flex w-full items-center justify-between gap-2 mb-0 text-left hover:opacity-90 transition-opacity"
                          >
                            <span className="flex items-center gap-1.5 text-sm font-semibold text-amber-800">
                              {expandedRounds.has(r.round) ? (
                                <ChevronDown className="h-4 w-4 shrink-0" />
                              ) : (
                                <ChevronRight className="h-4 w-4 shrink-0" />
                              )}
                              第 {r.round} 轮
                            </span>
                            <Badge variant="secondary" className="bg-amber-100 text-amber-800 border-amber-200 shrink-0">
                              未达标 {r.score.toFixed(2)}
                            </Badge>
                          </button>
                          {expandedRounds.has(r.round) ? (
                            <div className="mt-3">
                          <div className="rounded-lg bg-white/80 px-3 py-2 mb-3 border border-amber-100">
                            <p className="text-xs text-amber-700 mb-0.5 font-medium">问题</p>
                            <p className="text-sm text-gray-800 select-text leading-relaxed">{r.question}</p>
                          </div>

                          {docNames.length > 0 && (
                            <div className="mb-3">
                              <p className="text-xs text-amber-700 font-medium mb-1.5">引用的文档</p>
                              <div className="flex flex-wrap gap-1.5">
                                {docNames.map((name, i) => (
                                  <span
                                    key={i}
                                    className="inline-flex items-center px-2 py-0.5 rounded-md bg-amber-100/80 text-amber-800 text-xs"
                                  >
                                    {name}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          <div>
                            <p className="text-xs text-amber-700 font-medium mb-2">修改建议</p>
                            <div className="space-y-2">
                              {r.reason && (
                                <div className="rounded-lg bg-white/80 px-3 py-2 border border-amber-100">
                                  <p className="text-xs text-amber-700/80 mb-0.5">未通过原因</p>
                                  <p className="text-sm text-gray-700 select-text">{r.reason}</p>
                                </div>
                              )}
                              {r.suggestion && (
                                <div className="rounded-lg bg-white/80 px-3 py-2 border border-amber-100">
                                  <p className="text-xs text-amber-700/80 mb-0.5">补充建议</p>
                                  <p className="text-sm text-gray-700 select-text">{r.suggestion}</p>
                                </div>
                              )}
                              {getRoundDocumentIssues(
                                r.round,
                                result.document_issues ?? []
                              ).map((issue, i) => (
                                <div
                                  key={i}
                                  className="rounded-lg border-l-2 border-l-amber-400 bg-white/90 px-3 py-2 shadow-sm"
                                >
                                  {issue.document_title && (
                                    <p className="text-xs font-semibold text-amber-800 mb-1">
                                      📄 {issue.document_title}
                                    </p>
                                  )}
                                  {issue.description && (
                                    <p className="text-sm text-gray-700 mb-1 select-text">
                                      {issue.description}
                                    </p>
                                  )}
                                  {issue.modification_suggestion && (
                                    <p className="text-sm text-amber-700/90 italic select-text">
                                      → {issue.modification_suggestion}
                                    </p>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                          ) : (
                            <p className="text-xs text-amber-600 line-clamp-1 mt-2">{r.question}</p>
                          )}
                        </div>
                      </div>
                    )
                  )}
                </div>
              ) : result && !result.iteration_history?.length ? (
                <p className="text-sm text-gray-400 py-4">暂无迭代记录</p>
              ) : null}
            </CardContent>
          </Card>
        </div>

        {/* 右侧：评估摘要 + 最终答案 + 引用的文档 */}
        <div className="flex flex-col gap-4 min-h-0 overflow-hidden">
          <Card className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">最终答案</CardTitle>
                {result && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs h-7"
                    onClick={() => {
                      void navigator.clipboard
                        .writeText(result.answer)
                        .then(() => toast.success("已复制答案"));
                    }}
                  >
                    复制答案
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto pt-0">
              {error && (
                <p className="text-sm text-red-600 py-4">{error}</p>
              )}
              {result && (
                <>
                  <div className="rounded-lg bg-gray-50 p-3 mb-4 text-sm">
                    <p className="font-medium text-gray-700 mb-2">
                      【评估摘要】
                    </p>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-gray-600">
                      <span>迭代次数：{result.iteration} 轮</span>
                      <span>最终得分：{result.confidence_score.toFixed(2)}</span>
                      <span>达标分数：{PASS_SCORE}</span>
                      <span>
                        状态：
                        {result.confidence_score >= PASS_SCORE ? (
                          <span className="text-green-600 font-medium">
                            达标 ✓
                          </span>
                        ) : (
                          <span className="text-amber-600 font-medium">
                            未达标
                          </span>
                        )}
                      </span>
                    </div>
                  </div>
                  <div className="prose prose-sm max-w-none">
                    <p className="whitespace-pre-wrap text-gray-700">
                      {result.answer}
                    </p>
                  </div>
                </>
              )}
              {!result && !loading && !error && (
                <p className="text-sm text-gray-400 py-8">
                  答案将显示在这里
                </p>
              )}
            </CardContent>
          </Card>

          {result && (
            <Card className="shrink-0">
              <CardHeader className="py-3">
                <CardTitle className="text-sm">
                  引用的文档 ({docNames.length} 个)
                  {docNames.length === 0 && (
                    <span className="ml-2 text-amber-600 font-normal">
                      未检索到相关文档
                    </span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                {docNames.length === 0 ? (
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500">
                      若已上传文档仍无结果，请先执行「全量重建索引」
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs h-8"
                      onClick={handleReindex}
                      disabled={reindexing}
                    >
                      {reindexing ? "重建中…" : "🔄 全量重建索引"}
                    </Button>
                  </div>
                ) : (
                  <ul className="space-y-1 text-xs text-gray-600">
                    {docNames.map((name, i) => (
                      <li key={i}>· {name}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
