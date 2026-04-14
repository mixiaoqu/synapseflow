"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Toaster } from "sonner";
import { IterationHistory } from "@/components/kb-curation/IterationHistory";
import {
  ResultPanel,
  ResultPanelAction,
} from "@/components/kb-curation/ResultPanel";
import { useKbCuration } from "@/hooks/useKbCuration";

export default function KbCurationPage() {
  const {
    query,
    setQuery,
    maxIterations,
    setMaxIterations,
    knowledgeBaseId,
    setKnowledgeBaseId,
    categoryId,
    setCategoryId,
    knowledgeBases,
    categories,
    loading,
    result,
    error,
    reindexing,
    expandedRounds,
    docNames,
    toggleRound,
    expandAll,
    collapseAll,
    submit,
    triggerReindex,
  } = useKbCuration();

  return (
    <div className="min-h-full flex flex-col bg-gradient-to-br from-slate-50 via-white to-indigo-50/20">
      <Toaster position="top-right" richColors />

      <div className="shrink-0 border-b border-slate-200/80 bg-white/85 backdrop-blur-md px-6 py-5 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-purple-700 text-white shadow-lg shadow-indigo-600/25">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">知识库治理</h1>
            <p className="mt-1 text-sm leading-relaxed text-slate-500">
              面向管理员的多轮评估与修订入口，用于发现知识缺口并形成文档修订建议。
            </p>
          </div>
        </div>
      </div>

      <div className="grid flex-1 gap-5 p-5 lg:grid-cols-2 min-h-0">
        <div className="flex min-h-0 flex-col gap-5 overflow-hidden">
          <Card className="shrink-0 border-slate-200/90 shadow-sm ring-1 ring-slate-900/[0.04]">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-slate-900">治理问题</CardTitle>
              <p className="text-xs leading-relaxed text-slate-500">
                输入一个需要校验和治理的问题，系统会多轮评估回答质量并输出修订建议。
              </p>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void submit();
                }}
                className="space-y-3"
              >
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="min-h-[100px] w-full resize-none rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-800 placeholder:text-slate-400 shadow-sm focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none"
                  placeholder="例如：当前知识库对组件命名规范的说明是否足够清晰？如果不够，请指出需要修订的文档。"
                  disabled={loading}
                />

                <div className="flex flex-wrap gap-3">
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-gray-500">检索范围</label>
                    <select
                      value={knowledgeBaseId ?? ""}
                      onChange={(e) => {
                        const nextValue = e.target.value ? Number(e.target.value) : null;
                        setKnowledgeBaseId(nextValue);
                        setCategoryId(null);
                      }}
                      className="min-w-[120px] rounded border px-2 py-1 text-sm"
                      disabled={loading}
                    >
                      <option value="">全部知识库</option>
                      {knowledgeBases.map((collection) => (
                        <option key={collection.id} value={collection.id}>
                          {collection.name} ({collection.document_count})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <label className="text-xs text-gray-500">分类</label>
                    <select
                      value={categoryId ?? ""}
                      onChange={(e) =>
                        setCategoryId(e.target.value ? Number(e.target.value) : null)
                      }
                      className="min-w-[120px] rounded border px-2 py-1 text-sm"
                      disabled={loading || !knowledgeBaseId}
                    >
                      <option value="">{knowledgeBaseId ? "全部分类" : "先选知识库"}</option>
                      {categories.map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name} ({category.document_count})
                        </option>
                      ))}
                    </select>
                  </div>
  
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-gray-500">最大轮次</label>
                    <select
                      value={maxIterations}
                      onChange={(e) => setMaxIterations(Number(e.target.value))}
                      className="rounded border px-2 py-1 text-sm"
                      disabled={loading}
                    >
                      {[1, 2, 3, 4, 5].map((count) => (
                        <option key={count} value={count}>
                          {count}
                        </option>
                      ))}
                    </select>
                  </div>

                  <button
                    type="submit"
                    disabled={loading || !query.trim()}
                    className="rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-5 py-2 text-sm font-medium text-white shadow-md shadow-indigo-600/20 transition-all hover:from-indigo-700 hover:to-purple-700 hover:shadow-lg hover:shadow-indigo-600/30 disabled:opacity-50 disabled:shadow-none"
                  >
                    {loading ? "治理中..." : "开始治理"}
                  </button>
                </div>
              </form>
            </CardContent>
          </Card>

          <Card className="flex min-h-0 flex-1 flex-col overflow-hidden border-slate-200/90 shadow-sm ring-1 ring-slate-900/[0.04]">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-slate-900">治理过程</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto pt-0">
              {loading ? (
                <p className="py-8 text-center text-sm text-gray-500">
                  正在检索、评估并生成治理建议...
                </p>
              ) : (
                <IterationHistory
                  history={result?.iteration_history ?? []}
                  expandedRounds={expandedRounds}
                  docNames={docNames}
                  documentIssues={result?.document_issues ?? []}
                  onToggleRound={toggleRound}
                  onExpandAll={expandAll}
                  onCollapseAll={collapseAll}
                />
              )}
            </CardContent>
          </Card>
        </div>

        <div className="flex min-h-0 flex-col gap-5 overflow-hidden">
          <Card className="flex min-h-0 flex-1 flex-col overflow-hidden border-slate-200/90 shadow-sm ring-1 ring-slate-900/[0.04]">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold text-slate-900">最终回答</CardTitle>
                <ResultPanelAction result={result} />
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto pt-0">
              <ResultPanel result={result} error={error} />
            </CardContent>
          </Card>

          {result && (
            <Card className="shrink-0 border-slate-200/90 shadow-sm ring-1 ring-slate-900/[0.04]">
              <CardHeader className="py-3">
                <CardTitle className="text-sm font-semibold text-slate-900">
                  引用文档（{docNames.length} 篇）
                  {docNames.length === 0 && (
                    <span className="ml-2 font-normal text-amber-600">
                      暂未检索到相关文档
                    </span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                {docNames.length === 0 ? (
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500">
                      如果文档已上传但没有命中结果，可以先执行一次全量重建索引。
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs"
                      onClick={() => void triggerReindex()}
                      disabled={reindexing}
                    >
                      {reindexing ? "重建中..." : "全量重建索引"}
                    </Button>
                  </div>
                ) : (
                  <ul className="space-y-1 text-xs text-gray-600">
                    {docNames.map((name) => (
                      <li key={name}>· {name}</li>
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
