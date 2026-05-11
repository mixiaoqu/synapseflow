"use client";

import { ChangeEvent, DragEvent, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, LibraryBig, Loader2, RefreshCcw, Search, UploadCloud, X } from "lucide-react";
import { Toaster, toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  deleteDocument,
  indexDocument,
  listDocuments,
  uploadDocument,
  uploadDocumentsBatch,
  type DocumentListItem,
} from "@/lib/api/documents";
import { listDocumentCategories, type DocumentCategory } from "@/lib/api/documentCategories";
import {
  listKnowledgeBaseBranches,
  listKnowledgeBases,
  type KnowledgeBaseBranch,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import { listTeams, type Team } from "@/lib/api/teams";
import { cn } from "@/lib/utils";

import { KnowledgeBaseBranchSidebar } from "../../components/KnowledgeBaseBranchSidebar";
import { KnowledgeBaseDocumentTable } from "../../components/KnowledgeBaseDocumentTable";

const ACCEPT_FILES = ".txt,.md,.pdf,.docx";
const SUPPORTED_EXTENSIONS = [".txt", ".md", ".pdf", ".docx"];
const MAX_SIZE = 10 * 1024 * 1024;
const MAX_BATCH = 500;
const BRANCH_CATEGORY_BASELINE_PAGE_SIZE = 500;

type ConfirmDialogState = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  tone: "primary" | "danger";
  onConfirm: null | (() => void | Promise<void>);
};

function getSourcePaths(files: File[]) {
  const paths = files.map((file) => file.webkitRelativePath || null);
  return paths.some(Boolean) ? paths : undefined;
}

function buildDocumentsListUrl(teamId: number | null) {
  const query = new URLSearchParams();
  if (teamId != null) query.set("teamId", String(teamId));
  return `/admin/documents${query.toString() ? `?${query.toString()}` : ""}`;
}

export default function KnowledgeBaseDetailPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-500">
          <Loader2 className="h-6 w-6 animate-spin" />
        </main>
      }
    >
      <KnowledgeBaseDetailPageContent />
    </Suspense>
  );
}

