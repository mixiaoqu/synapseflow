"use client";

import Link from "next/link";
import { Edit, MoreHorizontal, Power, Trash2 } from "lucide-react";

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

interface ProjectRowProps {
  project: ProjectResponse;
  onEdit: (project: ProjectResponse) => void;
  onToggle: (project: ProjectResponse) => void;
  onDelete: (project: ProjectResponse) => void;
}

export function ProjectRow(props: ProjectRowProps) {
  const { project, onEdit, onToggle, onDelete } = props;
  const emptyDescription = "暂未填写描述";
  const appsLabel = `${project.app_count} 个应用`;
  const activeLabel = "已启用";
  const inactiveLabel = "已停用";
  const enterConfigLabel = "进入配置";
  const editLabel = "编辑项目";
  const disableLabel = "停用项目";
  const enableLabel = "启用项目";
  const deleteLabel = "删除项目";

  return (
    <div className="grid grid-cols-[minmax(0,2.3fr)_minmax(110px,0.8fr)_96px_88px_124px_48px] items-center gap-4 border-t border-slate-100 px-5 py-4">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-slate-900">{project.name}</div>
        <div className="mt-1 truncate text-xs text-slate-500">
          {project.description || emptyDescription}
        </div>
      </div>
      <code className="w-fit rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">
        {project.code}
      </code>
      <span className="text-sm text-slate-600">{appsLabel}</span>
      <Badge
        variant={project.is_active ? "default" : "secondary"}
        className={project.is_active ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-50" : ""}
      >
        {project.is_active ? activeLabel : inactiveLabel}
      </Badge>
      <Button asChild variant="outline" size="sm" className="justify-self-start">
        <Link href={`/admin/projects/${project.id}`}>{enterConfigLabel}</Link>
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="justify-self-end text-slate-500">
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-40">
          <DropdownMenuItem onSelect={() => onEdit(project)}>
            <Edit className="mr-2 h-4 w-4" />
            {editLabel}
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => onToggle(project)}>
            <Power className="mr-2 h-4 w-4" />
            {project.is_active ? disableLabel : enableLabel}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-red-600 focus:text-red-600"
            onSelect={() => onDelete(project)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            {deleteLabel}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
