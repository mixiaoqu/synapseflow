import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { DocumentIssue, IterationRecord } from "@/hooks/useKbCuration";
import { getRoundDocumentIssues } from "@/hooks/useKbCuration";

interface IterationHistoryProps {
  history: IterationRecord[];
  expandedRounds: Set<number>;
  docNames: string[];
  documentIssues: DocumentIssue[];
  onToggleRound: (round: number) => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
}

export function IterationHistory({
  history,
  expandedRounds,
  docNames,
  documentIssues,
  onToggleRound,
  onExpandAll,
  onCollapseAll,
}: IterationHistoryProps) {
  if (!history.length) {
    return (
      <p className="py-8 text-center text-sm text-gray-400">
        提问后将显示每轮治理记录
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end gap-1">
        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={onExpandAll}>
          全部展开
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          onClick={onCollapseAll}
        >
          全部折叠
        </Button>
      </div>

      {history.map((item) => {
        const expanded = expandedRounds.has(item.round);
        const issues = getRoundDocumentIssues(item.round, documentIssues);

        if (item.passed) {
          return (
            <div
              key={item.round}
              className="relative overflow-hidden rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50/80 to-white shadow-sm"
            >
              <div className="absolute inset-y-0 left-0 w-1 bg-emerald-500" />
              <div className="px-4 py-3 pl-4">
                <button
                  type="button"
                  onClick={() => onToggleRound(item.round)}
                  className="mb-0 flex w-full items-center justify-between gap-2 text-left transition-opacity hover:opacity-90"
                >
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-emerald-800">
                    {expanded ? (
                      <ChevronDown className="h-4 w-4 shrink-0" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0" />
                    )}
                    第 {item.round} 轮
                  </span>
                  <Badge className="shrink-0 bg-emerald-600 hover:bg-emerald-600">
                    达标 {item.score.toFixed(2)}
                  </Badge>
                </button>
                {expanded ? (
                  <div className="mt-3 space-y-3">
                    <div className="rounded-lg bg-white/70 px-3 py-2">
                      <p className="mb-0.5 text-xs text-emerald-700/80">问题</p>
                      <p className="text-sm leading-relaxed text-gray-800">{item.question}</p>
                    </div>
                    <div className="rounded-lg bg-white/60 px-3 py-2">
                      <p className="mb-1 text-xs text-emerald-700/80">回答</p>
                      <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
                        {item.answer}
                      </p>
                    </div>
                  </div>
                ) : (
                  <p className="mt-2 truncate text-xs text-emerald-600">{item.question}</p>
                )}
              </div>
            </div>
          );
        }

        return (
          <div
            key={item.round}
            className="relative overflow-hidden rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50/60 to-white shadow-sm"
          >
            <div className="absolute inset-y-0 left-0 w-1 bg-amber-500" />
            <div className="px-4 py-3 pl-4">
              <button
                type="button"
                onClick={() => onToggleRound(item.round)}
                className="mb-0 flex w-full items-center justify-between gap-2 text-left transition-opacity hover:opacity-90"
              >
                <span className="flex items-center gap-1.5 text-sm font-semibold text-amber-800">
                  {expanded ? (
                    <ChevronDown className="h-4 w-4 shrink-0" />
                  ) : (
                    <ChevronRight className="h-4 w-4 shrink-0" />
                  )}
                  第 {item.round} 轮
                </span>
                <Badge
                  variant="secondary"
                  className="shrink-0 border-amber-200 bg-amber-100 text-amber-800"
                >
                  未达标 {item.score.toFixed(2)}
                </Badge>
              </button>

              {expanded ? (
                <div className="mt-3 space-y-3">
                  <div className="rounded-lg border border-amber-100 bg-white/80 px-3 py-2">
                    <p className="mb-0.5 text-xs font-medium text-amber-700">问题</p>
                    <p className="text-sm leading-relaxed text-gray-800">{item.question}</p>
                  </div>

                  {docNames.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-xs font-medium text-amber-700">
                        涉及文档
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {docNames.map((name) => (
                          <span
                            key={name}
                            className="inline-flex items-center rounded-md bg-amber-100/80 px-2 py-0.5 text-xs text-amber-800"
                          >
                            {name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div>
                    <p className="mb-2 text-xs font-medium text-amber-700">修订建议</p>
                    <div className="space-y-2">
                      {item.reason && (
                        <div className="rounded-lg border border-amber-100 bg-white/80 px-3 py-2">
                          <p className="mb-0.5 text-xs text-amber-700/80">未通过原因</p>
                          <p className="text-sm text-gray-700">{item.reason}</p>
                        </div>
                      )}
                      {item.suggestion && (
                        <div className="rounded-lg border border-amber-100 bg-white/80 px-3 py-2">
                          <p className="mb-0.5 text-xs text-amber-700/80">补充建议</p>
                          <p className="text-sm text-gray-700">{item.suggestion}</p>
                        </div>
                      )}
                      {issues.map((issue, index) => (
                        <div
                          key={`${item.round}-${index}`}
                          className="rounded-lg border-l-2 border-l-amber-400 bg-white/90 px-3 py-2 shadow-sm"
                        >
                          {issue.document_title && (
                            <p className="mb-1 text-xs font-semibold text-amber-800">
                              文档：{issue.document_title}
                            </p>
                          )}
                          {issue.description && (
                            <p className="mb-1 text-sm text-gray-700">{issue.description}</p>
                          )}
                          {issue.modification_suggestion && (
                            <p className="text-sm italic text-amber-700/90">
                              建议：{issue.modification_suggestion}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="mt-2 line-clamp-1 text-xs text-amber-600">{item.question}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
