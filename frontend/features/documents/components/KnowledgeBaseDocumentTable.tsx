"use client";

import { Loader2, RefreshCcw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type {
  DocumentIndexStatus,
  DocumentLifecycleStatus,
  DocumentListItem,
} from "@/lib/api/documents";
import { cn } from "@/lib/utils";

const PAGE_SIZE_OPTIONS = [20, 50, 100];

const indexStatusMeta: Record<DocumentIndexStatus, { label: string; className: string }> = {
  queued: {
    label: "排队中",
    className: "border-slate-200 bg-slate-50 text-slate-700",
  },
  processing: {
    label: "索引中",
    className: "border-amber-200 bg-amber-50 text-amber-700",
  },
  indexed: {
    label: "已完成",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  failed: {
    label: "索引失败",
    className: "border-rose-200 bg-rose-50 text-rose-700",
  },
};

const lifecycleStatusMeta: Record<DocumentLifecycleStatus, { label: string; className: string }> = {
  draft: {
    label: "草稿",
    className: "border-slate-200 bg-slate-50 text-slate-700",
  },
  pending_review: {
    label: "待审核",
    className: "border-orange-200 bg-orange-50 text-orange-700",
  },
  published: {
    label: "已发布",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  archived: {
    label: "已归档",
    className: "border-slate-200 bg-slate-100 text-slate-600",
  },
};

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function KnowledgeBaseDocumentTable({
  documents,
  loading,
  total,
  page,
  pageSize,
  focusedDocumentId,
  showCategoryColumn,
  reindexingDocumentId,
  deletingDocumentId,
  onPageChange,
  onPageSizeChange,
  onOpenDetail,
  onReindex,
  onDelete,
}: {
  documents: DocumentListItem[];
  loading: boolean;
  total: number;
  page: number;
  pageSize: number;
  focusedDocumentId: number | null;
  showCategoryColumn: boolean;
  reindexingDocumentId: number | null;
  deletingDocumentId: number | null;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onOpenDetail: (document: DocumentListItem) => void;
  onReindex: (document: DocumentListItem) => void;
  onDelete: (document: DocumentListItem) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pageStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const pageEnd = total === 0 ? 0 : Math.min(page * pageSize, total);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">文档名称</th>
              {showCategoryColumn ? <th className="px-4 py-3 font-medium">所属分类</th> : null}
              <th className="px-4 py-3 font-medium">上传时间</th>
              <th className="px-4 py-3 font-medium">索引状态</th>
              <th className="px-4 py-3 font-medium">用户可见状态</th>
              <th className="px-4 py-3 text-right font-medium">操作</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100 bg-white">
            {loading ? (
              <tr>
                <td
                  colSpan={showCategoryColumn ? 6 : 5}
                  className="px-4 py-16 text-center text-slate-500"
                >
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    正在加载文档...
                  </span>
                </td>
              </tr>
            ) : documents.length === 0 ? (
              <tr>
                <td
                  colSpan={showCategoryColumn ? 6 : 5}
                  className="px-4 py-16 text-center text-slate-500"
                >
                  当前条件下暂无文档
                </td>
              </tr>
            ) : (
              documents.map((document) => {
                const focused = document.id === focusedDocumentId;
                const indexMeta = indexStatusMeta[document.index_status];
                const lifecycleMeta = lifecycleStatusMeta[document.status];

                return (
                  <tr
                    key={document.id}
                    onClick={() => onOpenDetail(document)}
                    className={cn(
                      "cursor-pointer align-top transition-colors",
                      focused ? "bg-blue-50/70" : "hover:bg-slate-50",
                    )}
                  >
                    <td className="px-4 py-4">
                      <div className="min-w-[240px]">
                        <p className="font-medium text-slate-900">{document.title}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          v{document.version}
                          {document.is_current ? " · 当前版本" : ""}
                          {document.is_live ? " · 生效中" : ""}
                        </p>
                      </div>
                    </td>
                    {showCategoryColumn ? (
                      <td className="px-4 py-4 text-slate-600">{document.category_name || "未分类"}</td>
                    ) : null}
                    <td className="px-4 py-4 text-slate-600">{formatDateTime(document.created_at)}</td>
                    <td className="px-4 py-4">
                      <span
                        className={cn(
                          "inline-flex rounded-full border px-2.5 py-1 text-xs font-medium",
                          indexMeta.className,
                        )}
                      >
                        {indexMeta.label}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={cn(
                          "inline-flex rounded-full border px-2.5 py-1 text-xs font-medium",
                          lifecycleMeta.className,
                        )}
                      >
                        {lifecycleMeta.label}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-full border-slate-200"
                          onClick={(event) => {
                            event.stopPropagation();
                            onOpenDetail(document);
                          }}
                        >
                          详情
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-full border-slate-200"
                          onClick={(event) => {
                            event.stopPropagation();
                            onReindex(document);
                          }}
                          disabled={reindexingDocumentId === document.id}
                        >
                          {reindexingDocumentId === document.id ? (
                            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <RefreshCcw className="mr-1.5 h-3.5 w-3.5" />
                          )}
                          重新索引
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-full border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                          onClick={(event) => {
                            event.stopPropagation();
                            onDelete(document);
                          }}
                          disabled={deletingDocumentId === document.id}
                        >
                          {deletingDocumentId === document.id ? (
                            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                          )}
                          删除
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-3 border-t border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500 md:flex-row md:items-center md:justify-between">
        <p>
          显示 {pageStart}-{pageEnd} / 共 {total} 条
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2">
            <span>每页</span>
            <select
              value={pageSize}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
              className="h-9 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-200"
            >
              {PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="rounded-full border-slate-200"
              onClick={() => onPageChange(Math.max(1, page - 1))}
              disabled={page <= 1}
            >
              上一页
            </Button>
            <span className="text-slate-600">
              第 {page} / {totalPages} 页
            </span>
            <Button
              variant="outline"
              size="sm"
              className="rounded-full border-slate-200"
              onClick={() => onPageChange(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
            >
              下一页
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
