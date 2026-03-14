"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const API_BASE =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) ||
  "http://localhost:8000";

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

interface QAResult {
  answer: string;
  confidence_score: number;
  iteration: number;
  retrieved_docs: Array<{ content: string; metadata?: Record<string, unknown> }>;
  iteration_history: IterationRecord[];
}

export default function QAPage() {
  const [query, setQuery] = useState("");
  const [maxIterations, setMaxIterations] = useState(3);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QAResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE}/api/v1/qa/invoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, max_iterations: maxIterations }),
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
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "发生错误，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-full flex flex-col bg-gray-50">
      {/* 顶部 */}
      <div className="bg-white border-b px-6 py-4 shrink-0">
        <h1 className="text-2xl font-bold text-gray-900">迭代问答</h1>
        <p className="text-sm text-gray-500 mt-1">
          知识库 Q&A，自动优化提问与答案质量
        </p>
      </div>

      <div className="flex-1 grid grid-cols-12 gap-4 p-4 min-h-0">
        {/* 左侧输入区 */}
        <div className="col-span-3 flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">输入问题</CardTitle>
              <p className="text-xs text-gray-500">
                支持复杂问题，系统会自动拆分与优化
              </p>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="w-full p-3 border rounded-lg text-sm min-h-[120px] resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="例如：智友前端开发规范中组件命名的要求是什么？"
                  disabled={loading}
                />
                <div className="flex items-center gap-2">
                  <label className="text-xs text-gray-500">最大轮次</label>
                  <select
                    value={maxIterations}
                    onChange={(e) => setMaxIterations(Number(e.target.value))}
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
                  className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
                >
                  {loading ? "处理中..." : "提问"}
                </button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* 中间：迭代历史 */}
        <div className="col-span-4 flex flex-col gap-4 min-h-0">
          <Card className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">迭代历史</CardTitle>
                {result && (
                  <Badge variant="secondary">
                    共 {result.iteration} 轮
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto pt-0 max-h-[calc(100vh-280px)]">
                  {!result && !loading && (
                    <p className="text-sm text-gray-400 py-8 text-center">
                      提问后将显示每轮问答记录
                    </p>
                  )}
                  {loading && (
                    <p className="text-sm text-gray-500 py-8 text-center">
                      正在检索与评估…
                    </p>
                  )}
                  {result?.iteration_history?.length ? (
                    <div className="space-y-3">
                      {result.iteration_history.map((r) => (
                        <div
                          key={r.round}
                          className={`rounded-lg border p-3 text-sm ${
                            r.passed ? "border-green-200 bg-green-50/50" : "border-amber-200 bg-amber-50/30"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-medium">第 {r.round} 轮</span>
                            <Badge
                              variant={r.passed ? "default" : "secondary"}
                              className={r.passed ? "bg-green-600" : ""}
                            >
                              得分 {r.score.toFixed(2)}
                              {r.passed ? " ✓" : " (未达标)"}
                            </Badge>
                          </div>
                          <p className="text-gray-700 font-medium mb-1">
                            问题：{r.question}
                          </p>
                          <p className="text-gray-600 text-xs line-clamp-3">
                            {r.answer}
                          </p>
                          {!r.passed && (r.reason || r.suggestion) && (
                            <p className="text-amber-700 text-xs mt-2">
                              {r.reason || ""}
                              {r.suggestion ? ` → ${r.suggestion}` : ""}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : result && !result.iteration_history?.length ? (
                    <p className="text-sm text-gray-400 py-4">暂无迭代记录</p>
                  ) : null}
            </CardContent>
          </Card>
        </div>

        {/* 右侧：最终答案与检索来源 */}
        <div className="col-span-5 flex flex-col gap-4 min-h-0">
          <Card className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">最终答案</CardTitle>
                {result && (
                  <Badge variant="outline">
                    置信度 {(result.confidence_score * 100).toFixed(0)}%
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto pt-0">
              {error && (
                <p className="text-sm text-red-600 py-4">{error}</p>
              )}
              {result && (
                <div className="prose prose-sm max-w-none">
                  <p className="whitespace-pre-wrap text-gray-700">
                    {result.answer}
                  </p>
                </div>
              )}
              {!result && !loading && !error && (
                <p className="text-sm text-gray-400 py-8">
                  答案将显示在这里
                </p>
              )}
            </CardContent>
          </Card>

          {/* 检索来源 */}
          {result?.retrieved_docs?.length ? (
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-sm">
                  检索来源 ({result.retrieved_docs.length} 条)
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0 max-h-40 overflow-auto">
                <ul className="space-y-2 text-xs">
                  {result.retrieved_docs.map((doc, i) => (
                    <li
                      key={i}
                      className="rounded border p-2 bg-gray-50 text-gray-600 line-clamp-2"
                    >
                      {doc.content}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
