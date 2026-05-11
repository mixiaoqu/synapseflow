"use client";

import { ChevronDown, FolderOpen, GitBranch } from "lucide-react";

import type { DocumentCategory } from "@/lib/api/documentCategories";
import type { KnowledgeBaseBranch } from "@/lib/api/knowledgeBases";
import { cn } from "@/lib/utils";

export function KnowledgeBaseBranchSidebar({
  branches,
  categories,
  selectedBranchId,
  selectedCategoryId,
  onSelectBranch,
  onSelectCategory,
}: {
  branches: KnowledgeBaseBranch[];
  categories: DocumentCategory[];
  selectedBranchId: number | null;
  selectedCategoryId: number | null;
  onSelectBranch: (branchId: number) => void;
  onSelectCategory: (categoryId: number | null) => void;
}) {
  const activeBranch = branches.find((item) => item.id === selectedBranchId) ?? null;

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 p-4">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          <GitBranch className="h-3.5 w-3.5" />
          版本控制台
        </div>

        <div className="relative">
          <select
            value={selectedBranchId ?? ""}
            onChange={(event) => {
              const next = Number(event.target.value);
              if (Number.isFinite(next) && next > 0) {
                onSelectBranch(next);
              }
            }}
            className="h-11 w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 pr-10 text-sm font-medium text-slate-800 outline-none transition focus:border-slate-300 focus:ring-2 focus:ring-slate-200"
          >
            <option value="">请选择版本</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        </div>

        {activeBranch ? (
          <p className="mt-2 text-xs text-slate-500">
            {activeBranch.code} · {activeBranch.document_count} 份文档
          </p>
        ) : (
          <p className="mt-2 text-xs text-slate-500">请选择一个版本进入工作台</p>
        )}
      </div>

      <div className="min-h-0 flex-1 p-3">
        <div className="mb-3 px-2 text-sm font-semibold text-slate-900">分类目录</div>

        <div className="space-y-1 overflow-y-auto pr-1">
          <button
            type="button"
            onClick={() => onSelectCategory(null)}
            className={cn(
              "flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm transition-colors",
              selectedCategoryId == null
                ? "bg-slate-100 font-medium text-slate-900"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
            )}
          >
            <FolderOpen className="h-4 w-4" />
            全部文档
          </button>

          {categories.map((category) => {
            const active = category.id === selectedCategoryId;

            return (
              <button
                key={category.id}
                type="button"
                onClick={() => onSelectCategory(category.id)}
                className={cn(
                  "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors",
                  active
                    ? "bg-slate-100 font-medium text-slate-900"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                )}
              >
                <span className="truncate">{category.name}</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">
                  {category.document_count}
                </span>
              </button>
            );
          })}

          {categories.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-500">
              当前版本下暂无可展示分类
            </div>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
