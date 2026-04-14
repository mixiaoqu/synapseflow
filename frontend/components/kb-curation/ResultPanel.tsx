import { Button } from "@/components/ui/button";
import type { KbCurationResult } from "@/hooks/useKbCuration";
import { PASS_SCORE } from "@/hooks/useKbCuration";
import { toast } from "sonner";

interface ResultPanelProps {
  result: KbCurationResult | null;
  error: string | null;
}

export function ResultPanel({ result, error }: ResultPanelProps) {
  return (
    <>
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {result ? (
        <>
          <div className="mb-4 rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-4 shadow-sm">
            <p className="mb-3 text-sm font-semibold text-slate-800">评估摘要</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                <p className="text-xs text-slate-500">迭代次数</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">{result.iteration} 轮</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                <p className="text-xs text-slate-500">最终得分</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">{result.confidence_score.toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                <p className="text-xs text-slate-500">达标阈值</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">{PASS_SCORE}</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                <p className="text-xs text-slate-500">状态</p>
                <p className="mt-1 text-lg font-semibold">
                  {result.confidence_score >= PASS_SCORE ? (
                    <span className="text-emerald-600">达标</span>
                  ) : (
                    <span className="text-amber-600">未达标</span>
                  )}
                </p>
              </div>
            </div>
          </div>
          <div className="prose prose-sm max-w-none rounded-xl border border-slate-200 bg-white p-4">
            <p className="whitespace-pre-wrap leading-relaxed text-slate-700">{result.answer}</p>
          </div>
        </>
      ) : !error ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
            <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <p className="mt-4 text-sm text-slate-500">最终回答会显示在这里</p>
        </div>
      ) : null}
    </>
  );
}

export function ResultPanelAction({ result }: { result: KbCurationResult | null }) {
  if (!result) return null;

  return (
    <Button
      variant="outline"
      size="sm"
      className="h-7 text-xs"
      onClick={() => {
        void navigator.clipboard.writeText(result.answer).then(() => {
          toast.success("已复制回答");
        });
      }}
    >
      复制回答
    </Button>
  );
}
