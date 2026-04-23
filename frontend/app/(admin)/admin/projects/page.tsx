"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Building2,
  Edit,
  Loader2,
  MoreHorizontal,
  Plus,
  Search,
  Settings,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  projectsApi,
  type ProjectPayload,
  type ProjectResponse,
} from "@/lib/api/endpoints/projects";

interface ProjectFormState {
  name: string;
  code: string;
  description: string;
  is_active: boolean;
}

const EMPTY_FORM: ProjectFormState = {
  name: "",
  code: "",
  description: "",
  is_active: true,
};

function toForm(project: ProjectResponse): ProjectFormState {
  return {
    name: project.name,
    code: project.code,
    description: project.description ?? "",
    is_active: project.is_active,
  };
}

function toPayload(form: ProjectFormState, teamId: number): ProjectPayload {
  return {
    name: form.name.trim(),
    code: form.code.trim(),
    team_id: teamId,
    description: form.description.trim() || null,
    is_active: form.is_active,
  };
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export default function ProjectsPage() {
  const { teamId, selectedTeam, teamsLoading } = useTeamScope();
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<ProjectResponse | null>(null);
  const [form, setForm] = useState<ProjectFormState>(EMPTY_FORM);

  const loadProjects = useCallback(async () => {
    if (teamId == null) {
      setProjects([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      setProjects(await projectsApi.list({ team_id: teamId }));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载项目失败");
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  const filteredProjects = useMemo(() => {
    const keyword = searchQuery.trim().toLowerCase();
    if (!keyword) return projects;
    return projects.filter(
      (project) =>
        project.name.toLowerCase().includes(keyword) ||
        project.code.toLowerCase().includes(keyword) ||
        (project.description ?? "").toLowerCase().includes(keyword),
    );
  }, [projects, searchQuery]);

  const openCreateDialog = () => {
    setEditingProject(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEditDialog = (project: ProjectResponse) => {
    setEditingProject(project);
    setForm(toForm(project));
    setDialogOpen(true);
  };

  const saveProject = async () => {
    if (teamId == null) {
      toast.error("请先选择团队");
      return;
    }
    if (!form.name.trim() || !form.code.trim()) {
      toast.error("项目名称和编码不能为空");
      return;
    }

    setSaving(true);
    try {
      const payload = toPayload(form, teamId);
      if (editingProject) {
        await projectsApi.update(editingProject.id, payload);
        toast.success("项目已更新");
      } else {
        await projectsApi.create(payload);
        toast.success("项目已创建");
      }
      setDialogOpen(false);
      await loadProjects();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存项目失败");
    } finally {
      setSaving(false);
    }
  };

  const toggleProject = async (project: ProjectResponse) => {
    try {
      await projectsApi.update(project.id, {
        name: project.name,
        code: project.code,
        team_id: project.team_id,
        description: project.description ?? null,
        is_active: !project.is_active,
      });
      toast.success(project.is_active ? "项目已停用" : "项目已启用");
      await loadProjects();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "切换项目状态失败");
    }
  };

  const deleteProject = async (project: ProjectResponse) => {
    if (!window.confirm(`确认删除项目「${project.name}」吗？项目下的应用也会一起删除。`)) {
      return;
    }

    try {
      await projectsApi.delete(project.id);
      toast.success("项目已删除");
      await loadProjects();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除项目失败");
    }
  };

  const noTeam = !teamsLoading && teamId == null;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-white px-8 py-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">项目管理</h1>
            <p className="mt-1 text-sm text-slate-500">
              管理企业项目和应用，将每个应用绑定到对应的问答助手。
              {selectedTeam ? ` 当前团队：${selectedTeam.name}` : ""}
            </p>
          </div>
          <Button
            onClick={openCreateDialog}
            disabled={teamId == null}
            className="gap-2 bg-blue-600 hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            新建项目
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center gap-4">
          <div className="relative w-72">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              placeholder="搜索项目名称或编码..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              className="h-10 border-slate-200 pl-9"
            />
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="grid grid-cols-12 gap-4 border-b border-slate-100 bg-slate-50/50 px-6 py-3 text-sm font-medium text-slate-500">
            <div className="col-span-3">项目名称</div>
            <div className="col-span-2">项目编码</div>
            <div className="col-span-2 text-center">应用数</div>
            <div className="col-span-2">状态</div>
            <div className="col-span-1">创建时间</div>
            <div className="col-span-2 text-right">操作</div>
          </div>

          {loading || teamsLoading ? (
            <div className="flex h-64 items-center justify-center text-sm text-slate-500">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              正在加载项目...
            </div>
          ) : noTeam ? (
            <div className="py-12 text-center">
              <Building2 className="mx-auto h-12 w-12 text-slate-200" />
              <h3 className="mt-4 text-sm font-medium text-slate-900">请先选择团队</h3>
              <p className="mt-1 text-sm text-slate-500">项目必须归属到一个团队。</p>
            </div>
          ) : filteredProjects.length === 0 ? (
            <div className="py-12 text-center">
              <Building2 className="mx-auto h-12 w-12 text-slate-200" />
              <h3 className="mt-4 text-sm font-medium text-slate-900">未找到项目</h3>
              <p className="mt-1 text-sm text-slate-500">
                可以调整搜索词，或新建一个项目。
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {filteredProjects.map((project) => (
                <div
                  key={project.id}
                  className="grid grid-cols-12 items-center gap-4 px-6 py-4 transition-colors hover:bg-slate-50/50"
                >
                  <div className="col-span-3 flex flex-col">
                    <span className="font-medium text-slate-900">{project.name}</span>
                    <span className="mt-0.5 truncate pr-4 text-xs text-slate-500">
                      {project.description || "未填写描述"}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <code className="rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-600">
                      {project.code}
                    </code>
                  </div>
                  <div className="col-span-2 text-center">
                    <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-slate-100 px-2 text-xs font-medium text-slate-600">
                      {project.app_count}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <Badge
                      variant={project.is_active ? "default" : "secondary"}
                      className={
                        project.is_active
                          ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-50"
                          : ""
                      }
                    >
                      {project.is_active ? "已启用" : "已停用"}
                    </Badge>
                  </div>
                  <div className="col-span-1 text-sm text-slate-500">
                    {formatDate(project.created_at)}
                  </div>
                  <div className="col-span-2 flex justify-end gap-2">
                    <Button variant="outline" size="sm" asChild className="h-8 shadow-sm">
                      <Link href={`/admin/projects/${project.id}`}>应用配置</Link>
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-500">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-36">
                        <DropdownMenuItem onSelect={() => openEditDialog(project)}>
                          <Edit className="mr-2 h-4 w-4 text-slate-400" />
                          编辑
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => void toggleProject(project)}>
                          <Settings className="mr-2 h-4 w-4 text-slate-400" />
                          {project.is_active ? "停用" : "启用"}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-red-600 focus:text-red-600"
                          onSelect={() => void deleteProject(project)}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          删除
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>{editingProject ? "编辑项目" : "新建项目"}</DialogTitle>
            <DialogDescription>
              项目用于区分业务系统，项目下可以创建多个应用。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid gap-2">
              <label className="text-sm font-medium text-slate-700">项目名称</label>
              <Input
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="例如：客户管理 CRM"
              />
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium text-slate-700">项目编码</label>
              <Input
                value={form.code}
                onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
                placeholder="例如：customer_crm"
              />
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium text-slate-700">描述</label>
              <Textarea
                value={form.description}
                onChange={(event) =>
                  setForm((current) => ({ ...current, description: event.target.value }))
                }
                placeholder="项目的业务范围或使用场景"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) =>
                  setForm((current) => ({ ...current, is_active: event.target.checked }))
                }
                className="h-4 w-4 rounded border-slate-300"
              />
              启用项目
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                取消
              </Button>
              <Button onClick={() => void saveProject()} disabled={saving}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                保存
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
