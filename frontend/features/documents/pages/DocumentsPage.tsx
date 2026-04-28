"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChangeEvent, DragEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Database,
  FileText,
  Loader2,
  MoreHorizontal,
  PencilLine,
  Plus,
  Search,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { Toaster, toast } from "sonner";

import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  uploadDocument,
  uploadDocumentsBatch,
} from "@/lib/api/documents";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  listKnowledgeBases,
  updateKnowledgeBase,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import { cn } from "@/lib/utils";

const ACCEPT_FILES = ".txt,.md,.pdf,.docx";
const SUPPORTED_EXTENSIONS = new Set([".txt", ".md", ".pdf", ".docx"]);
const MAX_SIZE = 10 * 1024 * 1024;
const MAX_BATCH = 500;

type KnowledgeBaseCardTone = "danger" | "warning" | "review" | "info" | "success" | "muted";
type KnowledgeBaseCardAction = "failed" | "indexing" | "pending_review" | "submittable" | "upload";

const cardToneMeta: Record<
  KnowledgeBaseCardTone,
  {
    border: string;
    stripe: string;
    chip: string;
    headline: string;
    shadow?: string;
  }
> = {
  danger: {
    border: "border-rose-300",
    stripe: "bg-rose-500",
    chip: "border-rose-200 bg-rose-50 text-rose-700",
    headline: "text-rose-700",
    shadow: "shadow-rose-100",
  },
  warning: {
    border: "border-amber-300",
    stripe: "bg-amber-500",
    chip: "border-amber-200 bg-amber-50 text-amber-700",
    headline: "text-amber-700",
  },
  review: {
    border: "border-orange-300",
    stripe: "bg-orange-500",
    chip: "border-orange-200 bg-orange-50 text-orange-700",
    headline: "text-orange-700",
  },
  info: {
    border: "border-blue-300",
    stripe: "bg-blue-500",
    chip: "border-blue-200 bg-blue-50 text-blue-700",
    headline: "text-blue-700",
  },
  success: {
    border: "border-emerald-300",
    stripe: "bg-emerald-500",
    chip: "border-emerald-200 bg-emerald-50 text-emerald-700",
    headline: "text-emerald-700",
  },
  muted: {
    border: "border-slate-200",
    stripe: "bg-slate-300",
    chip: "border-slate-200 bg-slate-100 text-slate-600",
    headline: "text-slate-600",
  },
};

