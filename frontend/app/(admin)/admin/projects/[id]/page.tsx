"use client";

import {
  type PointerEvent as ReactPointerEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Bot,
  Code2,
  Copy,
  Edit,
  Eye,
  Link as LinkIcon,
  Loader2,
  MoreHorizontal,
  Plus,
  RefreshCcw,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import {
  assistantsApi,
  type AssistantSummary,
} from "@/lib/api/assistants";
import {
  listKnowledgeBaseBranches,
  listKnowledgeBases,
  type KnowledgeBaseBranch,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import { productsApi, type ProductResponse } from "@/lib/api/products";
import {
  projectsApi,
  type ProjectAppKnowledgeBaseBranchBinding,
  type ProjectAppEmbedPreviewResponse,
  type ProjectAppPayload,
  type ProjectAppResponse,
  type ProjectPayload,
  type ProjectResponse,
} from "@/lib/api/endpoints/projects";

interface ProjectFormState {
  name: string;
  code: string;
  description: string;
  product_id: string;
  is_active: boolean;
}

interface AppFormState {
  name: string;
  code: string;
  description: string;
  default_assistant_id: number | null;
  bindings: Array<{
    knowledge_base_id: string;
    knowledge_base_branch_id: string;
  }>;
  is_active: boolean;
}

const EMPTY_APP_FORM: AppFormState = {
  name: "",
  code: "",
  description: "",
  default_assistant_id: null,
  bindings: [{ knowledge_base_id: "", knowledge_base_branch_id: "" }],
  is_active: true,
};

const PREVIEW_DRAWER_MIN_WIDTH = 360;
const PREVIEW_DRAWER_MAX_MARGIN = 24;
const PREVIEW_DRAWER_DEFAULT_WIDTH = 920;

function clampPreviewDrawerWidth(width: number) {
  if (typeof window === "undefined") return width;
  const maxWidth = Math.max(
    PREVIEW_DRAWER_MIN_WIDTH,
    window.innerWidth - PREVIEW_DRAWER_MAX_MARGIN,
  );
  return Math.min(Math.max(width, PREVIEW_DRAWER_MIN_WIDTH), maxWidth);
}

function toProjectForm(project: ProjectResponse): ProjectFormState {
  return {
    name: project.name,
    code: project.code,
    description: project.description ?? "",
    product_id: String(project.product_id),
    is_active: project.is_active,
  };
}

function toProjectPayload(project: ProjectResponse, form: ProjectFormState): ProjectPayload {
  return {
    name: form.name.trim(),
    code: form.code.trim(),
    team_id: project.team_id,
    product_id: Number(form.product_id),
    description: form.description.trim() || null,
    is_active: form.is_active,
  };
}

function toAppForm(app: ProjectAppResponse): AppFormState {
  return {
    name: app.name,
    code: app.code,
    description: app.description ?? "",
    default_assistant_id: app.default_assistant_id ?? null,
    bindings:
      app.bindings.length > 0
        ? app.bindings.map((item) => ({
            knowledge_base_id: String(item.knowledge_base_id),
            knowledge_base_branch_id: String(item.knowledge_base_branch_id),
          }))
        : [{ knowledge_base_id: "", knowledge_base_branch_id: "" }],
    is_active: app.is_active,
  };
}

function toAppPayload(form: AppFormState): ProjectAppPayload {
  const bindings: ProjectAppKnowledgeBaseBranchBinding[] = form.bindings
    .filter((item) => item.knowledge_base_id && item.knowledge_base_branch_id)
    .map((item) => ({
      knowledge_base_id: Number(item.knowledge_base_id),
      knowledge_base_branch_id: Number(item.knowledge_base_branch_id),
    }));
  return {
    name: form.name.trim(),
    code: form.code.trim(),
    description: form.description.trim() || null,
    default_assistant_id: form.default_assistant_id,
    bindings,
    is_active: form.is_active,
  };
}

function getProjectId(rawId: string | string[] | undefined): number | null {
  const value = Array.isArray(rawId) ? rawId[0] : rawId;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export default function ProjectDetailsPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = getProjectId(params.id);

  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [apps, setApps] = useState<ProjectAppResponse[]>([]);
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [assistants, setAssistants] = useState<AssistantSummary[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [branchOptions, setBranchOptions] = useState<Record<number, KnowledgeBaseBranch[]>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [projectDialogOpen, setProjectDialogOpen] = useState(false);
  const [appDialogOpen, setAppDialogOpen] = useState(false);
  const [embedModalOpen, setEmbedModalOpen] = useState(false);
  const [previewDrawerOpen, setPreviewDrawerOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [projectForm, setProjectForm] = useState<ProjectFormState | null>(null);
  const [appForm, setAppForm] = useState<AppFormState>(EMPTY_APP_FORM);
  const [editingApp, setEditingApp] = useState<ProjectAppResponse | null>(null);
  const [selectedApp, setSelectedApp] = useState<ProjectAppResponse | null>(null);
  const [previewApp, setPreviewApp] = useState<ProjectAppResponse | null>(null);
  const [previewSession, setPreviewSession] = useState<ProjectAppEmbedPreviewResponse | null>(null);
  const [previewDrawerWidth, setPreviewDrawerWidth] = useState(PREVIEW_DRAWER_DEFAULT_WIDTH);

  const loadData = useCallback(async () => {
    if (projectId == null) {
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const nextProject = await projectsApi.get(projectId);
      const [nextApps, nextAssistants, nextProducts, nextKnowledgeBases] = await Promise.all([
        projectsApi.listApps(projectId),
        assistantsApi.list({ team_id: nextProject.team_id, active_only: true }),
        productsApi.list({ team_id: nextProject.team_id }),
        listKnowledgeBases(nextProject.team_id),
      ]);
      setProject(nextProject);
      setApps(nextApps);
      setAssistants(nextAssistants);
      setProducts(nextProducts);
      setKnowledgeBases(nextKnowledgeBases);
      const branchEntries = await Promise.all(
        nextKnowledgeBases.map(async (kb) => [kb.id, await listKnowledgeBaseBranches(kb.id)] as const),
      );
      setBranchOptions(Object.fromEntries(branchEntries));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载项目详情失败");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const addBindingRow = () => {
    setAppForm((current) => ({
      ...current,
      bindings: [...current.bindings, { knowledge_base_id: "", knowledge_base_branch_id: "" }],
    }));
  };

  const updateBindingRow = (
    index: number,
    patch: Partial<{ knowledge_base_id: string; knowledge_base_branch_id: string }>,
  ) => {
    setAppForm((current) => ({
      ...current,
      bindings: current.bindings.map((item, itemIndex) =>
        itemIndex === index
          ? {
              knowledge_base_id:
                patch.knowledge_base_id !== undefined ? patch.knowledge_base_id : item.knowledge_base_id,
              knowledge_base_branch_id:
                patch.knowledge_base_id !== undefined
                  ? ""
                  : patch.knowledge_base_branch_id !== undefined
                    ? patch.knowledge_base_branch_id
                    : item.knowledge_base_branch_id,
            }
          : item,
      ),
    }));
  };

  const removeBindingRow = (index: number) => {
    setAppForm((current) => ({
      ...current,
      bindings:
        current.bindings.length <= 1
          ? [{ knowledge_base_id: "", knowledge_base_branch_id: "" }]
          : current.bindings.filter((_, itemIndex) => itemIndex !== index),
    }));
  };

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const assistantOptions = useMemo(() => {
    if (!editingApp?.default_assistant_id) return assistants;
    if (assistants.some((assistant) => assistant.id === editingApp.default_assistant_id)) {
      return assistants;
    }
    return assistants;
  }, [assistants, editingApp]);

  const openProjectDialog = () => {
    if (!project) return;
    setProjectForm(toProjectForm(project));
    setProjectDialogOpen(true);
  };

  const saveProject = async () => {
    if (!project || !projectForm) return;
    if (!projectForm.name.trim() || !projectForm.code.trim() || !projectForm.product_id) {
      toast.error("项目名称和编码不能为空");
      return;
    }

    setSaving(true);
    try {
      const updated = await projectsApi.update(
        project.id,
        toProjectPayload(project, projectForm),
      );
      setProject(updated);
      setProjectDialogOpen(false);
      toast.success("项目已更新");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存项目失败");
    } finally {
      setSaving(false);
    }
  };

  const openCreateAppDialog = () => {
    setEditingApp(null);
    setAppForm(EMPTY_APP_FORM);
    setAppDialogOpen(true);
  };

  const openEditAppDialog = (app: ProjectAppResponse) => {
    setEditingApp(app);
    setAppForm(toAppForm(app));
    setAppDialogOpen(true);
  };

  const saveApp = async () => {
    if (!project) return;
    if (!appForm.name.trim() || !appForm.code.trim()) {
      toast.error("应用名称和编码不能为空");
      return;
    }

    setSaving(true);
    try {
      const payload = toAppPayload(appForm);
      if (editingApp) {
        await projectsApi.updateApp(project.id, editingApp.id, payload);
        toast.success("应用已更新");
      } else {
        await projectsApi.createApp(project.id, payload);
        toast.success("应用已创建");
      }
      setAppDialogOpen(false);
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存应用失败");
    } finally {
      setSaving(false);
    }
  };

  const toggleApp = async (app: ProjectAppResponse) => {
    if (!project) return;

    try {
      await projectsApi.updateApp(project.id, app.id, {
        name: app.name,
        code: app.code,
        description: app.description ?? null,
        default_assistant_id: app.default_assistant_id ?? null,
        bindings: app.bindings.map((binding) => ({
          knowledge_base_id: binding.knowledge_base_id,
          knowledge_base_branch_id: binding.knowledge_base_branch_id,
        })),
        is_active: !app.is_active,
      });
      toast.success(app.is_active ? "应用已停用" : "应用已启用");
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "切换应用状态失败");
    }
  };

  const deleteApp = async (app: ProjectAppResponse) => {
    if (!project) return;
    if (!window.confirm(`确认删除应用「${app.name}」吗？`)) {
      return;
    }

    try {
      await projectsApi.deleteApp(project.id, app.id);
      toast.success("应用已删除");
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除应用失败");
    }
  };

  const handleShowEmbed = (app: ProjectAppResponse) => {
    setSelectedApp(app);
    setEmbedModalOpen(true);
  };

  const openPreviewDrawer = async (app: ProjectAppResponse) => {
    if (!project) return;

    setPreviewApp(app);
    setPreviewSession(null);
    setPreviewLoading(true);
    setPreviewDrawerOpen(true);

    try {
      const session = await projectsApi.createEmbedPreview(project.id, app.id);
      setPreviewSession(session);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "生成预览链接失败");
    } finally {
      setPreviewLoading(false);
    }
  };

  const refreshPreviewDrawer = async () => {
    if (!previewApp || !project) return;

    setPreviewLoading(true);
    try {
      const session = await projectsApi.createEmbedPreview(project.id, previewApp.id);
      setPreviewSession(session);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "刷新预览失败");
    } finally {
      setPreviewLoading(false);
    }
  };

  const startPreviewDrawerResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    const handleElement = event.currentTarget;
    handleElement.setPointerCapture(event.pointerId);

    const updateWidth = (clientX: number) => {
      setPreviewDrawerWidth(clampPreviewDrawerWidth(window.innerWidth - clientX));
    };

    updateWidth(event.clientX);

    const handlePointerMove = (moveEvent: PointerEvent) => {
      updateWidth(moveEvent.clientX);
    };

    const handlePointerUp = (upEvent: PointerEvent) => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      if (handleElement.hasPointerCapture(upEvent.pointerId)) {
        handleElement.releasePointerCapture(upEvent.pointerId);
      }
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
  };

  const copyText = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success("已复制");
    } catch {
      toast.error("复制失败");
    }
  };

  if (projectId == null) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        项目 ID 无效
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在加载项目详情...
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-slate-500">
        <div>项目不存在或无权访问</div>
        <Button variant="outline" onClick={() => router.push("/admin/projects")}>
          返回项目列表
        </Button>
      </div>
    );
  }

  const embedSessionSnippet = `POST /api/v1/embed/sessions
Authorization: Bearer <ENTERPRISE_SERVICE_TOKEN>
Content-Type: application/json

{
  "product_code": "${project.product_code ?? "product_code"}",
  "project_code": "${project.code}",
  "app_code": "${selectedApp?.code ?? "app_code"}",
  "external_user_id": "YOUR_USER_ID",
  "external_user_name": "张三",
}`;

  const iframeSnippet = `<iframe
  src="{embed_url}"
  width="100%"
  height="100%"
  frameBorder="0"
></iframe>`;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-white px-8 py-6">
        <div className="mb-4">
          <Link
            href="/admin/projects"
            className="inline-flex items-center text-sm text-slate-500 transition-colors hover:text-slate-900"
          >
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            返回项目列表
          </Link>
        </div>
        <div className="flex items-start justify-between">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                {project.name}
              </h1>
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
            <div className="flex items-center gap-3 text-sm text-slate-500">
              <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">
                {project.code}
              </span>
              <span>·</span>
              <span>{project.description || "未填写描述"}</span>
            </div>
          </div>
          <Button variant="outline" className="shadow-sm" onClick={openProjectDialog}>
            编辑项目
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">应用管理</h2>
            <p className="mt-1 text-sm text-slate-500">
              每个应用可以绑定不同助手，从而使用不同知识库回答问题。
            </p>
          </div>
          <Button
            onClick={openCreateAppDialog}
            className="h-9 gap-2 bg-blue-600 shadow-sm hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            新建应用
          </Button>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="grid grid-cols-12 gap-4 border-b border-slate-100 bg-slate-50/50 px-6 py-3 text-sm font-medium text-slate-500">
            <div className="col-span-3">应用名称</div>
            <div className="col-span-2">应用编码</div>
            <div className="col-span-3">绑定助手</div>
            <div className="col-span-2">知识库</div>
            <div className="col-span-1">状态</div>
            <div className="col-span-1 text-right">操作</div>
          </div>
          {apps.length === 0 ? (
            <div className="py-12 text-center">
              <Bot className="mx-auto h-12 w-12 text-slate-200" />
              <h3 className="mt-4 text-sm font-medium text-slate-900">还没有应用</h3>
              <p className="mt-1 text-sm text-slate-500">
                创建应用后，业务端就可以按应用获取对应助手。
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {apps.map((app) => (
                <div
                  key={app.id}
                  className="grid grid-cols-12 items-center gap-4 px-6 py-4 transition-colors hover:bg-slate-50/50"
                >
                  <div className="col-span-3">
                    <div className="font-medium text-slate-900">{app.name}</div>
                    <div className="mt-0.5 truncate pr-4 text-xs text-slate-500">
                      {app.description || "未填写描述"}
                    </div>
                  </div>
                  <div className="col-span-2">
                    <code className="rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-600">
                      {app.code}
                    </code>
                  </div>
                  <div className="col-span-3">
                    {app.default_assistant_id ? (
                      <button
                        type="button"
                        onClick={() => openEditAppDialog(app)}
                        className="group flex items-center gap-2"
                      >
                        <span className="flex items-center gap-1.5 rounded-md border border-blue-100 bg-blue-50 px-2 py-1 text-blue-700 transition-colors group-hover:bg-blue-100">
                          <Bot className="h-3.5 w-3.5" />
                          <span className="text-xs font-medium">
                            {app.default_assistant_name || `#${app.default_assistant_id}`}
                          </span>
                        </span>
                        <span className="text-xs text-slate-400 opacity-0 transition-opacity group-hover:text-blue-600 group-hover:opacity-100">
                          更改
                        </span>
                      </button>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditAppDialog(app)}
                        className="h-7 border border-dashed border-slate-300 px-2 text-xs text-slate-500 hover:text-blue-600"
                      >
                        <LinkIcon className="mr-1.5 h-3 w-3" />
                        绑定助手
                      </Button>
                    )}
                  </div>
                  <div className="col-span-2 text-sm text-slate-500">
                    {app.bindings.length > 0
                      ? app.bindings
                          .map((item) => `${item.knowledge_base_name || "知识库"} / ${item.knowledge_base_branch_name || "版本"}`)
                          .join("、")
                      : app.knowledge_base_name || "--"}
                  </div>
                  <div className="col-span-1">
                    <span
                      className={`inline-flex items-center gap-1.5 text-sm ${
                        app.is_active ? "text-emerald-600" : "text-slate-400"
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          app.is_active ? "bg-emerald-500" : "bg-slate-300"
                        }`}
                      />
                      {app.is_active ? "正常" : "停用"}
                    </span>
                  </div>
                  <div className="col-span-1 flex justify-end gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 gap-1.5 shadow-sm"
                      onClick={() => void openPreviewDrawer(app)}
                    >
                      <Eye className="h-3.5 w-3.5 text-slate-500" />
                      预览
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 gap-1.5 shadow-sm"
                      onClick={() => handleShowEmbed(app)}
                    >
                      <Code2 className="h-3.5 w-3.5 text-slate-500" />
                      接入
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-500">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-36">
                        <DropdownMenuItem onSelect={() => openEditAppDialog(app)}>
                          <Edit className="h-4 w-4" />
                          编辑
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => void toggleApp(app)}>
                          {app.is_active ? "停用" : "启用"}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-red-600 focus:text-red-600"
                          onSelect={() => void deleteApp(app)}
                        >
                          <Trash2 className="h-4 w-4" />
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

      <Dialog open={projectDialogOpen} onOpenChange={setProjectDialogOpen}>
        <DialogContent className="sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>编辑项目</DialogTitle>
            <DialogDescription>修改项目基础信息。</DialogDescription>
          </DialogHeader>
          {projectForm && (
            <div className="space-y-4 py-2">
              <div className="grid gap-2">
                <label className="text-sm font-medium text-slate-700">Product</label>
                <select
                  value={projectForm.product_id}
                  onChange={(event) =>
                    setProjectForm((current) =>
                      current ? { ...current, product_id: event.target.value } : current,
                    )
                  }
                  className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
                >
                  <option value="">Select a product</option>
                  {products.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.name} ({product.code})
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-2">
                <label className="text-sm font-medium text-slate-700">项目名称</label>
                <Input
                  value={projectForm.name}
                  onChange={(event) =>
                    setProjectForm((current) =>
                      current ? { ...current, name: event.target.value } : current,
                    )
                  }
                />
              </div>
              <div className="grid gap-2">
                <label className="text-sm font-medium text-slate-700">项目编码</label>
                <Input
                  value={projectForm.code}
                  onChange={(event) =>
                    setProjectForm((current) =>
                      current ? { ...current, code: event.target.value } : current,
                    )
                  }
                />
              </div>
              <div className="grid gap-2">
                <label className="text-sm font-medium text-slate-700">描述</label>
                <Textarea
                  value={projectForm.description}
                  onChange={(event) =>
                    setProjectForm((current) =>
                      current ? { ...current, description: event.target.value } : current,
                    )
                  }
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={projectForm.is_active}
                  onChange={(event) =>
                    setProjectForm((current) =>
                      current ? { ...current, is_active: event.target.checked } : current,
                    )
                  }
                  className="h-4 w-4 rounded border-slate-300"
                />
                启用项目
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setProjectDialogOpen(false)}>
                  取消
                </Button>
                <Button onClick={() => void saveProject()} disabled={saving}>
                  {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  保存
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={appDialogOpen} onOpenChange={setAppDialogOpen}>
        <DialogContent className="sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>{editingApp ? "编辑应用" : "新建应用"}</DialogTitle>
            <DialogDescription>
              应用代表业务系统里的一个端，例如企业后台、销售小程序或客户小程序。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid gap-2">
              <label className="text-sm font-medium text-slate-700">应用名称</label>
              <Input
                value={appForm.name}
                onChange={(event) =>
                  setAppForm((current) => ({ ...current, name: event.target.value }))
                }
                placeholder="例如：销售小程序"
              />
            </div>
            <div className="grid gap-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">知识库版本绑定</label>
                <Button type="button" variant="outline" size="sm" onClick={addBindingRow}>
                  新增绑定
                </Button>
              </div>
              <div className="space-y-2">
                {appForm.bindings.map((binding, index) => {
                  const branchList = branchOptions[Number(binding.knowledge_base_id) || 0] || [];
                  return (
                    <div key={`${index}-${binding.knowledge_base_id}`} className="grid grid-cols-[1fr_1fr_auto] gap-2">
                      <select
                        value={binding.knowledge_base_id}
                        onChange={(event) =>
                          updateBindingRow(index, { knowledge_base_id: event.target.value })
                        }
                        className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50"
                      >
                        <option value="">选择知识库</option>
                        {knowledgeBases.map((kb) => (
                          <option key={kb.id} value={kb.id}>
                            {kb.name}
                          </option>
                        ))}
                      </select>
                      <select
                        value={binding.knowledge_base_branch_id}
                        onChange={(event) =>
                          updateBindingRow(index, { knowledge_base_branch_id: event.target.value })
                        }
                        className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50"
                        disabled={!binding.knowledge_base_id}
                      >
                        <option value="">选择版本</option>
                        {branchList
                          .filter((branch) => branch.is_active)
                          .map((branch) => (
                            <option key={branch.id} value={branch.id}>
                              {branch.name} / {branch.code}
                            </option>
                          ))}
                      </select>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removeBindingRow(index)}
                        className="h-10 w-10"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  );
                })}
              </div>
              <p className="text-xs text-slate-500">
                一个应用可以绑定多个知识库，但同一个知识库只能选择一个版本。
              </p>
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium text-slate-700">应用编码</label>
              <Input
                value={appForm.code}
                onChange={(event) =>
                  setAppForm((current) => ({ ...current, code: event.target.value }))
                }
                placeholder="例如：sales_miniapp"
              />
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium text-slate-700">默认助手</label>
              <select
                value={appForm.default_assistant_id ?? ""}
                onChange={(event) =>
                  setAppForm((current) => ({
                    ...current,
                    default_assistant_id: event.target.value
                      ? Number(event.target.value)
                      : null,
                  }))
                }
                className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50"
              >
                <option value="">暂不绑定</option>
                {assistantOptions.map((assistant) => (
                  <option key={assistant.id} value={assistant.id}>
                    {assistant.name}
                    {assistant.knowledge_base_name ? ` / ${assistant.knowledge_base_name}` : ""}
                  </option>
                ))}
              </select>
              {assistants.length === 0 && (
                <p className="text-xs text-amber-600">
                  当前团队还没有可用助手，请先在助手管理中创建并启用助手。
                </p>
              )}
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium text-slate-700">描述</label>
              <Textarea
                value={appForm.description}
                onChange={(event) =>
                  setAppForm((current) => ({ ...current, description: event.target.value }))
                }
                placeholder="应用面向的用户或业务场景"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={appForm.is_active}
                onChange={(event) =>
                  setAppForm((current) => ({ ...current, is_active: event.target.checked }))
                }
                className="h-4 w-4 rounded border-slate-300"
              />
              启用应用
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setAppDialogOpen(false)}>
                取消
              </Button>
              <Button onClick={() => void saveApp()} disabled={saving}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                保存
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={embedModalOpen} onOpenChange={setEmbedModalOpen}>
        <DialogContent className="sm:max-w-[640px]">
          <DialogHeader>
            <DialogTitle>嵌入式接入代码</DialogTitle>
            <DialogDescription>
              由企业后端创建短期 iframe 地址，前端只使用返回的 embed_url。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
              当前应用：{selectedApp?.name} /{" "}
              <span className="font-mono text-xs">{selectedApp?.code}</span>
            </div>
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-slate-900">
                1. 企业后端获取 embed_url
              </h4>
              <p className="text-xs text-slate-500">
                服务端请求必须携带 SynapseFlow 服务端 token，不要暴露给浏览器或小程序。
              </p>
              <div className="relative">
                <pre className="overflow-x-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-50">
                  <code>{embedSessionSnippet}</code>
                </pre>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => void copyText(embedSessionSnippet)}
                  className="absolute right-2 top-2 h-6 w-6 text-slate-400 hover:text-white"
                >
                  <Copy className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-slate-900">2. 前端嵌入 iframe</h4>
              <p className="text-xs text-slate-500">
                将上一步返回的 embed_url 放入 iframe src。
              </p>
              <div className="relative">
                <pre className="overflow-x-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-50">
                  <code>{iframeSnippet}</code>
                </pre>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => void copyText(iframeSnippet)}
                  className="absolute right-2 top-2 h-6 w-6 text-slate-400 hover:text-white"
                >
                  <Copy className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Sheet
        open={previewDrawerOpen}
        onOpenChange={(open) => {
          setPreviewDrawerOpen(open);
          if (!open) {
            setPreviewLoading(false);
            setPreviewApp(null);
            setPreviewSession(null);
          }
        }}
      >
        <SheetContent
          side="right"
          className="flex max-w-full flex-col overflow-hidden p-0"
          style={{
            width: previewDrawerWidth,
            maxWidth: `calc(100vw - ${PREVIEW_DRAWER_MAX_MARGIN}px)`,
          }}
        >
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="调整预览抽屉宽度"
            title="拖拽调整预览宽度"
            onPointerDown={startPreviewDrawerResize}
            className="absolute inset-y-0 left-0 z-30 w-2 -translate-x-1/2 cursor-col-resize touch-none"
          >
            <div className="mx-auto h-full w-1 rounded-full bg-transparent transition-colors hover:bg-blue-400/60" />
          </div>
          <SheetHeader className="border-b border-slate-200 bg-white px-5 py-4 pr-14">
            <div className="flex items-start justify-between gap-4">
              <div>
                <SheetTitle>Embed 预览</SheetTitle>
                <SheetDescription className="mt-1">
                  {previewApp ? `${previewApp.name} / ${previewApp.code}` : "应用嵌入预览"}
                </SheetDescription>
              </div>
              <div className="flex items-center gap-2">
                <span className="hidden rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-500 sm:inline-flex">
                  {previewDrawerWidth}px
                </span>
                {previewSession ? (
                  <span className="hidden rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-500 sm:inline-flex">
                    {previewSession.expires_in_seconds}s
                  </span>
                ) : null}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void refreshPreviewDrawer()}
                  disabled={previewLoading || previewApp == null}
                  className="gap-1.5"
                >
                  {previewLoading ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RefreshCcw className="h-3.5 w-3.5" />
                  )}
                  刷新
                </Button>
              </div>
            </div>
          </SheetHeader>
          <div className="min-h-0 flex-1 bg-slate-100">
            {previewLoading ? (
              <div className="flex h-full items-center justify-center">
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  正在生成预览链接...
                </div>
              </div>
            ) : previewSession?.embed_url ? (
              <iframe
                key={previewSession.embed_url}
                src={previewSession.embed_url}
                className="h-full w-full border-0 bg-white"
                title={previewApp ? `${previewApp.name} embed preview` : "Embed preview"}
              />
            ) : (
              <div className="flex h-full items-center justify-center px-6">
                <div className="max-w-md text-center">
                  <p className="text-sm font-medium text-slate-900">无法打开预览</p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    请确认应用已启用，且已绑定一个可用的默认助手。
                  </p>
                </div>
              </div>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