function KnowledgeBaseDetailPageContent() {
  const params = useParams<{ knowledgeBaseId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();

  const kbId = Number(params.knowledgeBaseId);
  const teamIdQuery = Number(searchParams.get("teamId"));
  const branchIdQuery = Number(searchParams.get("branchId"));
  const categoryIdQuery = Number(searchParams.get("categoryId"));
  const documentIdQuery = Number(searchParams.get("documentId"));

  const teamIdFromQuery = Number.isFinite(teamIdQuery) && teamIdQuery > 0 ? teamIdQuery : null;
  const branchIdFromQuery = Number.isFinite(branchIdQuery) && branchIdQuery > 0 ? branchIdQuery : null;
  const categoryIdFromQuery =
    Number.isFinite(categoryIdQuery) && categoryIdQuery > 0 ? categoryIdQuery : null;
  const documentIdFromQuery =
    Number.isFinite(documentIdQuery) && documentIdQuery > 0 ? documentIdQuery : null;

  const [teams, setTeams] = useState<Team[]>([]);
  const [teamId, setTeamId] = useState<number | null>(teamIdFromQuery);
  const [kb, setKb] = useState<KnowledgeBaseWithCount | null>(null);
  const [branches, setBranches] = useState<KnowledgeBaseBranch[]>([]);
  const [allCategories, setAllCategories] = useState<DocumentCategory[]>([]);
  const [branchCategoryIds, setBranchCategoryIds] = useState<number[]>([]);
  const [selectedBranchId, setSelectedBranchId] = useState<number | null>(branchIdFromQuery);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(categoryIdFromQuery);
  const [focusedDocumentId, setFocusedDocumentId] = useState<number | null>(documentIdFromQuery);
  const [docs, setDocs] = useState<DocumentListItem[]>([]);
  const [docsTotal, setDocsTotal] = useState(0);
  const [docPage, setDocPage] = useState(1);
  const [docPageSize, setDocPageSize] = useState(20);
  const [searchInput, setSearchInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [loadingMeta, setLoadingMeta] = useState(false);
  const [loadingStructure, setLoadingStructure] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadBranchId, setUploadBranchId] = useState<number | null>(branchIdFromQuery);
  const [uploadCategoryId, setUploadCategoryId] = useState<number | null>(categoryIdFromQuery);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [reindexingDocumentId, setReindexingDocumentId] = useState<number | null>(null);
  const [deletingDocumentId, setDeletingDocumentId] = useState<number | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState>({
    open: false,
    title: "",
    description: "",
    confirmLabel: "确认",
    tone: "primary",
    onConfirm: null,
  });

  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const docsRequestSeqRef = useRef(0);

  const activeTeam = teams.find((item) => item.id === teamId) ?? null;
  const activeBranch = branches.find((item) => item.id === selectedBranchId) ?? null;
  const uploadBranch = branches.find((item) => item.id === uploadBranchId) ?? null;
  const uploadCategory = allCategories.find((item) => item.id === uploadCategoryId) ?? null;

  const branchCategories = useMemo(() => {
    const branchCategoryIdSet = new Set(branchCategoryIds);
    return allCategories.filter((item) => branchCategoryIdSet.has(item.id));
  }, [allCategories, branchCategoryIds]);

  const activeCategory = branchCategories.find((item) => item.id === selectedCategoryId) ?? null;
  const pageTitle = activeCategory?.name || "全部文档";

  const openConfirmDialog = (options: Omit<ConfirmDialogState, "open">) => {
    setConfirmDialog({
      open: true,
      ...options,
    });
  };

  const closeConfirmDialog = () => {
    setConfirmDialog((prev) => ({
      ...prev,
      open: false,
      onConfirm: null,
    }));
  };

  const runConfirmedAction = () => {
    const action = confirmDialog.onConfirm;
    closeConfirmDialog();
    if (!action) return;
    void Promise.resolve(action());
  };

  const reload = () => setReloadToken((prev) => prev + 1);

  useEffect(() => {
    if (documentIdFromQuery != null) {
      setFocusedDocumentId(documentIdFromQuery);
    }
  }, [documentIdFromQuery]);

  useEffect(() => {
    if (!Number.isFinite(kbId) || kbId <= 0) {
      toast.error("知识库 ID 无效");
      router.push("/admin/documents");
    }
  }, [kbId, router]);

  useEffect(() => {
    if (!Number.isFinite(kbId) || kbId <= 0) return;

    let cancelled = false;

    const run = async () => {
      setLoadingMeta(true);

      try {
        const teamList = await listTeams();
        if (cancelled) return;

        setTeams(teamList);

        let found: KnowledgeBaseWithCount | null = null;
        let foundTeamId: number | null = null;

        if (teamIdFromQuery != null) {
          const list = await listKnowledgeBases(teamIdFromQuery);
          found = list.find((item) => item.id === kbId) ?? null;
          if (found) foundTeamId = teamIdFromQuery;
        }

        if (!found) {
          for (const team of teamList) {
            const list = await listKnowledgeBases(team.id);
            const matched = list.find((item) => item.id === kbId);
            if (matched) {
              found = matched;
              foundTeamId = team.id;
              break;
            }
          }
        }

        if (cancelled) return;

        if (!found) {
          toast.error("未找到对应知识库");
          router.push("/admin/documents");
          return;
        }

        setKb(found);
        setTeamId(foundTeamId);
      } catch (error) {
        if (!cancelled) {
          toast.error(error instanceof Error ? error.message : "加载知识库失败");
        }
      } finally {
        if (!cancelled) setLoadingMeta(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [kbId, reloadToken, router, teamIdFromQuery]);

  useEffect(() => {
    if (!Number.isFinite(kbId) || kbId <= 0) {
      setBranches([]);
      setAllCategories([]);
      setBranchCategoryIds([]);
      setSelectedBranchId(null);
      setSelectedCategoryId(null);
      setUploadBranchId(null);
      setUploadCategoryId(null);
      return;
    }

    let cancelled = false;

    const run = async () => {
      setLoadingStructure(true);

      try {
        const [categoryItems, branchItems] = await Promise.all([
          listDocumentCategories(kbId),
          listKnowledgeBaseBranches(kbId),
        ]);
        if (cancelled) return;

        const fallbackBranchId =
          (branchIdFromQuery != null && branchItems.some((item) => item.id === branchIdFromQuery)
            ? branchIdFromQuery
            : null) ??
          branchItems.find((item) => item.is_active)?.id ??
          branchItems[0]?.id ??
          null;

        const fallbackCategoryId =
          categoryIdFromQuery != null && categoryItems.some((item) => item.id === categoryIdFromQuery)
            ? categoryIdFromQuery
            : null;

        setBranches(branchItems);
        setAllCategories(categoryItems);
        setSelectedBranchId((prev) =>
          prev != null && branchItems.some((item) => item.id === prev) ? prev : fallbackBranchId,
        );
        setSelectedCategoryId((prev) =>
          prev != null && categoryItems.some((item) => item.id === prev) ? prev : fallbackCategoryId,
        );
        setUploadBranchId((prev) =>
          prev != null && branchItems.some((item) => item.id === prev) ? prev : fallbackBranchId,
        );
        setUploadCategoryId((prev) =>
          prev != null && categoryItems.some((item) => item.id === prev) ? prev : fallbackCategoryId,
        );
      } catch (error) {
        if (!cancelled) {
          setBranches([]);
          setAllCategories([]);
          setBranchCategoryIds([]);
          setSelectedBranchId(null);
          setSelectedCategoryId(null);
          setUploadBranchId(null);
          setUploadCategoryId(null);
          toast.error(error instanceof Error ? error.message : "加载版本与分类失败");
        }
      } finally {
        if (!cancelled) setLoadingStructure(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [branchIdFromQuery, categoryIdFromQuery, kbId, reloadToken]);

  const loadDocumentsList = useCallback(async () => {
    if (!Number.isFinite(kbId) || kbId <= 0 || loadingStructure) return;

    if (branches.length > 0 && selectedBranchId == null) {
      setDocs([]);
      setDocsTotal(0);
      return;
    }

    const requestSeq = ++docsRequestSeqRef.current;
    setLoadingDocs(true);

    try {
      const result = await listDocuments({
        page: docPage,
        page_size: docPageSize,
        keyword: keyword || undefined,
        knowledge_base_id: kbId,
        knowledge_base_branch_id: selectedBranchId ?? undefined,
        category_id: selectedCategoryId ?? undefined,
        team_id: teamId ?? undefined,
      });

      if (requestSeq !== docsRequestSeqRef.current) return;

      if (result.total > 0 && result.items.length === 0 && docPage > 1) {
        setDocPage((prev) => Math.max(1, prev - 1));
        return;
      }

      setDocs(result.items);
      setDocsTotal(result.total);
    } catch (error) {
      if (requestSeq !== docsRequestSeqRef.current) return;
      toast.error(error instanceof Error ? error.message : "加载文档列表失败");
      setDocs([]);
      setDocsTotal(0);
    } finally {
      if (requestSeq === docsRequestSeqRef.current) {
        setLoadingDocs(false);
      }
    }
  }, [
    branches.length,
    docPage,
    docPageSize,
    kbId,
    keyword,
    loadingStructure,
    selectedBranchId,
    selectedCategoryId,
    teamId,
  ]);

  useEffect(() => {
    void loadDocumentsList();
  }, [loadDocumentsList, reloadToken]);

  useEffect(() => {
    if (!Number.isFinite(kbId) || kbId <= 0 || selectedBranchId == null) {
      setBranchCategoryIds([]);
      return;
    }

    let cancelled = false;

    const run = async () => {
      try {
        const result = await listDocuments({
          page: 1,
          page_size: BRANCH_CATEGORY_BASELINE_PAGE_SIZE,
          knowledge_base_id: kbId,
          knowledge_base_branch_id: selectedBranchId,
          team_id: teamId ?? undefined,
        });

        if (cancelled) return;

        const nextCategoryIds = Array.from(
          new Set(
            result.items
              .map((item) => item.category_id)
              .filter((item): item is number => item != null),
          ),
        );

        setBranchCategoryIds(nextCategoryIds);
      } catch (error) {
        if (cancelled) return;
        setBranchCategoryIds([]);
        toast.error(error instanceof Error ? error.message : "加载当前版本分类失败");
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [kbId, reloadToken, selectedBranchId, teamId]);

  useEffect(() => {
    if (selectedCategoryId == null) return;
    if (branchCategories.some((item) => item.id === selectedCategoryId)) return;
    setSelectedCategoryId(null);
  }, [branchCategories, selectedCategoryId]);

  const handleBack = () => {
    router.push(buildDocumentsListUrl(teamId));
  };

  const handleBranchSelect = (branchId: number) => {
    setSelectedBranchId(branchId);
    setSelectedCategoryId(null);
    setFocusedDocumentId(null);
    setDocPage(1);
  };

  const handleCategorySelect = (categoryId: number | null) => {
    setSelectedCategoryId(categoryId);
    setFocusedDocumentId(null);
    setDocPage(1);
  };

  const handleSearchSubmit = () => {
    setDocPage(1);
    setKeyword(searchInput.trim());
  };

  const handleOpenDetail = (document: DocumentListItem) => {
    setFocusedDocumentId(document.id);
    const query = new URLSearchParams();
    if (teamId != null) query.set("teamId", String(teamId));
    if (selectedBranchId != null) query.set("branchId", String(selectedBranchId));
    if (selectedCategoryId != null) query.set("categoryId", String(selectedCategoryId));
    query.set("documentId", String(document.id));
    router.push(`/admin/documents/${kbId}/documents/${document.id}?${query.toString()}`);
  };

  const handleReindex = async (document: DocumentListItem) => {
    setReindexingDocumentId(document.id);
    try {
      const result = await indexDocument(document.id);
      toast.success(result.message || "已提交重新索引任务");
      reload();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "重新索引失败");
    } finally {
      setReindexingDocumentId(null);
    }
  };

  const handleDelete = (document: DocumentListItem) => {
    openConfirmDialog({
      title: "删除文档",
      description: `确认删除《${document.title}》吗？删除后不可恢复。`,
      confirmLabel: "确认删除",
      tone: "danger",
      onConfirm: async () => {
        setDeletingDocumentId(document.id);
        try {
          await deleteDocument(document.id);
          toast.success("文档已删除");
          reload();
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "删除失败");
        } finally {
          setDeletingDocumentId(null);
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
    if (!uploadBranchId) {
      toast.error("请先选择上传版本");
      return;
    }

    const validFiles = Array.from(files).filter((file) => {
      const ext = "." + (file.name.split(".").pop()?.toLowerCase() || "");
      return SUPPORTED_EXTENSIONS.includes(ext) && file.size <= MAX_SIZE;
    });

    if (validFiles.length === 0) {
      toast.error("没有可上传的有效文件");
      return;
    }

    setUploading(true);

    try {
      const sourcePaths = getSourcePaths(validFiles);

      if (validFiles.length === 1) {
        await uploadDocument(validFiles[0], kbId, uploadBranchId, {
          categoryId: uploadCategoryId ?? undefined,
          sourcePath: sourcePaths?.[0] ?? null,
        });
      } else {
        await uploadDocumentsBatch(validFiles, kbId, uploadBranchId, {
          categoryId: uploadCategoryId ?? undefined,
          sourcePaths,
        });
      }

      toast.success(`已上传 ${validFiles.length} 份文档`);
      setUploadModalOpen(false);
      setDocPage(1);
      reload();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    void uploadFiles(event.dataTransfer.files);
  };

  const onFileSelect = (event: ChangeEvent<HTMLInputElement>) => {
    void uploadFiles(event.target.files);
    event.target.value = "";
  };

  if (loadingMeta && !kb) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        正在加载知识库...
      </main>
    );
  }

  return (
    <div className="bg-slate-50">
      <Toaster position="top-right" />

      <main className="h-[calc(100vh-64px)] overflow-hidden">
        <div className="flex h-full min-h-0 flex-col">
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6">
            <div className="min-w-0">
              <Button
                variant="ghost"
                className="mb-1 h-8 rounded-full px-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                onClick={handleBack}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                返回知识库
              </Button>
              <div className="flex min-w-0 items-center gap-2">
                <LibraryBig className="h-4 w-4 text-slate-400" />
                <h1 className="truncate text-lg font-semibold text-slate-900">{kb?.name || "知识库"}</h1>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                className="rounded-full border-slate-200"
                onClick={() => reload()}
              >
                <RefreshCcw className="mr-2 h-4 w-4" />
                刷新
              </Button>
              <Button
                className="rounded-full bg-slate-900 text-white hover:bg-slate-800"
                onClick={() => setUploadModalOpen(true)}
              >
                <UploadCloud className="mr-2 h-4 w-4" />
                上传文档
              </Button>
            </div>
          </header>

          <section className="flex min-h-0 flex-1 overflow-hidden">
            <KnowledgeBaseBranchSidebar
              branches={branches}
              categories={branchCategories}
              selectedBranchId={selectedBranchId}
              selectedCategoryId={selectedCategoryId}
              onSelectBranch={handleBranchSelect}
              onSelectCategory={handleCategorySelect}
            />

            <section className="flex min-h-0 flex-1 flex-col overflow-hidden bg-white">
              <div className="flex shrink-0 flex-col gap-4 border-b border-slate-200 px-6 py-5 xl:flex-row xl:items-end xl:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                      版本：{activeBranch?.name || "未选择"}
                    </span>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                      分类：{activeCategory?.name || "全部文档"}
                    </span>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                      文档：{docsTotal}
                    </span>
                  </div>
                  <h2 className="mt-2 text-2xl font-semibold text-slate-900">{pageTitle}</h2>
                  <p className="mt-2 text-sm text-slate-500">
                    {activeTeam ? `当前团队 ${activeTeam.name}` : "文档工作台"}
                    {keyword ? ` · 搜索 ${keyword}` : ""}
                  </p>
                </div>

                <div className="flex w-full max-w-xl gap-2">
                  <Input
                    value={searchInput}
                    onChange={(event) => setSearchInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        handleSearchSubmit();
                      }
                    }}
                    placeholder="搜索文档标题或关键词"
                    className="h-11 rounded-full border-slate-200 px-4"
                  />
                  <Button
                    variant="outline"
                    className="h-11 rounded-full border-slate-200 px-4"
                    onClick={handleSearchSubmit}
                  >
                    <Search className="mr-2 h-4 w-4" />
                    搜索
                  </Button>
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-hidden px-6 py-6">
                <KnowledgeBaseDocumentTable
                  documents={docs}
                  loading={loadingDocs}
                  total={docsTotal}
                  page={docPage}
                  pageSize={docPageSize}
                  focusedDocumentId={focusedDocumentId}
                  showCategoryColumn={selectedCategoryId == null}
                  reindexingDocumentId={reindexingDocumentId}
                  deletingDocumentId={deletingDocumentId}
                  onPageChange={setDocPage}
                  onPageSizeChange={(value) => {
                    setDocPageSize(value);
                    setDocPage(1);
                  }}
                  onOpenDetail={handleOpenDetail}
                  onReindex={handleReindex}
                  onDelete={handleDelete}
                />
              </div>
            </section>
          </section>
        </div>
      </main>

      {confirmDialog.open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm"
          onClick={closeConfirmDialog}
        >
          <div
            className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-lg font-semibold text-slate-900">{confirmDialog.title}</p>
                <p className="mt-2 text-sm leading-6 text-slate-500">{confirmDialog.description}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={closeConfirmDialog}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" className="border-slate-200" onClick={closeConfirmDialog}>
                取消
              </Button>
              <Button
                className={
                  confirmDialog.tone === "danger"
                    ? "bg-red-600 text-white hover:bg-red-700"
                    : "bg-blue-600 text-white hover:bg-blue-700"
                }
                onClick={runConfirmedAction}
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
            className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-lg font-semibold text-slate-900">上传文档</p>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  上传时选择目标版本与分类，上传完成后可进入文档详情查看正文、状态和后续操作。
                </p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => !uploading && setUploadModalOpen(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-5 grid gap-4">
              <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm sm:grid-cols-2">
                <div>
                  <p className="text-xs text-slate-500">当前团队</p>
                  <p className="mt-1 font-medium text-slate-800">{activeTeam?.name || "未识别团队"}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">当前知识库</p>
                  <p className="mt-1 font-medium text-slate-800">{kb?.name || "未识别知识库"}</p>
                </div>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">上传版本</label>
                <select
                  value={uploadBranchId ?? ""}
                  onChange={(event) => setUploadBranchId(event.target.value ? Number(event.target.value) : null)}
                  className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-200"
                >
                  <option value="">请选择版本</option>
                  {branches.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name} / {branch.code}
                    </option>
                  ))}
                </select>
                <p className="mt-2 text-xs text-slate-500">
                  当前选择：{uploadBranch?.name || "未选择版本"}
                </p>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">上传分类</label>
                <select
                  value={uploadCategoryId ?? ""}
                  onChange={(event) => setUploadCategoryId(event.target.value ? Number(event.target.value) : null)}
                  className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-200"
                >
                  <option value="">不指定分类</option>
                  {allCategories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}（{category.document_count}）
                    </option>
                  ))}
                </select>
                <p className="mt-2 text-xs text-slate-500">
                  当前选择：{uploadCategory?.name || "不指定分类"}
                </p>
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
                "mt-5 rounded-3xl border-2 border-dashed p-10 text-center transition-all",
                dragOver ? "border-blue-300 bg-blue-50/70" : "border-slate-300 bg-slate-50 hover:border-slate-400",
                uploading && "pointer-events-none opacity-70",
              )}
            >
              <input
                id="kb-upload-input"
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
                  正在上传...
                </div>
              ) : (
                <>
                  <UploadCloud className="mx-auto h-8 w-8 text-slate-500" />
                  <p className="mt-3 text-sm text-slate-700">拖拽文件到这里，或手动选择文件 / 文件夹上传</p>
                  <p className="mt-1 text-xs text-slate-500">
                    支持 txt / md / pdf / docx，单文件不超过 10MB，单次最多 {MAX_BATCH} 个文件
                  </p>
                  <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      className="rounded-xl border-slate-200"
                      onClick={(event) => {
                        event.stopPropagation();
                        document.getElementById("kb-upload-input")?.click();
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
      ) : null}
    </div>
  );
}
