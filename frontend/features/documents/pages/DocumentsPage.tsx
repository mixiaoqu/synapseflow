"use client";

import { ChangeEvent, DragEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Database, Loader2, PencilLine, Plus, Search, UploadCloud, X } from "lucide-react";
import { Toaster, toast } from "sonner";

import { AdminPage } from "@/components/admin/layout/AdminPage";
import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { KnowledgeBaseStatusSummary } from "@/features/documents/components/KnowledgeBaseStatusSummary";
import { KnowledgeBaseWorkbenchCard } from "@/features/documents/components/KnowledgeBaseWorkbenchCard";
import { uploadDocument, uploadDocumentsBatch } from "@/lib/api/documents";
import {
  createKnowledgeBase,
  createKnowledgeBaseBranch,
  deleteKnowledgeBase,
  listKnowledgeBaseBranches,
  listKnowledgeBases,
  updateKnowledgeBase,
  type KnowledgeBaseBranch,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import { cn } from "@/lib/utils";

const ACCEPT_FILES = ".txt,.md,.pdf,.docx";
const SUPPORTED_EXTENSIONS = new Set([".txt", ".md", ".pdf", ".docx"]);
const MAX_SIZE = 10 * 1024 * 1024;
const MAX_BATCH = 500;

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
  const [branchOptions, setBranchOptions] = useState<Record<number, KnowledgeBaseBranch[]>>({});
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

  const [createBranchModalOpen, setCreateBranchModalOpen] = useState(false);
  const [createBranchKnowledgeBaseId, setCreateBranchKnowledgeBaseId] = useState<number | null>(null);
  const [createBranchCode, setCreateBranchCode] = useState("");
  const [createBranchName, setCreateBranchName] = useState("");
  const [createBranchDescription, setCreateBranchDescription] = useState("");
  const [creatingBranch, setCreatingBranch] = useState(false);

  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadCollectionId, setUploadCollectionId] = useState<number | null>(null);
  const [uploadBranchId, setUploadBranchId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const [deletingKnowledgeBaseId, setDeletingKnowledgeBaseId] = useState<number | null>(null);
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
  const uploadTargetBranches = useMemo(
    () => (uploadCollectionId ? branchOptions[uploadCollectionId] ?? [] : []),
    [branchOptions, uploadCollectionId],
  );
  const uploadTargetBranch = useMemo(
    () => uploadTargetBranches.find((item) => item.id === uploadBranchId) ?? null,
    [uploadBranchId, uploadTargetBranches],
  );
  const uploadActiveBranches = useMemo(
    () => uploadTargetBranches.filter((item) => item.is_active),
    [uploadTargetBranches],
  );

  const loadKnowledgeBases = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
    if (selectedTeamId == null) {
      setKnowledgeBases([]);
      setBranchOptions({});
      setSelectedKnowledgeBaseId(null);
      setUploadCollectionId(null);
      setUploadBranchId(null);
      return;
    }

    if (!silent) setLoadingKnowledgeBases(true);
    try {
      const list = await listKnowledgeBases(selectedTeamId);
      const branchEntries = await Promise.all(
        list.map(async (item) => [item.id, await listKnowledgeBaseBranches(item.id)] as const),
      );
      setKnowledgeBases(list);
      setBranchOptions(Object.fromEntries(branchEntries));
      setSelectedKnowledgeBaseId((prev) =>
        prev && list.some((item) => item.id === prev) ? prev : list[0]?.id ?? null,
      );
      setUploadCollectionId((prev) =>
        prev && list.some((item) => item.id === prev) ? prev : list[0]?.id ?? null,
      );
    } catch {
      if (!silent) {
        toast.error("知识库列表加载失败");
        setKnowledgeBases([]);
        setBranchOptions({});
        setSelectedKnowledgeBaseId(null);
        setUploadCollectionId(null);
        setUploadBranchId(null);
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

  useEffect(() => {
    if (!uploadCollectionId) {
      setUploadBranchId(null);
      return;
    }
    const branches = branchOptions[uploadCollectionId] ?? [];
    setUploadBranchId((prev) =>
      prev && branches.some((item) => item.id === prev)
        ? prev
        : (branches.find((item) => item.is_active)?.id ?? null),
    );
  }, [branchOptions, uploadCollectionId]);

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
    if (selectedTeamId == null) {
      toast.error("请先选择团队");
      return;
    }
    setCreateName("");
    setCreateDescription("");
    setCreateModalOpen(true);
  };

  const openCreateBranchModal = (knowledgeBaseId?: number) => {
    const targetId = knowledgeBaseId ?? selectedKnowledgeBaseId ?? knowledgeBases[0]?.id ?? null;
    if (!targetId) {
      toast.error("请先选择知识库");
      return;
    }
    setCreateBranchKnowledgeBaseId(targetId);
    setCreateBranchCode("");
    setCreateBranchName("");
    setCreateBranchDescription("");
    setCreateBranchModalOpen(true);
  };

  const openEditModal = (knowledgeBase: KnowledgeBaseWithCount) => {
    setEditingKnowledgeBaseId(knowledgeBase.id);
    setEditName(knowledgeBase.name);
    setEditDescription(knowledgeBase.description || "");
    setEditModalOpen(true);
  };

  const openUploadModal = (knowledgeBaseId?: number) => {
    const targetId = knowledgeBaseId ?? selectedKnowledgeBaseId ?? knowledgeBases[0]?.id ?? null;
    if (!targetId) {
      toast.error("请先选择知识库");
      return;
    }
    setUploadCollectionId(targetId);
    const branches = branchOptions[targetId] ?? [];
    const firstActiveBranch = branches.find((item) => item.is_active) ?? null;
    setUploadBranchId(firstActiveBranch?.id ?? null);
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
      toast.error((error as { message?: string }).message || "更新知识库失败");
    } finally {
      setSavingKnowledgeBase(false);
    }
  };

  const handleCreateBranch = async () => {
    if (!createBranchKnowledgeBaseId || !createBranchCode.trim() || !createBranchName.trim()) {
      return;
    }
    setCreatingBranch(true);
    try {
      await createKnowledgeBaseBranch(createBranchKnowledgeBaseId, {
        code: createBranchCode.trim(),
        name: createBranchName.trim(),
        description: createBranchDescription.trim() || null,
        is_active: true,
      });
      toast.success("版本已创建");
      setCreateBranchModalOpen(false);
      await loadKnowledgeBases();
      setUploadCollectionId(createBranchKnowledgeBaseId);
    } catch (error: unknown) {
      toast.error((error as { message?: string }).message || "创建版本失败");
    } finally {
      setCreatingBranch(false);
    }
  };

  const handleDeleteKnowledgeBase = (knowledgeBase: KnowledgeBaseWithCount) => {
    openConfirmDialog({
      title: "删除知识库",
      description: `删除后将移除“${knowledgeBase.name}”及其关联文档记录，请确认。`,
      contextRows: [
        { label: "团队", value: activeTeam?.name || "未选择团队" },
        { label: "知识库", value: knowledgeBase.name },
        { label: "文档总数", value: `${knowledgeBase.document_count}` },
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
          toast.error((error as { message?: string }).message || "删除知识库失败");
        } finally {
          setDeletingKnowledgeBaseId(null);
        }
      },
    });
  };

  const uploadFiles = async (files: File[] | FileList | null) => {
    if (!files || files.length === 0) return;
    if (files.length > MAX_BATCH) {
      toast.error(`单次最多上传 ${MAX_BATCH} 个文件`);
      return;
    }

    const { accepted, invalidTypeCount, oversizeCount } = validateFiles(files);
    if (accepted.length === 0) {
      toast.error("没有可上传的文件，请检查格式与大小限制");
      return;
    }

    if (!uploadBranchId) {
      toast.error("请先选择版本");
      return;
    }

    setUploading(true);
    try {
      const knowledgeBaseId =
        uploadCollectionId && uploadCollectionId > 0 ? uploadCollectionId : undefined;
      const sourcePaths = getSourcePaths(accepted);

      if (accepted.length === 1) {
        await uploadDocument(accepted[0], knowledgeBaseId, uploadBranchId, {
          sourcePath: sourcePaths?.[0] ?? null,
        });
      } else {
        await uploadDocumentsBatch(accepted, knowledgeBaseId, uploadBranchId, {
          sourcePaths,
        });
      }

      const notes: string[] = [];
      if (invalidTypeCount > 0) notes.push(`${invalidTypeCount} 个文件格式不支持`);
      if (oversizeCount > 0) notes.push(`${oversizeCount} 个文件超过 10MB`);
      toast.success(
        notes.length
          ? `已上传 ${accepted.length} 个文件，已跳过：${notes.join("，")}`
          : `已上传 ${accepted.length} 个文件`,
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
  const headerDescription = activeTeam
    ? "管理您的企业知识库与文档资产，按工作台方式进入版本与内容管理。"
    : "选择团队后查看当前范围内的知识库工作台。";

  return (
    <div className="min-h-full bg-slate-50 text-slate-900">
      <Toaster position="top-right" richColors />

      <AdminPage className="px-6 py-8 sm:px-6 lg:px-8">
        <section className="mx-auto max-w-7xl">
          <div className="mb-8 flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                Knowledge Assets
              </p>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">
                知识库工作台
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-500">{headerDescription}</p>
            </div>

            <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-end lg:w-auto">
              <div className="relative w-full sm:w-[320px]">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  onKeyDown={(event) => event.key === "Enter" && setKeyword(searchInput.trim())}
                  placeholder="搜索知识库名称或描述"
                  className="h-12 rounded-full border-slate-200 bg-white pl-11 pr-4"
                />
              </div>
              <Button
                variant="outline"
                onClick={() => setKeyword(searchInput.trim())}
                className="h-12 rounded-full border-slate-200 bg-white px-5"
              >
                搜索
              </Button>
              <Button
                onClick={openCreateModal}
                className="h-12 rounded-full bg-slate-900 px-5 text-white hover:bg-slate-800"
              >
                <Plus className="mr-2 h-4 w-4" />
                新建知识库
              </Button>
            </div>
          </div>

          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-500 shadow-sm">
            <div className="flex flex-wrap items-center gap-3">
              <span>{isLoading ? "正在同步团队与知识库数据..." : `共找到 ${displayedKnowledgeBases.length} 个知识库`}</span>
              <span className="hidden text-slate-300 sm:inline">/</span>
              <span>{activeTeam?.name || "未选择团队"}</span>
            </div>
            {keyword ? (
              <Button
                variant="ghost"
                onClick={() => {
                  setSearchInput("");
                  setKeyword("");
                }}
                className="rounded-full px-0 text-slate-500 hover:bg-transparent hover:text-slate-900"
              >
                清空筛选
              </Button>
            ) : null}
          </div>

        {displayedKnowledgeBases.length === 0 ? (
          <section className="rounded-3xl border border-slate-200 bg-white px-6 py-14 text-center shadow-sm">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
              <Database className="h-8 w-8" />
            </div>
            <h2 className="mt-5 text-2xl font-semibold text-slate-900">
              {keyword ? "没有匹配的知识库" : "当前还没有知识库"}
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-500">
              {keyword
                ? "请调整搜索关键词，或清空筛选后查看全部知识库。"
                : "先创建知识库，再上传文档和维护版本，后续详情页管理链路保持不变。"}
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <Button onClick={openCreateModal} className="rounded-full bg-slate-900 px-5 text-white hover:bg-slate-800">
                <Plus className="mr-2 h-4 w-4" />
                新建知识库
              </Button>
              {keyword ? (
                <Button
                  variant="outline"
                  className="rounded-full border-slate-200"
                  onClick={() => {
                    setSearchInput("");
                    setKeyword("");
                  }}
                >
                  清空筛选
                </Button>
              ) : null}
            </div>
          </section>
        ) : (
          <section className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {displayedKnowledgeBases.map((knowledgeBase) => (
              <KnowledgeBaseWorkbenchCard
                key={knowledgeBase.id}
                knowledgeBase={knowledgeBase}
                branches={branchOptions[knowledgeBase.id] ?? []}
                active={selectedKnowledgeBaseId === knowledgeBase.id}
                deleting={deletingKnowledgeBaseId === knowledgeBase.id}
                onOpen={(item) => {
                  setSelectedKnowledgeBaseId(item.id);
                  openKnowledgeBase(item.id);
                }}
                onUpload={(item) => {
                  setSelectedKnowledgeBaseId(item.id);
                  openUploadModal(item.id);
                }}
                onEdit={openEditModal}
                onCreateBranch={(item) => {
                  setSelectedKnowledgeBaseId(item.id);
                  openCreateBranchModal(item.id);
                }}
                onDelete={handleDeleteKnowledgeBase}
              />
            ))}
          </section>
        )}
        </section>
      </AdminPage>

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
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  创建后即可进入详情页继续上传文档、管理版本和处理内容状态。
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
                  placeholder="例如：售后 FAQ、产品手册、运营规范"
                  className="h-11 rounded-xl border-slate-200"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">知识库描述</label>
                <Textarea
                  value={createDescription}
                  onChange={(event) => setCreateDescription(event.target.value)}
                  placeholder="描述知识库的用途、适用范围或文档来源。"
                  className="min-h-[120px] rounded-xl border-slate-200"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => !creatingKnowledgeBase && setCreateModalOpen(false)}
                  className="rounded-xl border-slate-200"
                >
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
                  更新名称和描述，不影响现有文档、版本和详情页管理链路。
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
                  placeholder="例如：售后 FAQ、产品手册、运营规范"
                  className="h-11 rounded-xl border-slate-200"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">知识库描述</label>
                <Textarea
                  value={editDescription}
                  onChange={(event) => setEditDescription(event.target.value)}
                  placeholder="描述知识库的用途、适用范围或文档来源。"
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

      {createBranchModalOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
          onClick={() => !creatingBranch && setCreateBranchModalOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-semibold text-slate-900">新建版本</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  版本用于区分不同内容范围，上传文档时会绑定到所选版本。
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => !creatingBranch && setCreateBranchModalOpen(false)}
                className="rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-5 space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">知识库</label>
                <select
                  value={createBranchKnowledgeBaseId ?? ""}
                  onChange={(event) =>
                    setCreateBranchKnowledgeBaseId(event.target.value ? Number(event.target.value) : null)
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
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">版本标识</label>
                <Input
                  value={createBranchCode}
                  onChange={(event) => setCreateBranchCode(event.target.value)}
                  placeholder="例如：v2.9.3 / customer-a"
                  className="h-11 rounded-xl border-slate-200"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">版本名称</label>
                <Input
                  value={createBranchName}
                  onChange={(event) => setCreateBranchName(event.target.value)}
                  placeholder="例如：五月发布版本"
                  className="h-11 rounded-xl border-slate-200"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">版本描述</label>
                <Textarea
                  value={createBranchDescription}
                  onChange={(event) => setCreateBranchDescription(event.target.value)}
                  placeholder="补充这个版本的用途、范围或所属客户。"
                  className="min-h-[100px] rounded-xl border-slate-200"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => !creatingBranch && setCreateBranchModalOpen(false)}
                  className="rounded-xl border-slate-200"
                >
                  取消
                </Button>
                <Button
                  onClick={() => void handleCreateBranch()}
                  disabled={creatingBranch || !createBranchKnowledgeBaseId || !createBranchCode.trim() || !createBranchName.trim()}
                  className="rounded-xl bg-blue-600 text-white hover:bg-blue-700"
                >
                  {creatingBranch ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Plus className="mr-2 h-4 w-4" />
                  )}
                  创建版本
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
                <p className="mt-2 text-sm leading-6 text-slate-500">{confirmDialog.description}</p>
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
                  选择知识库和版本后，可拖拽上传或选择单文件、文件夹批量导入。
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
                  <p className="text-xs text-slate-500">团队</p>
                  <p className="mt-1 truncate font-medium text-slate-800">
                    {activeTeam?.name || "未选择团队"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">知识库</p>
                  <p className="mt-1 truncate font-medium text-slate-800">
                    {uploadTargetKnowledgeBase?.name || "未选择知识库"}
                  </p>
                </div>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">知识库</label>
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

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">版本</label>
                <select
                  value={uploadBranchId ?? ""}
                  onChange={(event) =>
                    setUploadBranchId(event.target.value ? Number(event.target.value) : null)
                  }
                  disabled={uploadActiveBranches.length === 0}
                  className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-200"
                >
                  <option value="">请选择版本</option>
                  {uploadActiveBranches.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} / {item.code}
                    </option>
                  ))}
                </select>
                <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-500">
                  <span>
                    {uploadActiveBranches.length === 0
                      ? "当前知识库没有可用版本，请先创建版本。"
                      : uploadTargetBranch
                        ? `当前上传到：${uploadTargetBranch.name}`
                        : "请选择一个版本"}
                  </span>
                  <button
                    type="button"
                    onClick={() => openCreateBranchModal(uploadCollectionId ?? undefined)}
                    className="font-medium text-blue-600 hover:text-blue-700"
                  >
                    新建版本
                  </button>
                </div>
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
                  (uploading || uploadActiveBranches.length === 0) && "pointer-events-none opacity-70",
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
                    正在上传并创建索引任务...
                  </div>
                ) : uploadActiveBranches.length === 0 ? (
                  <>
                    <AlertTriangle className="mx-auto h-8 w-8 text-amber-500" />
                    <p className="mt-4 text-base font-medium text-slate-700">
                      当前没有可用版本，暂时无法上传文档
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      先创建版本，再为对应版本上传文件。
                    </p>
                    <div className="mt-5">
                      <Button
                        type="button"
                        className="rounded-xl bg-blue-600 text-white hover:bg-blue-700"
                        onClick={(event) => {
                          event.stopPropagation();
                          openCreateBranchModal(uploadCollectionId ?? undefined);
                        }}
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        新建版本
                      </Button>
                    </div>
                  </>
                ) : (
                  <>
                    <UploadCloud className="mx-auto h-8 w-8 text-slate-500" />
                    <p className="mt-4 text-base font-medium text-slate-700">
                      拖拽文件到这里，或选择文件、文件夹上传
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      支持 txt / md / pdf / docx，单文件不超过 10MB，单次最多 {MAX_BATCH} 个文件。
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

              {uploadTargetKnowledgeBase ? (
                <KnowledgeBaseStatusSummary knowledgeBase={uploadTargetKnowledgeBase} />
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
