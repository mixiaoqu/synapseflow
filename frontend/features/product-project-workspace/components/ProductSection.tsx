"use client";

import {
  ChevronDown,
  ChevronRight,
  Edit,
  FolderPlus,
  MoreHorizontal,
  Package2,
  Power,
  Trash2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ProjectResponse } from "@/lib/api/endpoints/projects";
import type { ProductResponse } from "@/lib/api/products";
import { ProjectRow } from "./ProjectRow";

interface ProductSectionProps {
  product: ProductResponse;
  projects: ProjectResponse[];
  totalApps: number;
  expanded: boolean;
  searchActive: boolean;
  onToggleExpanded: () => void;
  onCreateProject: (product: ProductResponse) => void;
  onEditProduct: (product: ProductResponse) => void;
  onToggleProduct: (product: ProductResponse) => void;
  onDeleteProduct: (product: ProductResponse) => void;
  onEditProject: (project: ProjectResponse) => void;
  onToggleProject: (project: ProjectResponse) => void;
  onDeleteProject: (project: ProjectResponse) => void;
}

export function ProductSection(props: ProductSectionProps) {
  const {
    product,
    projects,
    totalApps,
    expanded,
    searchActive,
    onToggleExpanded,
    onCreateProject,
    onEditProduct,
    onToggleProduct,
    onDeleteProduct,
    onEditProject,
    onToggleProject,
    onDeleteProject,
  } = props;
  const ExpandIcon = expanded ? ChevronDown : ChevronRight;
  const activeLabel = "已启用";
  const inactiveLabel = "已停用";
  const searchResultLabel = "搜索结果";
  const projectCountLabel = `${projects.length} 个项目`;
  const appCountLabel = `${totalApps} 个应用`;
  const emptyDescription = "暂未填写描述";
  const createProjectLabel = "新建项目";
  const editProductLabel = "编辑产品";
  const disableProductLabel = "停用产品";
  const enableProductLabel = "启用产品";
  const deleteProductLabel = "删除产品";
  const noProjectsTitle = "当前产品下还没有项目";
  const noProjectsDescription = "先在这个产品下创建项目，再进入项目详情页配置应用。";
  const projectNameHeader = "项目名称";
  const projectCodeHeader = "项目编码";
  const appCountHeader = "应用数";
  const statusHeader = "状态";
  const actionHeader = "操作";

  return (
    <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-4 px-5 py-4">
        <button
          type="button"
          onClick={onToggleExpanded}
          className="flex min-w-0 flex-1 items-start gap-3 text-left"
        >
          <div className="mt-0.5 rounded-lg border border-slate-200 bg-slate-50 p-2 text-slate-600">
            <ExpandIcon className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="truncate text-base font-semibold text-slate-900">{product.name}</h2>
              <Badge
                variant={product.is_active ? "default" : "secondary"}
                className={
                  product.is_active ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-50" : ""
                }
              >
                {product.is_active ? activeLabel : inactiveLabel}
              </Badge>
              {searchActive ? (
                <span className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">
                  {searchResultLabel}
                </span>
              ) : null}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-500">
              <code className="rounded bg-slate-100 px-2 py-1 text-slate-600">{product.code}</code>
              <span>{projectCountLabel}</span>
              <span>{appCountLabel}</span>
            </div>
            <p className="mt-2 text-sm text-slate-500">{product.description || emptyDescription}</p>
          </div>
        </button>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => onCreateProject(product)}>
            <FolderPlus className="mr-1.5 h-4 w-4" />
            {createProjectLabel}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="text-slate-500">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
              <DropdownMenuItem onSelect={() => onEditProduct(product)}>
                <Edit className="mr-2 h-4 w-4" />
                {editProductLabel}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onToggleProduct(product)}>
                <Power className="mr-2 h-4 w-4" />
                {product.is_active ? disableProductLabel : enableProductLabel}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-red-600 focus:text-red-600"
                onSelect={() => onDeleteProduct(product)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {deleteProductLabel}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      {expanded ? (
        projects.length === 0 ? (
          <div className="border-t border-slate-100 px-5 py-10 text-center">
            <Package2 className="mx-auto h-10 w-10 text-slate-200" />
            <p className="mt-3 text-sm font-medium text-slate-900">{noProjectsTitle}</p>
            <p className="mt-1 text-sm text-slate-500">
              {noProjectsDescription}
            </p>
          </div>
        ) : (
          <div>
            <div className="grid grid-cols-[minmax(0,2.3fr)_minmax(110px,0.8fr)_96px_88px_124px_48px] gap-4 border-t border-slate-100 bg-slate-50/50 px-5 py-3 text-xs font-medium text-slate-500">
              <div>{projectNameHeader}</div>
              <div>{projectCodeHeader}</div>
              <div>{appCountHeader}</div>
              <div>{statusHeader}</div>
              <div>{actionHeader}</div>
              <div />
            </div>
            {projects.map((project) => (
              <ProjectRow
                key={project.id}
                project={project}
                onEdit={onEditProject}
                onToggle={onToggleProject}
                onDelete={onDeleteProject}
              />
            ))}
          </div>
        )
      ) : null}
    </section>
  );
}
