"use client";

import { Eye, FileSearch, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { DocumentListItem } from "@/lib/api/documents";
import { cn } from "@/lib/utils";

import {
  actionButtonClass,
  availableReviewActions,
  formatDateTime,
  getTimelineLabel,
  indexStatusMeta,
  lifecycleMeta,
  reviewActionMeta,
  type ReviewAction,
} from "./review-utils";

interface ReviewTableProps {
  items: DocumentListItem[];
  loading: boolean;
  selectedIds: number[];
  allVisibleSelected: boolean;
  partiallySelected: boolean;
  onToggleSelect: (documentId: number, checked: boolean) => void;
  onToggleSelectAll: (checked: boolean) => void;
  onOpenDocument: (item: DocumentListItem) => void;
  onRunAction: (documentId: number, action: ReviewAction) => void;
  busyIds: number[];
}

function isBusy(documentId: number, busyIds: number[]): boolean {
  return busyIds.includes(documentId);
}

export function ReviewTable({
  items,
  loading,
  selectedIds,
  allVisibleSelected,
  partiallySelected,
  onToggleSelect,
  onToggleSelectAll,
  onOpenDocument,
  onRunAction,
  busyIds,
}: ReviewTableProps) {
  return (
    <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
      <Table>
        <TableHeader className="bg-slate-50/80">
          <TableRow className="hover:bg-slate-50/80">
            <TableHead className="w-12 px-5">
              <Checkbox
                checked={allVisibleSelected ? true : partiallySelected ? "indeterminate" : false}
                onCheckedChange={onToggleSelectAll}
                aria-label="全选当前列表"
              />
            </TableHead>
            <TableHead className="min-w-[320px]">文档信息</TableHead>
            <TableHead className="min-w-[220px]">状态与索引</TableHead>
            <TableHead className="min-w-[180px]">时间轨迹</TableHead>
            <TableHead className="min-w-[260px]">快捷操作</TableHead>
          </TableRow>
        </TableHeader>

        <TableBody>
          {loading ? (
            <TableRow className="hover:bg-white">
              <TableCell colSpan={5} className="px-5 py-20">
                <div className="flex items-center justify-center gap-2 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  正在加载审核列表...
                </div>
              </TableCell>
            </TableRow>
          ) : items.length === 0 ? (
            <TableRow className="hover:bg-white">
              <TableCell colSpan={5} className="px-5 py-20">
                <div className="flex flex-col items-center justify-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-slate-100 text-slate-300">
                    <FileSearch className="h-7 w-7" />
                  </div>
                  <p className="mt-4 text-lg font-medium text-slate-900">
                    太棒了，当前没有需要处理的文档
                  </p>
                  <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
                    你可以切换状态标签或调整搜索条件，查看其他生命周期下的文档。
                  </p>
                </div>
              </TableCell>
            </TableRow>
          ) : (
            items.map((item, index) => {
              const lifecycle = lifecycleMeta[item.status];
              const indexing = indexStatusMeta[item.index_status];
              const actions = availableReviewActions(item);
              const checked = selectedIds.includes(item.id);
              const busy = isBusy(item.id, busyIds);

              return (
                <TableRow
                  key={item.id}
                  data-state={checked ? "selected" : "unchecked"}
                  className={cn(
                    "cursor-pointer",
                    index % 2 === 1 && "bg-slate-50/35",
                  )}
                  onClick={() => onOpenDocument(item)}
                >
                  <TableCell className="px-5" onClick={(event) => event.stopPropagation()}>
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(nextChecked) =>
                        onToggleSelect(item.id, nextChecked)
                      }
                      aria-label={`选择文档 ${item.title}`}
                    />
                  </TableCell>

                  <TableCell className="align-top">
                    <div className="space-y-1.5">
                      <div className="text-sm font-semibold text-slate-900">
                        {item.title}
                      </div>
                      <div className="text-sm text-slate-500">
                        {item.knowledge_base_name || "未归属知识库"}
                        {item.category_name ? ` · ${item.category_name}` : ""}
                      </div>
                      <div className="text-xs text-slate-400">
                        版本 v{item.version}
                        {item.document_type ? ` · ${item.document_type.toUpperCase()}` : ""}
                      </div>
                    </div>
                  </TableCell>

                  <TableCell className="align-top">
                    <div className="space-y-2">
                      <Badge className={cn("w-fit gap-1.5 rounded-full px-2.5 py-1", lifecycle.className)}>
                        {lifecycle.icon}
                        {lifecycle.label}
                      </Badge>

                      <div className="space-y-1.5">
                        <Badge className={cn("w-fit gap-1.5 rounded-full px-2.5 py-1", indexing.className)}>
                          {indexing.icon}
                          {indexing.label}
                        </Badge>
                        {item.index_error ? (
                          <p className="max-w-[240px] text-xs leading-5 text-rose-600">
                            {item.index_error}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  </TableCell>

                  <TableCell
                    className="align-top text-sm text-slate-600"
                    title={`${getTimelineLabel(item)}：${formatDateTime(
                      item.published_at || item.reviewed_at || item.updated_at,
                    )}`}
                  >
                    <div>{formatDateTime(item.published_at || item.reviewed_at || item.updated_at)}</div>
                    <div className="mt-1 text-xs text-slate-400">{getTimelineLabel(item)}</div>
                  </TableCell>

                  <TableCell className="align-top" onClick={(event) => event.stopPropagation()}>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => onOpenDocument(item)}
                        className="h-9 rounded-xl border-slate-200 bg-white px-3 text-slate-700 hover:bg-slate-50"
                      >
                        <Eye className="h-4 w-4" />
                        审阅
                      </Button>

                      {actions.map((action) => (
                        <Button
                          key={action}
                          type="button"
                          disabled={busy}
                          onClick={() => onRunAction(item.id, action)}
                          className={cn(
                            "h-9 rounded-xl px-3 text-sm shadow-none",
                            actionButtonClass(action),
                          )}
                        >
                          {busy ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              处理中
                            </>
                          ) : (
                            reviewActionMeta[action].label
                          )}
                        </Button>
                      ))}

                      {actions.length === 0 ? (
                        <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">
                          {item.index_status !== "indexed"
                            ? "等待索引完成后才能进入审核流转"
                            : "当前状态暂无快捷操作"}
                        </span>
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </div>
  );
}