function formatDateTime(value?: string | null) {
  if (!value) return "暂无";
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function getIndexingCount(knowledgeBase: KnowledgeBaseWithCount) {
  return knowledgeBase.queued_document_count + knowledgeBase.processing_document_count;
}

function getCardSummary(knowledgeBase: KnowledgeBaseWithCount): {
  label: string;
  headline: string;
  tone: KnowledgeBaseCardTone;
  action: KnowledgeBaseCardAction;
  actionLabel: string;
} {
  const indexingCount = getIndexingCount(knowledgeBase);

  if (knowledgeBase.failed_document_count > 0) {
    return {
      label: `索引失败 ${knowledgeBase.failed_document_count}`,
      headline: `${knowledgeBase.failed_document_count} 篇文档索引失败`,
      tone: "danger",
      action: "failed",
      actionLabel: "查看失败",
    };
  }
  if (indexingCount > 0) {
    return {
      label: `索引中 ${indexingCount}`,
      headline: `${indexingCount} 篇文档正在索引`,
      tone: "warning",
      action: "indexing",
      actionLabel: "查看进度",
    };
  }
  if (knowledgeBase.pending_review_document_count > 0) {
    return {
      label: `待审核 ${knowledgeBase.pending_review_document_count}`,
      headline: `${knowledgeBase.pending_review_document_count} 篇文档待审核`,
      tone: "review",
      action: "pending_review",
      actionLabel: "审核文档",
    };
  }
  if (knowledgeBase.submittable_document_count > 0) {
    return {
      label: `可提交审核 ${knowledgeBase.submittable_document_count}`,
      headline: `${knowledgeBase.submittable_document_count} 篇文档可提交审核`,
      tone: "info",
      action: "submittable",
      actionLabel: "提交审核",
    };
  }
  if (knowledgeBase.published_document_count > 0) {
    return {
      label: `已发布 ${knowledgeBase.published_document_count}`,
      headline: `${knowledgeBase.published_document_count} 篇文档已发布`,
      tone: "success",
      action: "upload",
      actionLabel: "上传文档",
    };
  }
  return {
    label: "空知识库",
    headline: "还没有文档",
    tone: "muted",
    action: "upload",
    actionLabel: "上传文档",
  };
}

type ConfirmDialogState = {
  open: boolean;
  title: string;
  description: string;
  contextRows?: Array<{ label: string; value: string }>;
  confirmLabel: string;
  tone: "primary" | "danger";
  onConfirm: null | (() => void | Promise<void>);
};

function validateFiles(files: File[] | FileList) {
  const allFiles = Array.from(files);
  const acceptedBeforeCap: File[] = [];
  let invalidTypeCount = 0;
  let oversizeCount = 0;
  for (const file of allFiles) {
    const ext = "." + (file.name.split(".").pop()?.toLowerCase() || "");
    if (!SUPPORTED_EXTENSIONS.has(ext)) {
      invalidTypeCount += 1;
      continue;
    }
    if (file.size > MAX_SIZE) {
      oversizeCount += 1;
      continue;
    }
    acceptedBeforeCap.push(file);
  }
  return {
    accepted: acceptedBeforeCap,
    invalidTypeCount,
    oversizeCount,
  };
}

function getSourcePaths(files: File[]) {
  const paths = files.map((file) => file.webkitRelativePath || null);
  return paths.some(Boolean) ? paths : undefined;
}

export default function DocumentsPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const {
    teamId: selectedTeamId,
    teamsLoading,
    selectedTeam: activeTeam,
  } = useTeamScope();

  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState<number | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [loadingKnowledgeBases, setLoadingKnowledgeBases] = useState(false);
  const [creatingKnowledgeBase, setCreatingKnowledgeBase] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingKnowledgeBaseId, setEditingKnowledgeBaseId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [savingKnowledgeBase, setSavingKnowledgeBase] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadCollectionId, setUploadCollectionId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deletingKnowledgeBaseId, setDeletingKnowledgeBaseId] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState>({
    open: false,
    title: "",
    description: "",
    confirmLabel: "确认",
    tone: "primary",
    onConfirm: null,
  });

  const displayedKnowledgeBases = useMemo(() => {
    const q = keyword.trim().toLowerCase();
    if (!q) return knowledgeBases;
    return knowledgeBases.filter((item) =>
      [item.name, item.description || ""].some((value) => value.toLowerCase().includes(q)),
    );
  }, [keyword, knowledgeBases]);
  const uploadTargetKnowledgeBase = useMemo(
    () => knowledgeBases.find((item) => item.id === uploadCollectionId) ?? null,
    [knowledgeBases, uploadCollectionId],
  );

  const loadKnowledgeBases = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
    if (selectedTeamId == null) {
      setKnowledgeBases([]);
      setSelectedKnowledgeBaseId(null);
      setUploadCollectionId(null);
      return;
    }
    if (!silent) setLoadingKnowledgeBases(true);
    try {
      const list = await listKnowledgeBases(selectedTeamId);
      setKnowledgeBases(list);
      setSelectedKnowledgeBaseId((prev) =>
        prev && list.some((item) => item.id === prev) ? prev : list[0]?.id ?? null,
      );
      setUploadCollectionId((prev) =>
        prev && list.some((item) => item.id === prev) ? prev : list[0]?.id ?? null,
      );
    } catch {
      if (!silent) {
        toast.error("加载知识库失败");
        setKnowledgeBases([]);
        setSelectedKnowledgeBaseId(null);
        setUploadCollectionId(null);
      }
    } finally {
      if (!silent) setLoadingKnowledgeBases(false);
    }
  }, [selectedTeamId]);

  useEffect(() => {
    if (teamsLoading) return;
    void loadKnowledgeBases();
  }, [loadKnowledgeBases, teamsLoading]);

  useEffect(() => {
    if (!knowledgeBases.some((item) => item.status === "indexing")) return undefined;
    const timer = window.setTimeout(() => {
      void loadKnowledgeBases({ silent: true });
    }, 8000);
    return () => window.clearTimeout(timer);
  }, [knowledgeBases, loadKnowledgeBases]);

  const closeConfirmDialog = () => {
    setConfirmDialog((prev) => ({
      ...prev,
      open: false,
      onConfirm: null,
    }));
  };

  const openConfirmDialog = (options: Omit<ConfirmDialogState, "open">) => {
    setConfirmDialog({
      open: true,
      ...options,
    });
  };

  const runConfirmedAction = () => {
    const action = confirmDialog.onConfirm;
    closeConfirmDialog();
    if (!action) return;
    void Promise.resolve(action());
  };

  const openCreateModal = () => {
    if (selectedTeamId == null) return toast.error("请先选择团队");
    setCreateName("");
    setCreateDescription("");
    setCreateModalOpen(true);
  };

  const openEditModal = (knowledgeBase: KnowledgeBaseWithCount) => {
    setEditingKnowledgeBaseId(knowledgeBase.id);
    setEditName(knowledgeBase.name);
    setEditDescription(knowledgeBase.description || "");
    setEditModalOpen(true);
  };

  const openUploadModal = (knowledgeBaseId?: number) => {
    const targetId = knowledgeBaseId ?? selectedKnowledgeBaseId ?? knowledgeBases[0]?.id ?? null;
    if (!targetId) return toast.error("请先创建知识库，再上传文档");
    setUploadCollectionId(targetId);
    setDragOver(false);
    setUploadModalOpen(true);
  };

  const openKnowledgeBase = (knowledgeBaseId: number) => {
    const query = new URLSearchParams();
    if (selectedTeamId != null) query.set("teamId", String(selectedTeamId));
    router.push(`/admin/documents/${knowledgeBaseId}${query.toString() ? `?${query.toString()}` : ""}`);
  };

  const handleCreateKnowledgeBase = async () => {
    if (!createName.trim() || selectedTeamId == null) return;
    setCreatingKnowledgeBase(true);
    try {
      const created = await createKnowledgeBase(
        createName.trim(),
        selectedTeamId,
        createDescription.trim() || undefined,
      );
      toast.success("知识库已创建");
      setCreateModalOpen(false);
      await loadKnowledgeBases();
      setSelectedKnowledgeBaseId(created.id);
      setUploadCollectionId(created.id);
    } catch (error: unknown) {
      toast.error((error as { message?: string }).message || "创建知识库失败");
    } finally {
      setCreatingKnowledgeBase(false);
    }
  };

  const handleEditKnowledgeBase = async () => {
    if (!editName.trim() || editingKnowledgeBaseId == null) return;

    setSavingKnowledgeBase(true);
    try {
      await updateKnowledgeBase(editingKnowledgeBaseId, {
        name: editName.trim(),
        description: editDescription.trim() || undefined,
      });
      toast.success("知识库已更新");
      setEditModalOpen(false);
      await loadKnowledgeBases();
    } catch (error: unknown) {
      toast.error((error as { message?: string }).message || "更新失败");
    } finally {
      setSavingKnowledgeBase(false);
    }
  };

  const handleDeleteKnowledgeBase = (knowledgeBase: KnowledgeBaseWithCount) => {
    openConfirmDialog({
      title: "删除这个知识库？",
      description: `“${knowledgeBase.name}”会被删除，文档会从知识库解绑。此操作不可恢复。`,
      contextRows: [
        { label: "当前团队", value: activeTeam?.name || "未选择团队" },
        { label: "目标知识库", value: knowledgeBase.name },
        { label: "包含文档", value: `${knowledgeBase.document_count} 篇` },
      ],
      confirmLabel: "确认删除",
      tone: "danger",
      onConfirm: async () => {
        setDeletingKnowledgeBaseId(knowledgeBase.id);
        try {
          await deleteKnowledgeBase(knowledgeBase.id);
          toast.success("知识库已删除");
          await loadKnowledgeBases();
        } catch (error: unknown) {
          toast.error((error as { message?: string }).message || "删除失败");
        } finally {
          setDeletingKnowledgeBaseId(null);
        }
      },
    });
  };

  const uploadFiles = async (files: File[] | FileList | null) => {
    if (!files || files.length === 0) return;
    if (files.length > MAX_BATCH) {
      toast.error(`单次最多上传 ${MAX_BATCH} 个文件，请减少文件数量后重试`);
      return;
    }

    const { accepted, invalidTypeCount, oversizeCount } = validateFiles(files);
    if (accepted.length === 0) return toast.error("没有符合要求的文件，请检查格式或大小限制");

    setUploading(true);
    try {
      const knowledgeBaseId =
        uploadCollectionId && uploadCollectionId > 0 ? uploadCollectionId : undefined;
      const sourcePaths = getSourcePaths(accepted);
      if (accepted.length === 1) {
        await uploadDocument(accepted[0], knowledgeBaseId, {
          sourcePath: sourcePaths?.[0] ?? null,
        });
      } else {
        await uploadDocumentsBatch(accepted, knowledgeBaseId, {
          sourcePaths,
        });
      }

      const notes: string[] = [];
      if (invalidTypeCount > 0) notes.push(`${invalidTypeCount} 个格式不支持`);
      if (oversizeCount > 0) notes.push(`${oversizeCount} 个超过 10MB`);
      toast.success(
        notes.length
          ? `已上传 ${accepted.length} 个文件，并加入索引队列，${notes.join("，")}`
          : `已上传 ${accepted.length} 个文件，并加入索引队列`,
      );
      setUploadModalOpen(false);
      await loadKnowledgeBases();
    } catch (error: unknown) {
      toast.error((error as { message?: string }).message || "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragOver(false);
    void uploadFiles(event.dataTransfer.files);
  };

  const onFileSelect = (event: ChangeEvent<HTMLInputElement>) => {
    void uploadFiles(event.target.files);
    event.target.value = "";
  };

  const isLoading = teamsLoading || loadingKnowledgeBases;
  const hasKnowledgeBases = knowledgeBases.length > 0;

  return (
    <div className="flex min-h-full flex-col bg-gray-50 text-slate-900">
      <Toaster position="top-right" richColors />
      <header className="px-4 pt-6 sm:px-6">
        <div className="mx-auto max-w-[1700px]">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-900">团队知识库</h1>
              <p className="mt-1 text-sm text-slate-500">
                {activeTeam
                  ? `${activeTeam.name} · ${knowledgeBases.length} 个知识库`
                  : "正在加载团队信息..."}
              </p>
            </div>

            <div className="flex w-full max-w-[820px] flex-col gap-2 lg:flex-row lg:items-center">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  onKeyDown={(event) => event.key === "Enter" && setKeyword(searchInput.trim())}
                  placeholder="搜索知识库名称或描述"
                  className="h-11 rounded-xl border-slate-200 bg-white pl-10 text-slate-800 placeholder:text-slate-400"
                />
              </div>
              <Button
                variant="outline"
                onClick={() => setKeyword(searchInput.trim())}
                className="h-11 rounded-xl border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
              >
                搜索
              </Button>
              <Button
                variant="outline"
                onClick={openCreateModal}
                className="h-11 rounded-xl border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
              >
                <Plus className="mr-2 h-4 w-4" />
                新建知识库
              </Button>
              <Button
                onClick={() => openUploadModal()}
                disabled={!hasKnowledgeBases}
                className="h-11 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:bg-slate-300"
              >
                <UploadCloud className="mr-2 h-4 w-4" />
                上传文档
              </Button>
            </div>
          </div>

          {!hasKnowledgeBases && !isLoading ? (
            <p className="mt-4 text-sm text-amber-700">
              当前团队还没有知识库。先创建知识库，再上传文档会更顺畅。
            </p>
          ) : null}
        </div>
      </header>
      <main className="flex-1 px-4 pb-8 pt-4 sm:px-6">
        <section className="mx-auto max-w-[1700px]">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-500">
            <span>{isLoading ? "正在同步团队与知识库内容..." : `共找到 ${displayedKnowledgeBases.length} 个知识库`}</span>
            <span>{activeTeam?.name || "未选择团队"}</span>
          </div>

          {displayedKnowledgeBases.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center shadow-sm">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
                <Database className="h-8 w-8" />
              </div>
              <h2 className="mt-5 text-2xl font-semibold text-slate-900">
                {keyword ? "没有找到匹配的知识库" : "还没有知识库"}
              </h2>
              <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-500">
                {keyword
                  ? "可以尝试更换关键词，或者直接新建一个知识库。"
                  : "先创建一个知识库，再上传文档、建立索引并进入详细工作区。"}
              </p>
              <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                <Button onClick={openCreateModal} className="rounded-xl bg-blue-600 text-white hover:bg-blue-700">
                  <Plus className="mr-2 h-4 w-4" />
                  新建知识库
                </Button>
                {keyword ? (
                  <Button variant="outline" className="rounded-xl border-slate-200" onClick={() => {
                    setSearchInput("");
                    setKeyword("");
                  }}>
                    清空搜索
                  </Button>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {displayedKnowledgeBases.map((knowledgeBase) => {
                const active = selectedKnowledgeBaseId === knowledgeBase.id;
                const indexingCount = getIndexingCount(knowledgeBase);
                const cardSummary = getCardSummary(knowledgeBase);
                const tone = cardToneMeta[cardSummary.tone];
                const runPrimaryAction = () => {
                  setSelectedKnowledgeBaseId(knowledgeBase.id);
                  if (cardSummary.action === "upload") {
                    openUploadModal(knowledgeBase.id);
                    return;
                  }
                  if (
                    cardSummary.action === "pending_review" ||
                    cardSummary.action === "submittable"
                  ) {
                    const filter =
                      cardSummary.action === "pending_review" ? "pending_review" : "draft";
                    router.push(`/admin/review?filter=${filter}`);
                    return;
                  }
                  openKnowledgeBase(knowledgeBase.id);
                };

                return (
                  <div
                    key={knowledgeBase.id}
                    className={cn(
                      "group relative flex h-full min-h-[300px] flex-col overflow-hidden rounded-2xl border bg-white shadow-sm transition-all hover:-translate-y-1 hover:shadow-md",
                      active ? "ring-4 ring-blue-50" : "",
                      tone.border,
                      tone.shadow,
                    )}
                  >
                    <div className={cn("absolute inset-y-0 left-0 w-1", tone.stripe)} />
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedKnowledgeBaseId(knowledgeBase.id);
                        openKnowledgeBase(knowledgeBase.id);
                      }}
                      className="flex flex-1 flex-col text-left outline-none"
                    >
                      <div className="flex flex-1 flex-col p-5 pl-6">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <span className="inline-flex text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                              知识库
                            </span>
                            <h3 className="mt-2 truncate text-lg font-bold text-slate-900 transition-colors group-hover:text-blue-700">
                              {knowledgeBase.name}
                            </h3>
                          </div>
                          <div
                            className={cn(
                              "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
                              tone.chip,
                            )}
                          >
                            {cardSummary.tone === "danger" ? (
                              <AlertTriangle className="h-3.5 w-3.5" />
                            ) : cardSummary.tone === "warning" ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : cardSummary.tone === "muted" ? (
                              <FileText className="h-3.5 w-3.5" />
                            ) : (
                              <span className={cn("h-2 w-2 rounded-full", tone.stripe)} />
                            )}
                            {cardSummary.label}
                          </div>
                        </div>
                        <p className="mt-1.5 line-clamp-2 text-sm text-slate-500">
                          {knowledgeBase.description || "围绕单个主题集中组织文档、检索与问答。"}
                        </p>

                        <div className="mt-5">
                          <p className={cn("text-lg font-semibold", tone.headline)}>
                            {cardSummary.headline}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            最近上传 {formatDateTime(knowledgeBase.last_uploaded_at)}
                          </p>
                        </div>

                        <div className="mt-5 grid grid-cols-3 gap-2">
                          {[
                            {
                              label: "可提交审核",
                              value: knowledgeBase.submittable_document_count,
                              className: "text-blue-700",
                            },
                            {
                              label: "待审核",
                              value: knowledgeBase.pending_review_document_count,
                              className: "text-orange-700",
                            },
                            {
                              label: "已发布",
                              value: knowledgeBase.published_document_count,
                              className: "text-emerald-700",
                            },
                            {
                              label: "索引中",
                              value: indexingCount,
                              className: "text-amber-700",
                            },
                            {
                              label: "失败",
                              value: knowledgeBase.failed_document_count,
                              className: "text-rose-700",
                            },
                            {
                              label: "总文档",
                              value: knowledgeBase.document_count,
                              className: "text-slate-700",
                            },
                          ].map((item) => (
                            <div key={item.label} className="rounded-xl bg-slate-50 px-3 py-2">
                              <p className="truncate text-[11px] font-medium text-slate-400">
                                {item.label}
                              </p>
                              <p className={cn("mt-1 text-base font-semibold", item.className)}>
                                {item.value}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </button>

                    <div className="flex items-center justify-between gap-3 border-t border-slate-100 bg-white px-4 py-3 pl-5">
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <span>更新于 {formatDateTime(knowledgeBase.updated_at)}</span>
                        {indexingCount > 0 && (
                          <span className="flex items-center gap-1 text-amber-600">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            处理中...
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-1.5">
                        <Button
                          size="sm"
                          className={cn(
                            "h-8 rounded-lg px-3 text-xs text-white",
                            cardSummary.tone === "danger"
                              ? "bg-rose-600 hover:bg-rose-700"
                              : cardSummary.tone === "warning" || cardSummary.tone === "review"
                                ? "bg-amber-600 hover:bg-amber-700"
                                : cardSummary.tone === "info"
                                  ? "bg-blue-600 hover:bg-blue-700"
                                  : "bg-slate-900 hover:bg-slate-800",
                          )}
                          onClick={runPrimaryAction}
                        >
                          {cardSummary.action === "upload" ? (
                            <UploadCloud className="mr-1.5 h-4 w-4" />
                          ) : null}
                          {cardSummary.actionLabel}
                        </Button>
                        {cardSummary.action !== "upload" ? (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-8 rounded-lg border-slate-200 bg-white text-xs text-slate-600 hover:bg-slate-50"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedKnowledgeBaseId(knowledgeBase.id);
                              openUploadModal(knowledgeBase.id);
                            }}
                          >
                            <UploadCloud className="mr-1.5 h-4 w-4" />
                            上传
                          </Button>
                        ) : null}

                        <DropdownMenu.Root>
                          <DropdownMenu.Trigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 rounded-lg px-0 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                              onClick={(e) => e.stopPropagation()}
                              aria-label="更多操作"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenu.Trigger>
                          <DropdownMenu.Portal>
                            <DropdownMenu.Content
                              side="bottom"
                              align="end"
                              sideOffset={8}
                              className="z-50 min-w-[160px] rounded-xl border border-slate-200 bg-white p-1.5 text-sm shadow-xl"
                            >
                              <DropdownMenu.Item
                                onSelect={() => openEditModal(knowledgeBase)}
                                className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2 text-slate-700 outline-none transition-colors hover:bg-slate-100 focus:bg-slate-100"
                              >
                                <PencilLine className="h-4 w-4" />
                                编辑知识库
                              </DropdownMenu.Item>
                              <DropdownMenu.Item
                                onSelect={() =>
                                  void navigator.clipboard
                                    .writeText(String(knowledgeBase.id))
                                    .then(() => toast.success("知识库 ID 已复制"))
                                    .catch(() => toast.error("复制失败"))
                                }
                                className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2 text-slate-700 outline-none transition-colors hover:bg-slate-100 focus:bg-slate-100"
                              >
                                <FileText className="h-4 w-4" />
                                复制知识库 ID
                              </DropdownMenu.Item>
                              <DropdownMenu.Separator className="my-1 h-px bg-slate-200" />
                              <DropdownMenu.Item
                                onSelect={() => handleDeleteKnowledgeBase(knowledgeBase)}
                                disabled={deletingKnowledgeBaseId === knowledgeBase.id}
                                className={cn(
                                  "flex select-none items-center gap-2 rounded-lg px-3 py-2 outline-none transition-colors",
                                  deletingKnowledgeBaseId === knowledgeBase.id
                                    ? "cursor-not-allowed text-rose-300"
                                    : "cursor-pointer text-rose-600 hover:bg-rose-50 focus:bg-rose-50",
                                )}
                              >
                                {deletingKnowledgeBaseId === knowledgeBase.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <Trash2 className="h-4 w-4" />
                                )}
                                删除知识库
                              </DropdownMenu.Item>
                            </DropdownMenu.Content>
                          </DropdownMenu.Portal>
                        </DropdownMenu.Root>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </main>
      {createModalOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
          onClick={() => !creatingKnowledgeBase && setCreateModalOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-semibold text-slate-900">新建知识库</h3>
                <p className="hidden">
                  为当前团队创建一个新的知识库，后续可以继续上传文档并进入详细工作区。
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  选择目标知识库后上传文件。
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => !creatingKnowledgeBase && setCreateModalOpen(false)}
                className="rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-5 space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">所属团队</label>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-600">
                  {activeTeam?.name || "未选择团队"}
                </div>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">知识库名称</label>
                <Input
                  value={createName}
                  onChange={(event) => setCreateName(event.target.value)}
                  placeholder="例如：产品文档、实施规范、培训资料"
                  className="h-11 rounded-xl border-slate-200"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">知识库描述</label>
                <Textarea
                  value={createDescription}
                  onChange={(event) => setCreateDescription(event.target.value)}
                  placeholder="简要说明这个知识库会包含什么内容，方便团队后续搜索和管理。"
                  className="min-h-[120px] rounded-xl border-slate-200"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => !creatingKnowledgeBase && setCreateModalOpen(false)} className="rounded-xl border-slate-200">
                  取消
                </Button>
                <Button
                  onClick={() => void handleCreateKnowledgeBase()}
                  disabled={creatingKnowledgeBase || !createName.trim() || selectedTeamId == null}
                  className="rounded-xl bg-blue-600 text-white hover:bg-blue-700"
                >
                  {creatingKnowledgeBase ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Plus className="mr-2 h-4 w-4" />
                  )}
                  创建知识库
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
      {editModalOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
          onClick={() => !savingKnowledgeBase && setEditModalOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-semibold text-slate-900">编辑知识库</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  可以更新知识库名称和概述，方便团队后续识别和管理。
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => !savingKnowledgeBase && setEditModalOpen(false)}
                className="rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-5 space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">所属团队</label>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-600">
                  {activeTeam?.name || "未选择团队"}
                </div>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">知识库名称</label>
                <Input
                  value={editName}
                  onChange={(event) => setEditName(event.target.value)}
                  placeholder="例如：产品文档、实施规范、培训资料"
                  className="h-11 rounded-xl border-slate-200"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">知识库概述</label>
                <Textarea
                  value={editDescription}
                  onChange={(event) => setEditDescription(event.target.value)}
                  placeholder="补充这个知识库包含的内容范围，方便团队理解。"
                  className="min-h-[120px] rounded-xl border-slate-200"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => !savingKnowledgeBase && setEditModalOpen(false)}
                  className="rounded-xl border-slate-200"
                >
                  取消
                </Button>
                <Button
                  onClick={() => void handleEditKnowledgeBase()}
                  disabled={savingKnowledgeBase || !editName.trim() || editingKnowledgeBaseId == null}
                  className="rounded-xl bg-blue-600 text-white hover:bg-blue-700"
                >
                  {savingKnowledgeBase ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <PencilLine className="mr-2 h-4 w-4" />
                  )}
                  保存修改
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
      {confirmDialog.open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
          onClick={closeConfirmDialog}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-semibold text-slate-900">{confirmDialog.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  {confirmDialog.description}
                </p>
                {confirmDialog.contextRows?.length ? (
                  <div className="mt-4 space-y-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm">
                    {confirmDialog.contextRows.map((row) => (
                      <div key={row.label} className="flex items-center justify-between gap-4">
                        <span className="text-slate-500">{row.label}</span>
                        <span className="min-w-0 truncate font-medium text-slate-800">
                          {row.value}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={closeConfirmDialog}
                className="rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-6 flex items-center justify-end gap-2">
              <Button variant="outline" onClick={closeConfirmDialog} className="rounded-xl border-slate-200">
                取消
              </Button>
              <Button
                onClick={runConfirmedAction}
                className={
                  confirmDialog.tone === "danger"
                    ? "rounded-xl bg-rose-600 text-white hover:bg-rose-700"
                    : "rounded-xl bg-blue-600 text-white hover:bg-blue-700"
                }
              >
                {confirmDialog.confirmLabel}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
      {uploadModalOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
          onClick={() => !uploading && setUploadModalOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-semibold text-slate-900">上传文档</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  选择目标知识库后上传，系统会自动提取文本并加入索引队列。
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => !uploading && setUploadModalOpen(false)}
                className="rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-5 space-y-4">
              <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm sm:grid-cols-2">
                <div>
                  <p className="text-xs text-slate-500">目标团队</p>
                  <p className="mt-1 truncate font-medium text-slate-800">
                    {activeTeam?.name || "未选择团队"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">目标知识库</p>
                  <p className="mt-1 truncate font-medium text-slate-800">
                    {uploadTargetKnowledgeBase?.name || "未选择知识库"}
                  </p>
                </div>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">目标知识库</label>
                <select
                  value={uploadCollectionId ?? ""}
                  onChange={(event) =>
                    setUploadCollectionId(event.target.value ? Number(event.target.value) : null)
                  }
                  className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-200"
                >
                  {knowledgeBases.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </div>

              <div
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                className={cn(
                  "rounded-2xl border-2 border-dashed p-10 text-center transition-all",
                  dragOver
                    ? "border-blue-300 bg-blue-50/70"
                    : "border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-slate-100",
                  uploading && "pointer-events-none opacity-70",
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPT_FILES}
                  multiple
                  onChange={onFileSelect}
                  className="hidden"
                />
                <input
                  ref={folderInputRef}
                  type="file"
                  multiple
                  onChange={onFileSelect}
                  className="hidden"
                  {...({ webkitdirectory: "true", directory: "true" } as Record<string, string>)}
                />
                {uploading ? (
                  <div className="inline-flex items-center gap-2 text-slate-600">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    正在上传并加入索引队列...
                  </div>
                ) : (
                  <>
                    <UploadCloud className="mx-auto h-8 w-8 text-slate-500" />
                    <p className="mt-4 text-base font-medium text-slate-700">
                      拖拽文档到这里，或点击选择文件
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      支持 txt / md / pdf / docx，单文件最大 10MB，单次最多 {MAX_BATCH} 个文件
                    </p>
                    <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        className="rounded-xl border-slate-200"
                        onClick={(event) => {
                          event.stopPropagation();
                          fileInputRef.current?.click();
                        }}
                      >
                        选择文件
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        className="rounded-xl border-slate-200"
                        onClick={(event) => {
                          event.stopPropagation();
                          folderInputRef.current?.click();
                        }}
                      >
                        选择文件夹
                      </Button>
                    </div>
                  </>
                  )}
                </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
