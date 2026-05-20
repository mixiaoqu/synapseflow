"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, Loader2 } from "lucide-react";

import { AnswerMarkdown } from "@/components/ask/AnswerMarkdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { getDocument, type DocumentDetail, type DocumentListItem } from "@/lib/api/documents";
import { cn } from "@/lib/utils";

import {
  actionButtonClass,
  availableReviewActions,
  formatDateTime,
  getReviewActionLabel,
  indexStatusMeta,
  lifecycleMeta,
  looksLikeMarkdown,
  type ReviewAction,
} from "./review-utils";

interface ReviewDocumentSheetProps {
  open: boolean;
  documentId: number | null;
  listItem: DocumentListItem | null;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onRunAction: (documentId: number, action: ReviewAction) => Promise<boolean>;
}

function MetaCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <div className="text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
        {label}
      </div>
      <div className="mt-2 text-sm text-slate-700">{value}</div>
    </div>
  );
}

export function ReviewDocumentSheet({
  open,
  documentId,
  listItem,
  busy,
  onOpenChange,
  onRunAction,
}: ReviewDocumentSheetProps) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || documentId == null) {
      setDetail(null);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await getDocument(documentId);
        if (cancelled) return;
        setDetail(response);
      } catch (loadError) {
        if (cancelled) return;
        setError(loadError instanceof Error ? loadError.message : "加载文档正文失败");
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [documentId, open]);

  const documentView = detail ?? listItem;
  const actions = useMemo(
    () => (documentView ? availableReviewActions(documentView) : []),
    [documentView],
  );
  const lifecycle =
    documentView != null ? lifecycleMeta[documentView.status] : null;
  const indexStatus =
    documentView != null ? indexStatusMeta[documentView.index_status] : null;
  const latestTimelineLabel = documentView?.published_at
    ? "最近发布"
    : documentView?.reviewed_at
      ? "最近审核"
      : "最近更新";
  const canRenderMarkdown = looksLikeMarkdown(
    detail?.document_type ?? listItem?.document_type,
    detail?.content ?? "",
  );

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex h-full w-full max-w-full flex-col overflow-hidden border-l border-slate-200 bg-white p-0 sm:max-w-3xl lg:max-w-[50vw]"
      >
        <SheetHeader className="border-b border-slate-200 bg-white px-6 py-5 pr-14">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              {lifecycle ? (
                <Badge className={cn("gap-1.5 rounded-full px-2.5 py-1", lifecycle.className)}>
                  {lifecycle.icon}
                  {lifecycle.label}
                </Badge>
              ) : null}
              {indexStatus ? (
                <Badge className={cn("gap-1.5 rounded-full px-2.5 py-1", indexStatus.className)}>
                  {indexStatus.icon}
                  {indexStatus.label}
                </Badge>
              ) : null}
            </div>

            <div>
              <SheetTitle className="line-clamp-2 text-2xl tracking-tight text-slate-900">
                {documentView?.title || "文档预览"}
              </SheetTitle>
              <SheetDescription className="mt-2 text-sm leading-6 text-slate-500">
                {listItem?.knowledge_base_name || "未归属知识库"}
                {documentView?.category_name ? ` · ${documentView.category_name}` : ""}
                {documentView?.version ? ` · v${documentView.version}` : ""}
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <div className="min-h-0 flex-1 overflow-y-auto bg-slate-50/60">
          {loading ? (
            <div className="flex min-h-[320px] items-center justify-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在加载正文预览...
            </div>
          ) : error ? (
            <div className="m-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          ) : (
            <div className="space-y-6 p-6">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <MetaCard
                  label="最近时间"
                  value={
                    documentView
                      ? `${latestTimelineLabel} · ${formatDateTime(
                          documentView.published_at ||
                            documentView.reviewed_at ||
                            documentView.updated_at,
                        )}`
                      : "暂无"
                  }
                />
                <MetaCard
                  label="文档类型"
                  value={(detail?.document_type ?? listItem?.document_type ?? "未知").toUpperCase()}
                />
                <MetaCard
                  label="来源路径"
                  value={detail?.source_path || listItem?.source_path || "未记录"}
                />
                <MetaCard
                  label="索引备注"
                  value={documentView?.index_error || "索引状态正常"}
                />
              </div>

              <section className="rounded-[28px] border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-200 px-6 py-4">
                  <div className="text-sm font-medium text-slate-900">正文预览</div>
                  <p className="mt-1 text-sm text-slate-500">
                    请先确认正文内容，再选择需要的操作。
                  </p>
                </div>

                <div className="px-6 py-6">
                  {!detail?.content ? (
                    <div className="flex min-h-[280px] flex-col items-center justify-center text-center">
                      <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-300">
                        <FileText className="h-6 w-6" />
                      </div>
                      <p className="mt-4 text-base font-medium text-slate-900">
                        当前文档暂时没有可预览的正文
                      </p>
                      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
                        你可以查看上方状态和索引备注，再决定后续操作。
                      </p>
                    </div>
                  ) : canRenderMarkdown ? (
                    <div className="max-w-none text-sm leading-7 text-slate-700">
                      <AnswerMarkdown text={detail.content} />
                    </div>
                  ) : (
                    <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-slate-700">
                      {detail.content}
                    </pre>
                  )}
                </div>
              </section>
            </div>
          )}
        </div>

        <div className="border-t border-slate-200 bg-white/95 px-6 py-4 backdrop-blur">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-500">
              根据当前状态选择审核、退回、下线或重新上线操作。
            </p>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                className="h-11 rounded-xl border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
              >
                关闭
              </Button>

              {actions.map((action) => (
                <Button
                  key={action}
                  type="button"
                  disabled={busy || documentId == null}
                  onClick={async () => {
                    if (documentId == null) return;
                    const succeeded = await onRunAction(documentId, action);
                    if (succeeded) {
                      onOpenChange(false);
                    }
                  }}
                  className={cn(
                    "h-11 rounded-xl px-5 text-sm shadow-none",
                    actionButtonClass(action),
                  )}
                >
                  {busy ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      处理中
                    </>
                  ) : (
                    getReviewActionLabel(action, documentView?.status)
                  )}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
