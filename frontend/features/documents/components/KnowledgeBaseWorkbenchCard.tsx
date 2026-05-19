"use client";

import { Loader2, MoreHorizontal, PencilLine, Trash2, UploadCloud } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { KnowledgeBaseWithCount } from "@/lib/api/knowledgeBases";
import { cn } from "@/lib/utils";

import { formatKnowledgeBaseDateTime } from "./KnowledgeBaseStatusSummary";

export function KnowledgeBaseWorkbenchCard({
  knowledgeBase,
  active,
  deleting,
  onOpen,
  onUpload,
  onEdit,
  onDelete,
}: {
  knowledgeBase: KnowledgeBaseWithCount;
  active: boolean;
  deleting: boolean;
  onOpen: (knowledgeBase: KnowledgeBaseWithCount) => void;
  onUpload: (knowledgeBase: KnowledgeBaseWithCount) => void;
  onEdit: (knowledgeBase: KnowledgeBaseWithCount) => void;
  onDelete: (knowledgeBase: KnowledgeBaseWithCount) => void;
}) {
  return (
    <article
      role="button"
      tabIndex={0}
      onClick={() => onOpen(knowledgeBase)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(knowledgeBase);
        }
      }}
      className={cn(
        "group relative flex h-full min-h-[228px] cursor-pointer flex-col overflow-hidden rounded-xl border bg-white transition-all duration-200 hover:-translate-y-1 hover:shadow-md",
        active
          ? "border-slate-300 shadow-sm ring-2 ring-slate-100"
          : "border-slate-200 shadow-sm hover:border-slate-300",
      )}
    >
      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-white shadow-sm">
                <span className="text-sm font-semibold">KB</span>
              </div>
              <div className="min-w-0">
                <h3 className="truncate text-lg font-semibold text-slate-900">{knowledgeBase.name}</h3>
                <span className="mt-2 inline-flex rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                  文档 {knowledgeBase.document_count}
                </span>
              </div>
            </div>
            <p className="mt-4 line-clamp-2 min-h-12 text-sm leading-6 text-slate-500">
              {knowledgeBase.description || "管理知识库下的文档、分类、索引和发布状态。"}
            </p>
          </div>

          <div onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  aria-label="更多操作"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44">
                <DropdownMenuItem onSelect={() => onUpload(knowledgeBase)}>
                  <UploadCloud className="mr-2 h-4 w-4" />
                  上传文档
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => onEdit(knowledgeBase)}>
                  <PencilLine className="mr-2 h-4 w-4" />
                  编辑知识库
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onSelect={() => onDelete(knowledgeBase)}
                  disabled={deleting}
                  className="text-rose-600 focus:text-rose-700"
                >
                  {deleting ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="mr-2 h-4 w-4" />
                  )}
                  删除知识库
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className="rounded-full bg-slate-100 px-2.5 py-1">
            知识库
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-1">
            文档 {knowledgeBase.document_count}
          </span>
        </div>

        <div className="mt-auto border-t border-slate-100 pt-4 text-xs text-slate-500">
          <p>最近更新：{formatKnowledgeBaseDateTime(knowledgeBase.updated_at)}</p>
        </div>
      </div>
    </article>
  );
}
