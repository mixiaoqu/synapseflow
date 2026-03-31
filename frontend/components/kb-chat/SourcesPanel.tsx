import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, FolderOpen, PanelRight, UnfoldVertical } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RetrievedDoc } from "@/lib/api/endpoints/kbChat";
import type { KbChatTurn } from "@/hooks/useKbChat";

function truncateText(value: string, max: number): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= max) return normalized;
  return `${normalized.slice(0, max)}...`;
}

function SourceChunkCard({
  doc,
  index,
  expanded,
  onToggle,
}: {
  doc: RetrievedDoc;
  index: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const title = doc.metadata?.document_title?.trim() || `摘录片段 ${index + 1}`;
  const body = doc.content?.trim() || "";
  const previewLen = 220;
  const needsExpand = body.length > previewLen;

  return (
    <div className="rounded-xl border border-slate-200/90 bg-white/90 shadow-sm ring-1 ring-slate-900/[0.02] transition-shadow hover:shadow-md">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-2.5 rounded-xl px-3.5 py-3 text-left transition-colors hover:bg-teal-50/40"
      >
        {expanded ? (
          <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-teal-600" />
        ) : (
          <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-800">{title}</span>
            {doc.metadata?.chunk_index != null && (
              <Badge
                variant="secondary"
                className="px-1.5 py-0 text-[10px] font-normal tabular-nums"
              >
                块 #{doc.metadata.chunk_index}
              </Badge>
            )}
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
            {expanded || !needsExpand ? body : truncateText(body, previewLen)}
          </p>
          {needsExpand && (
            <span className="mt-1.5 inline-block text-[11px] font-medium text-teal-700">
              {expanded ? "收起" : "展开全文"}
            </span>
          )}
        </div>
      </button>
    </div>
  );
}

export interface SourcesPanelProps {
  collectionLabel: string;
  sourceDocs: RetrievedDoc[];
  lastTurn: KbChatTurn | null;
  loading: boolean;
  expandedChunks: Set<string>;
  onToggleChunk: (key: string) => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  className?: string;
}

export function SourcesPanel({
  collectionLabel,
  sourceDocs,
  lastTurn,
  loading,
  expandedChunks,
  onToggleChunk,
  onExpandAll,
  onCollapseAll,
  className,
}: SourcesPanelProps) {
  const uniqueDocCount = new Set(
    sourceDocs
      .map((doc) => doc.metadata?.document_id)
      .filter((id): id is number => id != null),
  ).size;
  const canExpandOps = Boolean(lastTurn && sourceDocs.length > 0);
  const allExpanded =
    sourceDocs.length > 0 &&
    sourceDocs.every((_, i) => expandedChunks.has(`${lastTurn?.id}-${i}`));

  return (
    <div
      className={cn(
        "flex min-h-0 flex-1 flex-col overflow-hidden bg-gradient-to-b from-white to-slate-50/50",
        className,
      )}
    >
      <div className="shrink-0 border-b border-slate-100/90 px-4 py-3.5">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <PanelRight className="h-4 w-4 text-teal-600" />
              本轮资料摘录
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">
              展示当前回答命中的原文片段，方便和回答内容交叉核对。
            </p>
          </div>
          {canExpandOps ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 shrink-0 gap-1 px-2 text-xs text-slate-600"
              onClick={allExpanded ? onCollapseAll : onExpandAll}
            >
              <UnfoldVertical className="h-3.5 w-3.5" />
              {allExpanded ? "全部收起" : "全部展开"}
            </Button>
          ) : null}
        </div>

        <div className="mt-2.5 flex flex-wrap gap-2">
          <Badge variant="outline" className="border-slate-200 font-normal text-slate-600">
            <FolderOpen className="mr-1 h-3 w-3 opacity-70" />
            {collectionLabel}
          </Badge>
          {sourceDocs.length > 0 && (
            <Badge className="border border-teal-200/60 bg-teal-600/10 font-normal text-teal-800 hover:bg-teal-600/15">
              {sourceDocs.length} 条片段
              {uniqueDocCount > 0 ? ` · ${uniqueDocCount} 篇文档` : ""}
            </Badge>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto p-3 overscroll-contain">
        {!lastTurn ? (
          <p className="px-1 py-8 text-center text-xs leading-relaxed text-slate-400">
            发送问题后，这里会展示命中的资料摘录。
          </p>
        ) : sourceDocs.length === 0 ? (
          <div className="px-1 py-8 text-center">
            <p className="text-xs leading-relaxed text-slate-500">
              {loading
                ? "正在检索资料..."
                : "本轮没有返回摘录。如果已上传文档仍没有结果，请到“文档库”检查索引状态。"}
            </p>
          </div>
        ) : (
          sourceDocs.map((doc, index) => {
            const key = `${lastTurn.id}-${index}`;
            return (
              <SourceChunkCard
                key={key}
                doc={doc}
                index={index}
                expanded={expandedChunks.has(key)}
                onToggle={() => onToggleChunk(key)}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
