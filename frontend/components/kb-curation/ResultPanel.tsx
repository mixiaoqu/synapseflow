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
      {error && <p className="py-4 text-sm text-red-600">{error}</p>}

      {result ? (
        <>
          <div className="mb-4 rounded-lg bg-gray-50 p-3 text-sm">
            <p className="mb-2 font-medium text-gray-700">评估摘要</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-gray-600">
              <span>迭代次数：{result.iteration} 轮</span>
              <span>最终得分：{result.confidence_score.toFixed(2)}</span>
              <span>达标阈值：{PASS_SCORE}</span>
              <span>
                状态：
                {result.confidence_score >= PASS_SCORE ? (
                  <span className="font-medium text-green-600"> 达标</span>
                ) : (
                  <span className="font-medium text-amber-600"> 未达标</span>
                )}
              </span>
            </div>
          </div>
          <div className="prose prose-sm max-w-none">
            <p className="whitespace-pre-wrap text-gray-700">{result.answer}</p>
          </div>
        </>
      ) : !error ? (
        <p className="py-8 text-sm text-gray-400">最终回答会显示在这里</p>
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
