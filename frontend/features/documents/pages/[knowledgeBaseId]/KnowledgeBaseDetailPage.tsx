"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChangeEvent, DragEvent, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Eye,
  FileClock,
  ListFilter,
  Loader2,
  MoreHorizontal,
  PencilLine,
  RefreshCcw,
  Save,
  Search,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { Toaster, toast } from "sonner";

import { AnswerMarkdown } from "@/components/ask/AnswerMarkdown";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  createDocumentVersion,
  deleteDocument,
  getDocument,
  getDocumentVersions,
  indexDocument,
  listDocuments,
  reindexAll,
  replaceDocumentContent,
  switchCurrentDocumentVersion,
  uploadDocument,
  uploadDocumentsBatch,
  type DocumentDetail,
  type DocumentIndexStatus,
  type DocumentListItem,
  type DocumentVersionItem,
} from "@/lib/api/documents";
import {
  listDocumentCategories,
  type DocumentCategory,
} from "@/lib/api/documentCategories";
import {
  deleteKnowledgeBase,
  listKnowledgeBases,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import { listTeams, type Team } from "@/lib/api/teams";

const ACCEPT_FILES = ".txt,.md,.pdf,.docx";
const SUPPORTED_EXTENSIONS = [".txt", ".md", ".pdf", ".docx"];
const MAX_SIZE = 10 * 1024 * 1024;
const MAX_BATCH = 500;
const PAGE_SIZE_OPTIONS = [20, 50, 100];

type StatusValue = "all" | DocumentIndexStatus;
type DetailTabValue = "preview" | "edit" | "versions";
type ConfirmDialogState = {
  open: boolean;
  title: string;
  description: string;
  contextRows?: Array<{ label: string; value: string }>;
  confirmLabel: string;
  tone: "primary" | "danger";
  onConfirm: null | (() => void | Promise<void>);
};

function getLastViewedDocStorageKey(knowledgeBaseId: number) {
  return `documents:last-viewed:${knowledgeBaseId}`;
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("zh-CN");
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";

  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  const fractionDigits = unitIndex === 0 ? 0 : 1;
  return `${size.toFixed(fractionDigits)} ${units[unitIndex]}`;
}

function looksLikeMarkdown(documentType: string | null | undefined, content: string) {
  const normalizedType = (documentType || "").toLowerCase();
  if (normalizedType === "md" || normalizedType === "markdown") return true;
  return /(^|\n)\s{0,3}(#{1,6}\s|[-*]\s|\d+\.\s|>\s|```)/.test(content);
}

function slugifyHeading(text: string, index: number) {
  const normalized = text
    .trim()
    .toLowerCase()
    .replace(/[`*_~#[\]()]/g, "")
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9\u4e00-\u9fa5-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");

  return normalized || `section-${index + 1}`;
}

function extractMarkdownHeadings(content: string) {
  const seen = new Map<string, number>();

  return content
    .split(/\r?\n/)
    .map((line) => line.match(/^(#{1,3})\s+(.+?)\s*#*\s*$/))
    .filter((match): match is RegExpMatchArray => Boolean(match))
    .map((match, index) => {
      const rawText = match[2].trim();
      const baseId = slugifyHeading(rawText, index);
      const duplicateCount = seen.get(baseId) ?? 0;
      seen.set(baseId, duplicateCount + 1);

      return {
        depth: match[1].length,
        text: rawText,
        id: duplicateCount === 0 ? baseId : `${baseId}-${duplicateCount + 1}`,
      };
    });
}

function getSourcePaths(files: File[]) {
  const paths = files.map((file) => file.webkitRelativePath || null);
  return paths.some(Boolean) ? paths : undefined;
}

const documentIndexMeta: Record<
  DocumentIndexStatus,
  { label: string; className: string; tone: "slate" | "amber" | "emerald" | "rose" }
> = {
  queued: {
    label: "排队中",
    className: "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-50",
    tone: "slate",
  },
  processing: {
    label: "索引中",
    className: "border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-50",
    tone: "amber",
  },
  indexed: {
    label: "已索引",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-50",
    tone: "emerald",
  },
  failed: {
    label: "索引失败",
    className: "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-50",
    tone: "rose",
  },
};

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
  const teamIdFromQuery = Number.isFinite(teamIdQuery) && teamIdQuery > 0 ? teamIdQuery : null;

  const [detailTab, setDetailTab] = useState<DetailTabValue>("preview");
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamId, setTeamId] = useState<number | null>(teamIdFromQuery);
  const [kb, setKb] = useState<KnowledgeBaseWithCount | null>(null);
  const [docs, setDocs] = useState<DocumentListItem[]>([]);
  const [docsTotal, setDocsTotal] = useState(0);
  const [docPage, setDocPage] = useState(1);
  const [docPageSize, setDocPageSize] = useState(20);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<DocumentDetail | null>(null);
  const [versions, setVersions] = useState<DocumentVersionItem[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [selectedVersionDoc, setSelectedVersionDoc] = useState<DocumentDetail | null>(null);
  const [loadingMeta, setLoadingMeta] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [loadingDoc, setLoadingDoc] = useState(false);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [loadingVersionDoc, setLoadingVersionDoc] = useState(false);
  const [reindexingAll, setReindexingAll] = useState(false);
  const [deletingKnowledgeBase, setDeletingKnowledgeBase] = useState(false);
  const [indexingOne, setIndexingOne] = useState(false);
  const [deletingOne, setDeletingOne] = useState(false);
  const [savingReplace, setSavingReplace] = useState(false);
  const [savingNewVersion, setSavingNewVersion] = useState(false);
  const [switchingCurrentVersion, setSwitchingCurrentVersion] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState>({
    open: false,
    title: "",
    description: "",
    confirmLabel: "确认",
    tone: "primary",
    onConfirm: null,
  });
  const [searchInput, setSearchInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [categories, setCategories] = useState<DocumentCategory[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [status, setStatus] = useState<StatusValue>("all");
  const [docType, setDocType] = useState("all");
  const [editing, setEditing] = useState(false);
  const [editorContent, setEditorContent] = useState("");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadCategoryId, setUploadCategoryId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const editorTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const previewScrollRef = useRef<HTMLDivElement | null>(null);
  const previewArticleRef = useRef<HTMLElement | null>(null);
  const docsRequestSeqRef = useRef(0);
  const [activePreviewHeadingId, setActivePreviewHeadingId] = useState<string | null>(null);

  const activeTeam = teams.find((item) => item.id === teamId) ?? null;
  const activeCategory = categories.find((item) => item.id === selectedCategoryId) ?? null;
  const uploadCategory = categories.find((item) => item.id === uploadCategoryId) ?? null;

  const typeOptions = useMemo(
    () =>
      Array.from(
        new Set(
          docs
            .map((item) => item.document_type)
            .filter((item): item is string => Boolean(item)),
        ),
      ),
    [docs],
  );

  const filteredDocs = useMemo(() => {
    return docs.filter((item) => {
      const hitStatus = status === "all" || item.index_status === status;
      const hitType = docType === "all" || item.document_type === docType;
      return hitStatus && hitType;
    });
  }, [docs, status, docType]);

  const hasActiveFilters =
    Boolean(searchInput.trim()) ||
    Boolean(keyword) ||
    status !== "all" ||
    docType !== "all" ||
    selectedCategoryId != null;
  const activeFilterCount = [
    Boolean(keyword),
    status !== "all",
    docType !== "all",
    selectedCategoryId != null,
  ].filter(Boolean).length;

  const { indexedDocsOnPage, processingDocsOnPage, failedDocsOnPage } = useMemo(() => {
    return {
      indexedDocsOnPage: filteredDocs.filter((item) => item.index_status === "indexed").length,
      processingDocsOnPage: filteredDocs.filter(
        (item) => item.index_status === "queued" || item.index_status === "processing",
      ).length,
      failedDocsOnPage: filteredDocs.filter((item) => item.index_status === "failed").length,
    };
  }, [filteredDocs]);
  const selectedDocListItem = docs.find((item) => item.id === selectedDocId) ?? null;
  const currentVersion =
    versions.find((item) => item.is_current) ??
    versions.find((item) => item.is_latest) ??
    versions[versions.length - 1] ??
    null;
  const latestVersion =
    versions.find((item) => item.is_latest) ?? versions[versions.length - 1] ?? null;
  const isViewingCurrentVersion =
    selectedVersionId == null || currentVersion == null || selectedVersionId === currentVersion.id;
  const isViewingLatestVersion =
    latestVersion != null && selectedVersionId === latestVersion.id;
  const activeDoc = isViewingCurrentVersion ? selectedDoc : selectedVersionDoc;
  const activeDocLoading = loadingDoc || (!isViewingCurrentVersion && loadingVersionDoc);
  const totalPages = Math.max(1, Math.ceil(docsTotal / docPageSize));
  const pageStart = docsTotal === 0 ? 0 : (docPage - 1) * docPageSize + 1;
  const pageEnd = docsTotal === 0 ? 0 : Math.min(docPage * docPageSize, docsTotal);
  const isEditorDirty = activeDoc != null && editorContent !== activeDoc.content;
  const selectedDocVersion = activeDoc?.version ?? selectedDocListItem?.version ?? 1;
  const selectedDocIndexStatus = isViewingCurrentVersion
    ? (selectedDoc?.index_status ?? selectedDocListItem?.index_status ?? "queued")
    : null;
  const selectedDocIndexed = selectedDocIndexStatus === "indexed";
  const selectedDocType =
    activeDoc?.document_type || selectedDocListItem?.document_type || "未知类型";
  const selectedDocSize = activeDoc?.size ?? selectedDocListItem?.size ?? 0;
  const selectedDocUpdatedAt = activeDoc?.updated_at ?? selectedDocListItem?.updated_at ?? null;
  const selectedDocCreatedAt = activeDoc?.created_at ?? selectedDocUpdatedAt;
  const selectedDocIndexError =
    isViewingCurrentVersion
      ? (selectedDoc?.index_error ?? selectedDocListItem?.index_error ?? null)
      : null;
  const lastViewedDocStorageKey =
    Number.isFinite(kbId) && kbId > 0 ? getLastViewedDocStorageKey(kbId) : null;
  const viewingVersionLabel = isViewingCurrentVersion
    ? `v${selectedDocVersion} · 当前版本`
    : isViewingLatestVersion
      ? `v${selectedDocVersion} · 最新版本`
      : `v${selectedDocVersion} · 历史版本`;
  const currentIndexMeta = selectedDocIndexStatus
    ? documentIndexMeta[selectedDocIndexStatus]
    : null;
  const retrievalStatus = !isViewingCurrentVersion
    ? {
        label: "不参与检索",
        className:
          "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-50",
      }
    : currentIndexMeta
      ? {
          label: currentIndexMeta.label,
          className: currentIndexMeta.className,
        }
      : {
          label: "状态未知",
          className:
            "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-50",
        };
  const selectedDocSummary = [
    activeDoc?.category_name || selectedDocListItem?.category_name || null,
    selectedDocType,
    formatBytes(selectedDocSize),
    selectedDocUpdatedAt ? `更新于 ${formatDateTime(selectedDocUpdatedAt)}` : null,
  ]
    .filter((item): item is string => Boolean(item))
    .join(" · ");
  const documentMetaLine = [
    `分类: ${activeDoc?.category_name || selectedDocListItem?.category_name || "未分类"}`,
    selectedDocCreatedAt ? `上传于 ${formatDateTime(selectedDocCreatedAt)}` : null,
  ]
    .filter((item): item is string => Boolean(item))
    .join(" · ");
  const primaryWarning = !isViewingCurrentVersion
    ? {
        tone: "blue" as const,
        message: "当前正在查看非生效版本。只有切换为当前版本后，它才会参与知识库问答检索。",
      }
    : selectedDocIndexStatus === "failed"
      ? {
          tone: "rose" as const,
          message: selectedDocIndexError || "当前文档索引失败，请重新排队索引后再检索。",
        }
      : selectedDocIndexStatus === "processing"
        ? {
            tone: "amber" as const,
            message: "当前文档正在建立索引，完成前暂时不会参与知识库问答检索。",
          }
        : selectedDocIndexStatus === "queued"
          ? {
              tone: "slate" as const,
              message: "当前文档已进入索引队列，完成前暂时不会参与知识库问答检索。",
            }
          : !selectedDocIndexed
            ? {
                tone: "amber" as const,
                message: "当前文档还未建立索引，现有内容暂时不会参与知识库问答检索。",
              }
            : null;
  const previewSupportsMarkdown = looksLikeMarkdown(
    activeDoc?.document_type ?? selectedDocListItem?.document_type,
    activeDoc?.content ?? "",
  );
  const previewHeadings = previewSupportsMarkdown
    ? extractMarkdownHeadings(activeDoc?.content ?? "")
    : [];
  const hasPreviewHeadings = previewHeadings.length > 0;

  const resetEditorState = (content = activeDoc?.content ?? "") => {
    setEditorContent(content);
    setEditing(false);
  };

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

  const requestDiscardDraft = ({
    title,
    description,
    confirmLabel,
    onConfirm,
  }: {
    title: string;
    description: string;
    confirmLabel: string;
    onConfirm: () => void;
  }) => {
    if (!isEditorDirty) {
      onConfirm();
      return;
    }

    openConfirmDialog({
      title,
      description,
      confirmLabel,
      tone: "primary",
      onConfirm: () => {
        resetEditorState();
        onConfirm();
      },
    });
  };

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
          toast.error("未找到该知识库，或当前账号无权限访问");
          router.push("/admin/documents");
          return;
        }

        setKb(found);
        setTeamId(foundTeamId);
      } catch (error) {
        if (!cancelled) {
          toast.error(error instanceof Error ? error.message : "加载知识库信息失败");
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
      setCategories([]);
      setSelectedCategoryId(null);
      setUploadCategoryId(null);
      return;
    }

    let cancelled = false;

    const run = async () => {
      try {
        const items = await listDocumentCategories(kbId);
        if (cancelled) return;
        setCategories(items);
        setSelectedCategoryId((prev) =>
          prev && items.some((item) => item.id === prev) ? prev : null,
        );
        setUploadCategoryId((prev) =>
          prev && items.some((item) => item.id === prev) ? prev : null,
        );
      } catch (error) {
        if (!cancelled) {
          setCategories([]);
          setSelectedCategoryId(null);
          setUploadCategoryId(null);
          toast.error(error instanceof Error ? error.message : "加载分类失败");
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [kbId, reloadToken]);

  const loadDocumentsList = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!Number.isFinite(kbId) || kbId <= 0) return;

    const requestSeq = ++docsRequestSeqRef.current;
    if (!silent) setLoadingDocs(true);

    try {
      const result = await listDocuments({
        page: docPage,
        page_size: docPageSize,
        keyword: keyword || undefined,
        knowledge_base_id: kbId,
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
      setSelectedDocId((prev) => {
        if (prev && result.items.some((item) => item.id === prev)) return prev;
        if (lastViewedDocStorageKey && typeof window !== "undefined") {
          const storedId = Number(window.localStorage.getItem(lastViewedDocStorageKey));
          if (storedId > 0 && result.items.some((item) => item.id === storedId)) {
            return storedId;
          }
        }
        return result.items[0]?.id ?? null;
      });

      if (silent) {
        setSelectedDoc((current) => {
          if (!current) return current;
          const updated = result.items.find((item) => item.id === current.id);
          if (!updated) return current;
          return {
            ...current,
            index_status: updated.index_status,
            index_error: updated.index_error,
            indexed_at: updated.indexed_at,
            updated_at: updated.updated_at,
          };
        });
      }
    } catch (error) {
      if (requestSeq !== docsRequestSeqRef.current) return;
      if (!silent) {
        toast.error(error instanceof Error ? error.message : "加载文档列表失败");
        setDocs([]);
        setDocsTotal(0);
      }
    } finally {
      if (requestSeq !== docsRequestSeqRef.current) return;
      if (!silent) setLoadingDocs(false);
    }
  }, [
    docPage,
    docPageSize,
    kbId,
    keyword,
    lastViewedDocStorageKey,
    reloadToken,
    selectedCategoryId,
    teamId,
  ]);

  useEffect(() => {
    void loadDocumentsList();
  }, [loadDocumentsList]);

  useEffect(() => {
    if (filteredDocs.length === 0) {
      return;
    }

    if (!selectedDocId) {
      setSelectedDocId(filteredDocs[0]?.id ?? null);
      return;
    }

    if (selectedDocId && !filteredDocs.some((item) => item.id === selectedDocId)) {
      setSelectedDocId(filteredDocs[0]?.id ?? null);
    }
  }, [filteredDocs, selectedDocId]);

  useEffect(() => {
    if (!lastViewedDocStorageKey || typeof window === "undefined") return;
    if (!selectedDocId) return;

    window.localStorage.setItem(lastViewedDocStorageKey, String(selectedDocId));
  }, [lastViewedDocStorageKey, selectedDocId]);

  useEffect(() => {
    if (!selectedDocId) {
      setSelectedDoc(null);
      setEditorContent("");
      setEditing(false);
      return;
    }

    let cancelled = false;

    const run = async () => {
      setLoadingDoc(true);

      try {
        const detail = await getDocument(selectedDocId);
        if (cancelled) return;

        setSelectedDoc(detail);
        setEditorContent(detail.content);
        setEditing(false);
      } catch (error) {
        if (!cancelled) {
          toast.error(error instanceof Error ? error.message : "加载文档详情失败");
        }
      } finally {
        if (!cancelled) setLoadingDoc(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [reloadToken, selectedDocId]);

  useEffect(() => {
    if (!docs.some((item) => item.index_status === "queued" || item.index_status === "processing")) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      void loadDocumentsList({ silent: true });
    }, 8000);
    return () => window.clearTimeout(timer);
  }, [docs, loadDocumentsList]);

  useEffect(() => {
    if (!selectedDocId) {
      setVersions([]);
      setSelectedVersionId(null);
      return;
    }

    let cancelled = false;

    const run = async () => {
      setLoadingVersions(true);

      try {
        const items = await getDocumentVersions(selectedDocId);
        if (cancelled) return;

        setVersions(items);
        setSelectedVersionId((prev) => {
          if (prev && items.some((item) => item.id === prev)) return prev;
          return (
            items.find((item) => item.is_current)?.id ??
            items.find((item) => item.is_latest)?.id ??
            items[items.length - 1]?.id ??
            null
          );
        });
      } catch (error) {
        if (!cancelled) {
          toast.error(error instanceof Error ? error.message : "加载版本列表失败");
          setVersions([]);
          setSelectedVersionId(null);
        }
      } finally {
        if (!cancelled) setLoadingVersions(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [reloadToken, selectedDocId]);

  useEffect(() => {
    if (!selectedVersionId) {
      setSelectedVersionDoc(null);
      setLoadingVersionDoc(false);
      return;
    }

    if (isViewingCurrentVersion) {
      setSelectedVersionDoc(null);
      setLoadingVersionDoc(false);
      return;
    }

    let cancelled = false;

    const run = async () => {
      setLoadingVersionDoc(true);
      setSelectedVersionDoc(null);

      try {
        const detail = await getDocument(selectedVersionId);
        if (!cancelled) setSelectedVersionDoc(detail);
      } catch (error) {
        if (!cancelled) {
          toast.error(error instanceof Error ? error.message : "加载版本详情失败");
        }
      } finally {
        if (!cancelled) setLoadingVersionDoc(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [isViewingCurrentVersion, selectedVersionId]);

  useEffect(() => {
    if (!isEditorDirty) return;

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isEditorDirty]);

  useEffect(() => {
    if (detailTab !== "edit") return;

    const textarea = editorTextareaRef.current;
    if (!textarea) return;

    textarea.style.height = "0px";
    textarea.style.height = `${Math.max(textarea.scrollHeight, 640)}px`;
  }, [detailTab, editorContent]);

  useEffect(() => {
    const article = previewArticleRef.current;
    if (!article || previewHeadings.length === 0) return;

    const headingElements = Array.from(article.querySelectorAll("h1, h2, h3"));
    headingElements.forEach((element, index) => {
      const heading = previewHeadings[index];
      if (!heading) return;
      element.id = heading.id;
      (element as HTMLElement).style.scrollMarginTop = "104px";
    });
  }, [activeDoc?.content, previewHeadings]);

  useEffect(() => {
    const scrollContainer = previewScrollRef.current;
    const article = previewArticleRef.current;
    if (!scrollContainer || !article || previewHeadings.length === 0 || detailTab !== "preview") {
      setActivePreviewHeadingId(previewHeadings[0]?.id ?? null);
      return;
    }

    const syncActiveHeading = () => {
      const headings = Array.from(article.querySelectorAll<HTMLElement>("h1, h2, h3"));
      if (headings.length === 0) {
        setActivePreviewHeadingId(previewHeadings[0]?.id ?? null);
        return;
      }

      const containerTop = scrollContainer.getBoundingClientRect().top;
      const current =
        headings
          .filter((heading) => heading.getBoundingClientRect().top - containerTop <= 120)
          .at(-1) ?? headings[0];

      setActivePreviewHeadingId(current.id || (previewHeadings[0]?.id ?? null));
    };

    syncActiveHeading();
    scrollContainer.addEventListener("scroll", syncActiveHeading, { passive: true });
    return () => scrollContainer.removeEventListener("scroll", syncActiveHeading);
  }, [activeDoc?.content, detailTab, previewHeadings]);

  const reload = () => setReloadToken((value) => value + 1);

  const openDocumentsList = () => {
    requestDiscardDraft({
      title: "离开当前文档工作台？",
      description: "你还没有保存当前修改。现在返回知识库列表，会直接丢失这部分编辑内容。",
      confirmLabel: "放弃修改并返回",
      onConfirm: () => router.push("/admin/documents"),
    });
  };

  const onDetailTabChange = (nextTab: DetailTabValue) => {
    if (nextTab === detailTab) return;
    if (detailTab === "edit" && nextTab !== "edit") {
      requestDiscardDraft({
        title: "切换标签页？",
        description: "当前编辑内容还没有保存。离开编辑区后，这些本地修改会被放弃。",
        confirmLabel: "放弃修改并切换",
        onConfirm: () => setDetailTab(nextTab),
      });
      return;
    }

    if (nextTab === "edit") {
      if (!activeDoc) {
        toast.error("当前版本内容仍在加载，请稍后再试");
        return;
      }
      resetEditorState(activeDoc.content);
    }

    setDetailTab(nextTab);
  };

  const onSelectDocument = (docId: number) => {
    if (docId === selectedDocId) {
      setDetailTab("preview");
      return;
    }
    requestDiscardDraft({
      title: "切换到另一篇文档？",
      description: "当前文档还有未保存修改。现在切换文档，会丢失这部分编辑内容。",
      confirmLabel: "放弃修改并切换",
      onConfirm: () => {
        setSelectedDocId(docId);
        setDetailTab("preview");
      },
    });
  };

  const scrollPreviewToTop = () => {
    previewScrollRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  };

  const switchReadingTarget = useCallback(
    (versionId: number | null) => {
      const applyTarget = () => {
        setSelectedVersionId(versionId);
        setDetailTab("preview");
      };

      if (detailTab === "edit" && isEditorDirty) {
        requestDiscardDraft({
          title: "切换查看版本？",
          description: "当前编辑内容还没有保存。切换版本后，这些本地修改会被放弃。",
          confirmLabel: "放弃修改并切换",
          onConfirm: applyTarget,
        });
        return;
      }

      applyTarget();
    },
    [detailTab, isEditorDirty],
  );

  const onSelectPreviewHeading = (headingId: string) => {
    const target = Array.from(
      previewArticleRef.current?.querySelectorAll<HTMLElement>("h1, h2, h3") ?? [],
    ).find((element) => element.id === headingId);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const onSearch = useCallback(() => {
    setKeyword(searchInput.trim());
    setDocPage(1);
  }, [searchInput]);

  const onClearSearch = useCallback(() => {
    setSearchInput("");
    setKeyword("");
    setDocPage(1);
  }, []);

  const onResetFilters = useCallback(() => {
    setSearchInput("");
    setKeyword("");
    setStatus("all");
    setDocType("all");
    setSelectedCategoryId(null);
    setDocPage(1);
  }, []);

  const onEditFromVersion = () => {
    if (!activeDoc) return;
    setEditorContent(activeDoc.content);
    setEditing(selectedDoc?.content !== activeDoc.content);
    setDetailTab("edit");
  };

  const onSwitchCurrentVersion = async () => {
    if (!selectedVersionId || isViewingCurrentVersion) return;
    openConfirmDialog({
      title: "切换当前生效版本？",
      description:
        "切换后，这个版本会立即成为知识库问答的生效内容；原当前版本将不再参与检索。",
      confirmLabel: "确认切换",
      tone: "primary",
      onConfirm: async () => {
        setSwitchingCurrentVersion(true);
        try {
          const updated = await switchCurrentDocumentVersion(selectedVersionId);
          setSelectedDocId(updated.id);
          setSelectedVersionId(updated.id);
          setDetailTab("preview");
          toast.success(`已切换为当前版本 v${updated.version}，并加入索引队列`);
          reload();
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "切换当前版本失败");
        } finally {
          setSwitchingCurrentVersion(false);
        }
      },
    });
  };

  const onReindexAll = async () => {
    setReindexingAll(true);
    try {
      const result = await reindexAll({ team_id: teamId ?? undefined, knowledge_base_id: kbId });
      toast.success(result.message || `已将 ${result.queued} 篇文档加入重建队列`);
      reload();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "全量重建索引失败");
    } finally {
      setReindexingAll(false);
    }
  };

  const onDeleteKnowledgeBase = () => {
    if (!kb) return;

    openConfirmDialog({
      title: "删除这个知识库？",
      description: `“${kb.name}”会被删除，文档会从知识库解绑，之后可重新归档到其他知识库。此操作不可恢复。`,
      contextRows: [
        { label: "所属团队", value: activeTeam?.name || "未识别团队" },
        { label: "目标知识库", value: kb.name },
        { label: "包含文档", value: `${kb.document_count} 篇` },
      ],
      confirmLabel: "确认删除",
      tone: "danger",
      onConfirm: async () => {
        setDeletingKnowledgeBase(true);
        try {
          await deleteKnowledgeBase(kb.id);
          toast.success("知识库已删除");
          router.push("/admin/documents");
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "删除失败");
        } finally {
          setDeletingKnowledgeBase(false);
        }
      },
    });
  };

  const onReindexOne = async () => {
    if (!selectedDocListItem) return;

    setIndexingOne(true);
    try {
      const result = await indexDocument(selectedDocListItem.id);
      toast.success(result.message || "文档已加入索引队列");
      reload();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "文档重新索引失败");
    } finally {
      setIndexingOne(false);
    }
  };

  const onDeleteOne = async () => {
    if (!selectedDocListItem) return;
    openConfirmDialog({
      title: "删除这篇文档？",
      description: `“${selectedDocListItem.title}”及其全部版本都会被删除，相关版本记录也无法恢复。`,
      confirmLabel: "确认删除",
      tone: "danger",
      onConfirm: async () => {
        setDeletingOne(true);
        try {
          await deleteDocument(selectedDocListItem.id);
          toast.success("文档已删除");
          reload();
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "删除失败");
        } finally {
          setDeletingOne(false);
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
        await uploadDocument(validFiles[0], kbId, {
          categoryId: uploadCategoryId ?? undefined,
          sourcePath: sourcePaths?.[0] ?? null,
        });
      } else {
        await uploadDocumentsBatch(validFiles, kbId, {
          categoryId: uploadCategoryId ?? undefined,
          sourcePaths,
        });
      }

      toast.success(`已上传 ${validFiles.length} 个文件，并加入索引队列`);
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

  const onCancelEdit = () => {
    const exitEdit = () => {
      resetEditorState();
      setDetailTab("preview");
    };

    if (isEditorDirty) {
      requestDiscardDraft({
        title: "放弃当前编辑内容？",
        description: "当前编辑内容还没有保存。离开编辑区后，这些本地修改会被放弃。",
        confirmLabel: "放弃修改并返回",
        onConfirm: exitEdit,
      });
      return;
    }

    exitEdit();
  };

  const onSaveReplace = async () => {
    if (!selectedDoc) return;

    setSavingReplace(true);
    try {
      const updated = await replaceDocumentContent(selectedDoc.id, editorContent);
      setSelectedDoc(updated);
      setEditorContent(updated.content);
      setEditing(false);
      setSelectedVersionId(updated.id);
      setDetailTab("preview");
      toast.success("当前文档内容已更新，并重新加入索引队列");
      reload();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSavingReplace(false);
    }
  };

  const onSaveNewVersion = async () => {
    if (!selectedDoc) return;

    setSavingNewVersion(true);
    try {
      const created = await createDocumentVersion(selectedDoc.id, editorContent);
      setEditing(false);
      setDetailTab("preview");
      setDocPage(1);
      setSelectedDocId(created.id);
      setSelectedVersionId(created.id);
      toast.success(`已保存为版本 v${created.version}，并加入索引队列`);
      reload();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "新建版本失败");
    } finally {
      setSavingNewVersion(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-white text-slate-900">
      <Toaster position="top-right" richColors />

      <header className="shrink-0 border-b border-slate-100 bg-white/95 px-4 py-4 backdrop-blur-sm sm:px-6">
        <div className="mx-auto flex max-w-[1700px] flex-wrap items-end justify-between gap-3">
          <div>
            <Button
              variant="ghost"
              size="sm"
              className="mb-2 rounded-full px-3 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
              onClick={openDocumentsList}
            >
              <ArrowLeft className="mr-1 h-4 w-4" />
              返回
            </Button>
            <h1 className="text-2xl font-semibold tracking-tight">{kb?.name || "知识库工作台"}</h1>
            <p className="mt-1 text-sm text-slate-500">
              {activeTeam ? `所属团队：${activeTeam.name}` : "正在识别所属团队..."} |{" "}
              {loadingMeta ? "正在同步知识库信息..." : `共 ${kb?.document_count ?? docsTotal} 篇文档`}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              className="rounded-full border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
              disabled={deletingKnowledgeBase}
              onClick={onDeleteKnowledgeBase}
            >
              {deletingKnowledgeBase ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="mr-2 h-4 w-4" />
              )}
              删除知识库
            </Button>
            <Button
              variant="outline"
              className="rounded-full border-slate-200 text-slate-700"
              disabled={reindexingAll}
              onClick={() => void onReindexAll()}
            >
              {reindexingAll ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCcw className="mr-2 h-4 w-4" />
              )}
              全量重建索引
            </Button>
            <Button
              className="rounded-full bg-slate-900 text-white hover:bg-slate-800"
              onClick={() => {
                setUploadCategoryId(activeCategory?.id ?? null);
                setUploadModalOpen(true);
              }}
            >
              <UploadCloud className="mr-2 h-4 w-4" />
              上传文档
            </Button>
          </div>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-hidden bg-white">
        <section className="mx-auto flex h-full max-w-[1700px] min-h-0 flex-col xl:flex-row">
          <section className="flex min-h-0 flex-col border-b border-slate-100 bg-slate-50/70 xl:h-full xl:w-[360px] xl:shrink-0 xl:border-b-0 xl:border-r">
            <div className="shrink-0 border-b border-slate-100 px-4 py-4">
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") onSearch();
                    }}
                    placeholder="搜索文档标题"
                    className="h-9 rounded-full border-transparent bg-slate-100 pl-10 pr-4 text-sm shadow-none placeholder:text-slate-400 hover:bg-slate-200 focus-visible:bg-white focus-visible:ring-1 focus-visible:ring-slate-300"
                  />
                </div>
                <DropdownMenu.Root>
                  <DropdownMenu.Trigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className={cn(
                        "relative h-9 rounded-full px-3 text-slate-500 hover:bg-slate-100 hover:text-slate-900",
                        hasActiveFilters ? "text-blue-600" : "",
                      )}
                    >
                      <ListFilter className="mr-1.5 h-4 w-4" />
                      筛选
                      {activeFilterCount > 0 ? (
                        <span className="ml-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-blue-600 px-1.5 text-[10px] font-semibold text-white">
                          {activeFilterCount}
                        </span>
                      ) : null}
                    </Button>
                  </DropdownMenu.Trigger>
                  <DropdownMenu.Portal>
                    <DropdownMenu.Content
                      align="end"
                      sideOffset={8}
                      className="z-50 w-72 rounded-2xl border border-slate-200 bg-white p-3 shadow-xl"
                    >
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-medium text-slate-900">筛选条件</p>
                          {hasActiveFilters ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 rounded-full px-2.5 text-xs text-slate-500"
                              onClick={onResetFilters}
                            >
                              重置
                            </Button>
                          ) : null}
                        </div>
                        <div>
                          <p className="mb-1.5 text-xs text-slate-500">状态</p>
                          <select
                            value={status}
                            onChange={(e) => setStatus(e.target.value as StatusValue)}
                            className="h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition-colors hover:border-slate-300 focus:border-slate-300"
                          >
                            <option value="all">全部状态</option>
                            <option value="queued">排队中</option>
                            <option value="processing">索引中</option>
                            <option value="indexed">已索引</option>
                            <option value="failed">索引失败</option>
                          </select>
                        </div>
                        <div>
                          <p className="mb-1.5 text-xs text-slate-500">类型</p>
                          <select
                            value={docType}
                            onChange={(e) => setDocType(e.target.value)}
                            className="h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition-colors hover:border-slate-300 focus:border-slate-300"
                          >
                            <option value="all">全部类型</option>
                            {typeOptions.map((item) => (
                              <option key={item} value={item}>
                                {item}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <p className="mb-1.5 text-xs text-slate-500">分类</p>
                          <select
                            value={selectedCategoryId ?? ""}
                            onChange={(e) => {
                              setSelectedCategoryId(e.target.value ? Number(e.target.value) : null);
                              setDocPage(1);
                            }}
                            className="h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition-colors hover:border-slate-300 focus:border-slate-300"
                          >
                            <option value="">全部分类</option>
                            {categories.map((category) => (
                              <option key={category.id} value={category.id}>
                                {category.name}（{category.document_count}）
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </DropdownMenu.Content>
                  </DropdownMenu.Portal>
                </DropdownMenu.Root>
                {keyword || searchInput ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-9 rounded-full px-3 text-slate-500 hover:bg-slate-100"
                    onClick={onClearSearch}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                ) : null}
              </div>

              {hasActiveFilters ? (
                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  {keyword ? (
                    <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-1 text-xs text-blue-700">
                      {keyword}
                    </span>
                  ) : null}
                  {status !== "all" ? (
                    <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 text-xs text-slate-600 ring-1 ring-slate-200">
                      {documentIndexMeta[status].label}
                    </span>
                  ) : null}
                  {docType !== "all" ? (
                    <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 text-xs text-slate-600 ring-1 ring-slate-200">
                      {docType}
                    </span>
                  ) : null}
                  {activeCategory ? (
                    <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 text-xs text-slate-600 ring-1 ring-slate-200">
                      {activeCategory.name}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>

            <div className="shrink-0 border-b border-slate-100/80 px-4 py-3 text-xs text-slate-500">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  {loadingDocs ? (
                    <span>正在加载文档...</span>
                  ) : docsTotal > 0 ? (
                    <>
                      <span className="font-medium text-slate-700">
                        {pageStart}-{pageEnd} / {docsTotal}
                      </span>
                      {hasActiveFilters && filteredDocs.length !== docsTotal ? (
                        <span className="rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">
                          筛选后 {filteredDocs.length}
                        </span>
                      ) : null}
                    </>
                  ) : (
                    <span>暂无文档</span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
                    {indexedDocsOnPage}
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-500"></span>
                    {processingDocsOnPage}
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-rose-500"></span>
                    {failedDocsOnPage}
                  </span>
                </div>
              </div>
            </div>

            <div
              className={cn(
                "min-h-[240px] flex-1 overflow-y-auto overscroll-contain px-3 pb-3 pt-2 xl:min-h-0 xl:pb-4",
                "[scrollbar-width:thin] [&::-webkit-scrollbar]:w-2",
                "[&::-webkit-scrollbar-track]:bg-transparent",
                "[&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-300",
                "[&::-webkit-scrollbar-thumb:hover]:bg-slate-400",
              )}
            >
              {loadingMeta || loadingDocs ? (
                <div className="flex flex-col items-center justify-center py-12 text-slate-500">
                  <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
                  <p className="mt-3 text-sm">正在加载文档列表...</p>
                </div>
              ) : docs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center text-slate-500">
                  <UploadCloud className="h-8 w-8 text-slate-300" />
                  <p className="mt-4 text-sm font-medium text-slate-700">暂无文档</p>
                  <p className="mt-1 text-xs">点击右上角“上传文档”开始添加内容</p>
                </div>
              ) : filteredDocs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center text-slate-500">
                  <Search className="h-8 w-8 text-slate-300" />
                  <p className="mt-4 text-sm font-medium text-slate-700">没有符合条件的文档</p>
                  <p className="mt-1 text-xs">尝试调整筛选条件或清空搜索</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredDocs.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => onSelectDocument(item.id)}
                      className={cn(
                        "group flex w-full items-start gap-3 rounded-2xl border px-4 py-3 text-left shadow-sm transition-all",
                        selectedDocId === item.id
                          ? "border-blue-200 bg-blue-50/90 shadow-blue-100/70"
                          : "border-slate-200/80 bg-white/90 hover:border-slate-300 hover:bg-white",
                      )}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <h4
                            className={cn(
                              "truncate text-sm transition-colors",
                              selectedDocId === item.id
                                ? "font-semibold text-blue-900"
                                : "text-slate-900",
                            )}
                          >
                            {item.title}
                          </h4>
                          <span
                            className={cn(
                              "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium",
                              item.index_status === "indexed"
                                ? "text-emerald-700"
                                : item.index_status === "failed"
                                  ? "text-rose-700"
                                  : item.index_status === "processing"
                                    ? "text-amber-700"
                                    : "text-slate-500",
                            )}
                          >
                            <span
                              className={cn(
                                "h-1.5 w-1.5 rounded-full",
                                item.index_status === "indexed"
                                  ? "bg-emerald-500"
                                  : item.index_status === "failed"
                                    ? "bg-rose-500"
                                    : item.index_status === "processing"
                                      ? "bg-amber-500"
                                      : "bg-slate-400",
                              )}
                            />
                            {documentIndexMeta[item.index_status].label}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
                          {item.category_name ? <span>{item.category_name}</span> : null}
                          <span>{item.document_type || "未知类型"}</span>
                          <span>{formatBytes(item.size)}</span>
                          <span>{formatDate(item.updated_at)}</span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="shrink-0 border-t border-slate-100 bg-white/70 px-4 py-3 text-xs text-slate-500 backdrop-blur">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span>每页</span>
                  <select
                    value={docPageSize}
                    onChange={(e) => {
                      setDocPageSize(Number(e.target.value));
                      setDocPage(1);
                    }}
                    className="h-8 rounded-full border border-slate-200 bg-white px-3 text-xs text-slate-700 outline-none hover:border-slate-300"
                  >
                    {PAGE_SIZE_OPTIONS.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center gap-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 rounded-full p-0"
                    disabled={docPage <= 1 || loadingDocs}
                    onClick={() => setDocPage(1)}
                    title="首页"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    <ChevronLeft className="-ml-2.5 h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 rounded-full p-0"
                    disabled={docPage <= 1 || loadingDocs}
                    onClick={() => setDocPage((prev) => Math.max(1, prev - 1))}
                    title="上一页"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </Button>
                  <span className="min-w-[80px] text-center">
                    {docPage} / {totalPages}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 rounded-full p-0"
                    disabled={docPage >= totalPages || loadingDocs}
                    onClick={() => setDocPage((prev) => Math.min(totalPages, prev + 1))}
                    title="下一页"
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 rounded-full p-0"
                    disabled={docPage >= totalPages || loadingDocs}
                    onClick={() => setDocPage(totalPages)}
                    title="末页"
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                    <ChevronRight className="-ml-2.5 h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          </section>

          <section className="min-h-0 flex-1 overflow-hidden bg-white">
            {selectedDocListItem ? (
              <div className="flex h-full min-h-0 flex-col">
                <div className="px-6 py-8 xl:px-12">
                  <div className="mx-auto max-w-5xl border-b border-slate-100 pb-4">
                    {filteredDocs.length === 0 ? (
                      <div className="mb-4 rounded-full bg-amber-50 px-4 py-2 text-sm text-amber-700">
                        当前筛选条件下没有匹配的文档，仍显示之前选中的内容。
                      </div>
                    ) : null}
                    <div className="flex items-start justify-between gap-6">
                      <div className="min-w-0 flex-1">
                        <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">
                          {selectedDocListItem.title}
                        </h2>
                        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-500">
                          <span>{documentMetaLine}</span>
                          <span>·</span>
                          <DropdownMenu.Root>
                            <DropdownMenu.Trigger asChild>
                              <button
                                type="button"
                                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-sm text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
                              >
                                版本 v{selectedDocVersion}
                                <ChevronDown className="h-3.5 w-3.5" />
                              </button>
                            </DropdownMenu.Trigger>
                            <DropdownMenu.Portal>
                              <DropdownMenu.Content
                                side="bottom"
                                align="start"
                                sideOffset={8}
                                className="z-50 max-h-[360px] w-72 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-2 shadow-xl"
                              >
                                <div className="px-2 py-1 text-xs font-medium text-slate-500">版本历史</div>
                                {loadingVersions ? (
                                  <div className="flex items-center gap-2 px-3 py-3 text-sm text-slate-500">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    正在加载版本...
                                  </div>
                                ) : versions.length === 0 ? (
                                  <div className="px-3 py-3 text-sm text-slate-500">暂无版本记录</div>
                                ) : (
                                  versions.map((item) => (
                                    <DropdownMenu.Item
                                      key={item.id}
                                      onSelect={() => switchReadingTarget(item.is_current ? null : item.id)}
                                      className={cn(
                                        "flex cursor-pointer select-none items-center justify-between rounded-xl px-3 py-2 outline-none transition-colors hover:bg-slate-100 focus:bg-slate-100",
                                        selectedVersionId === item.id || (item.is_current && isViewingCurrentVersion)
                                          ? "bg-slate-100"
                                          : "",
                                      )}
                                    >
                                      <div>
                                        <p className="text-sm font-medium text-slate-900">v{item.version}</p>
                                        <p className="text-xs text-slate-500">{formatDateTime(item.created_at)}</p>
                                      </div>
                                      <div className="flex flex-wrap gap-1">
                                        {item.is_current ? (
                                          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                                            当前
                                          </span>
                                        ) : null}
                                        {item.is_latest ? (
                                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                                            最新
                                          </span>
                                        ) : null}
                                      </div>
                                    </DropdownMenu.Item>
                                  ))
                                )}
                              </DropdownMenu.Content>
                            </DropdownMenu.Portal>
                          </DropdownMenu.Root>
                        </div>
                        {primaryWarning ? (
                          <div
                            className={cn(
                              "mt-4 rounded-2xl px-4 py-3 text-sm",
                              primaryWarning.tone === "blue"
                                ? "bg-blue-50 text-blue-800"
                                : primaryWarning.tone === "rose"
                                  ? "bg-rose-50 text-rose-800"
                                  : primaryWarning.tone === "slate"
                                    ? "bg-slate-100 text-slate-700"
                                    : "bg-amber-50 text-amber-800",
                            )}
                          >
                            {primaryWarning.message}
                          </div>
                        ) : null}
                      </div>

                      <div className="flex shrink-0 items-start gap-2">
                        {detailTab === "edit" ? (
                          <Button
                            variant="outline"
                            className="h-9 rounded-full border-slate-200 px-4"
                            onClick={onCancelEdit}
                            disabled={loadingDoc}
                          >
                            返回阅读
                          </Button>
                        ) : (
                          <Button
                            className="h-9 rounded-full bg-slate-900 px-4 text-white hover:bg-slate-800"
                            onClick={() => {
                              if (isViewingCurrentVersion) {
                                void onDetailTabChange("edit");
                              } else {
                                onEditFromVersion();
                              }
                            }}
                            disabled={activeDocLoading}
                          >
                            <PencilLine className="mr-2 h-4 w-4" />
                            编辑正文
                          </Button>
                        )}

                        <Button
                          variant="outline"
                          size="icon"
                          className="h-9 w-9 rounded-full border-slate-200"
                          onClick={() =>
                            isViewingCurrentVersion ? void onReindexOne() : switchReadingTarget(null)
                          }
                          disabled={
                            isViewingCurrentVersion
                              ? !selectedDocListItem || indexingOne
                              : currentVersion == null
                          }
                          title={isViewingCurrentVersion ? "重新索引" : "查看当前版本"}
                        >
                          {isViewingCurrentVersion ? (
                            indexingOne ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <RefreshCcw className="h-4 w-4" />
                            )
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>

                        <DropdownMenu.Root>
                          <DropdownMenu.Trigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-9 w-9 rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenu.Trigger>
                          <DropdownMenu.Portal>
                            <DropdownMenu.Content
                              side="bottom"
                              align="end"
                              sideOffset={8}
                              className="z-50 min-w-[180px] rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl"
                            >
                              {!isViewingCurrentVersion ? (
                                <DropdownMenu.Item
                                  onSelect={() => switchReadingTarget(null)}
                                  className="flex cursor-pointer select-none items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-700 outline-none transition-colors hover:bg-slate-100 focus:bg-slate-100"
                                >
                                  <Eye className="h-4 w-4" />
                                  查看当前版本
                                </DropdownMenu.Item>
                              ) : null}
                              {!isViewingCurrentVersion ? (
                                <DropdownMenu.Item
                                  onSelect={() => void onSwitchCurrentVersion()}
                                  disabled={switchingCurrentVersion}
                                  className="flex cursor-pointer select-none items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-700 outline-none transition-colors hover:bg-slate-100 focus:bg-slate-100 data-[disabled]:opacity-50"
                                >
                                  {switchingCurrentVersion ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <FileClock className="h-4 w-4" />
                                  )}
                                  切换为当前版本
                                </DropdownMenu.Item>
                              ) : null}
                              {latestVersion && selectedVersionId !== latestVersion.id ? (
                                <DropdownMenu.Item
                                  onSelect={() =>
                                    switchReadingTarget(latestVersion.is_current ? null : latestVersion.id)
                                  }
                                  className="flex cursor-pointer select-none items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-700 outline-none transition-colors hover:bg-slate-100 focus:bg-slate-100"
                                >
                                  <FileClock className="h-4 w-4" />
                                  查看最新版本
                                </DropdownMenu.Item>
                              ) : null}
                              <DropdownMenu.Item
                                onSelect={() =>
                                  void navigator.clipboard
                                    .writeText(String(selectedDocListItem.id))
                                    .then(() => toast.success("文档 ID 已复制"))
                                    .catch(() => toast.error("复制失败"))
                                }
                                className="flex cursor-pointer select-none items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-700 outline-none transition-colors hover:bg-slate-100 focus:bg-slate-100"
                              >
                                <FileClock className="h-4 w-4" />
                                复制文档 ID
                              </DropdownMenu.Item>
                              <DropdownMenu.Separator className="my-1 h-px bg-slate-100" />
                              <DropdownMenu.Item
                                onSelect={() => void onDeleteOne()}
                                disabled={!selectedDocListItem || deletingOne}
                                className="flex cursor-pointer select-none items-center gap-2 rounded-xl px-3 py-2 text-sm text-rose-600 outline-none transition-colors hover:bg-rose-50 focus:bg-rose-50 data-[disabled]:opacity-50"
                              >
                                {deletingOne ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <Trash2 className="h-4 w-4" />
                                )}
                                删除文档
                              </DropdownMenu.Item>
                            </DropdownMenu.Content>
                          </DropdownMenu.Portal>
                        </DropdownMenu.Root>
                      </div>
                    </div>
                  </div>
                </div>

                {detailTab === "edit" ? (
                  <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-10 xl:px-12">
                    <div className="mx-auto flex w-full max-w-6xl flex-col">
                      <div className="mb-4 rounded-3xl border border-slate-200 bg-slate-50/70 px-5 py-4">
                        {isViewingCurrentVersion ? (
                          <div className="text-sm text-slate-500">
                            正在编辑版本 v{selectedDocVersion}。编辑区会按正文长度自动展开，便于一次看完整篇文档。
                          </div>
                        ) : (
                          <div className="text-sm text-slate-500">
                            正在基于版本 v{selectedDocVersion} 编辑。保存后建议新建版本，避免直接覆盖历史版本。
                          </div>
                        )}
                      </div>

                      <div className="rounded-[32px] border border-slate-200 bg-white shadow-sm">
                        <Textarea
                          ref={editorTextareaRef}
                          value={editorContent}
                          onChange={(e) => {
                            setEditorContent(e.target.value);
                            if (!editing) setEditing(true);
                          }}
                          className="min-h-[calc(100vh-320px)] w-full resize-none overflow-hidden rounded-[32px] border-0 bg-transparent px-6 py-6 font-mono text-[15px] leading-8 text-slate-800 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
                          placeholder="在这里编辑文档内容"
                        />
                      </div>

                      <div className="sticky bottom-0 mt-4 border-t border-slate-200 bg-white/95 px-1 py-4 backdrop-blur">
                        <div className="flex flex-col gap-3 rounded-3xl bg-slate-900 px-4 py-4 text-white shadow-2xl sm:flex-row sm:items-center sm:justify-between">
                          <p className="text-sm text-slate-300">
                            {isEditorDirty ? "有未保存修改" : "当前没有新的修改"}
                          </p>

                          <div className="flex flex-wrap items-center gap-2">
                            <Button
                              variant="ghost"
                              className="rounded-full px-4 text-white hover:bg-white/10 hover:text-white"
                              onClick={onCancelEdit}
                              disabled={loadingDoc}
                            >
                              返回阅读
                            </Button>
                            <Button
                              variant="outline"
                              className="rounded-full border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
                              onClick={() => void onSaveReplace()}
                              disabled={
                                activeDocLoading ||
                                !selectedDoc ||
                                !isViewingCurrentVersion ||
                                !isViewingLatestVersion ||
                                !isEditorDirty ||
                                savingReplace
                              }
                            >
                              {savingReplace ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              ) : (
                                <Save className="mr-2 h-4 w-4" />
                              )}
                              保存并覆盖
                            </Button>
                            <Button
                              className="rounded-full bg-white px-4 text-slate-900 hover:bg-slate-100"
                              onClick={() => void onSaveNewVersion()}
                              disabled={loadingDoc || !selectedDoc || !isEditorDirty || savingNewVersion}
                            >
                              {savingNewVersion ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              ) : (
                                <FileClock className="mr-2 h-4 w-4" />
                              )}
                              保存为新版本
                            </Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div ref={previewScrollRef} className="min-h-0 flex-1 overflow-y-auto px-6 pb-12 xl:px-12">
                    {activeDocLoading ? (
                      <div className="flex min-h-[320px] items-center justify-center text-sm text-slate-500">
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        正在加载正文...
                      </div>
                    ) : !activeDoc ? (
                      <div className="flex min-h-[320px] items-center justify-center text-sm text-slate-500">
                        暂无可阅读内容。
                      </div>
                    ) : !activeDoc.content ? (
                      <div className="flex min-h-[320px] items-center justify-center text-sm text-slate-500">
                        当前文档还没有可预览的正文内容。
                      </div>
                    ) : (
                      <div
                        className={cn(
                          "mx-auto w-full",
                          hasPreviewHeadings ? "xl:flex xl:items-start xl:gap-8" : "",
                        )}
                      >
                        <article ref={previewArticleRef} className="min-w-0 flex-1 pb-12">
                          {previewSupportsMarkdown ? (
                            <div className="text-base leading-relaxed text-slate-700">
                              <AnswerMarkdown text={activeDoc.content} />
                            </div>
                          ) : (
                            <pre className="whitespace-pre-wrap break-words font-sans text-base leading-relaxed text-slate-700">
                              {activeDoc.content}
                            </pre>
                          )}
                        </article>

                        {hasPreviewHeadings ? (
                          <aside className="hidden xl:block sticky top-6 w-64 shrink-0 border-l border-slate-200 pl-4">
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-sm text-slate-500">目录</p>
                              <button
                                type="button"
                                onClick={scrollPreviewToTop}
                                className="text-xs text-slate-400 transition-colors hover:text-slate-700"
                              >
                                顶部
                              </button>
                            </div>
                            <div className="mt-3 space-y-1">
                              {previewHeadings.map((heading) => (
                                <button
                                  key={heading.id}
                                  type="button"
                                  onClick={() => onSelectPreviewHeading(heading.id)}
                                  className={cn(
                                    "block w-full border-l border-transparent py-1 pl-3 text-left text-sm transition-colors",
                                    heading.depth === 2 ? "pl-5" : "",
                                    heading.depth === 3 ? "pl-7 text-[13px]" : "",
                                    activePreviewHeadingId === heading.id
                                      ? "border-slate-900 font-semibold text-slate-900"
                                      : "text-slate-500 hover:text-slate-900",
                                  )}
                                >
                                  {heading.text}
                                </button>
                              ))}
                            </div>
                          </aside>
                        ) : null}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex h-full min-h-[360px] items-center justify-center px-6 py-16 xl:h-[calc(100vh-88px)]">
                <div className="text-center">
                  <Eye className="mx-auto h-10 w-10 text-slate-300" />
                  <p className="mt-4 text-base font-medium text-slate-700">从左侧选择一篇文档开始阅读</p>
                  <p className="mt-1 text-sm text-slate-500">选中文档后即可查看正文并进行编辑。</p>
                </div>
              </div>
            )}
          </section>
        </section>
      </main>

      {confirmDialog.open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm"
          onClick={closeConfirmDialog}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-lg font-semibold text-slate-900">{confirmDialog.title}</p>
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
              <Button variant="ghost" size="icon" onClick={closeConfirmDialog}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-2">
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
            className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-lg font-semibold">上传文档</p>
                  <p className="text-sm text-slate-500">
                    选择文件后即可上传到当前知识库。
                  </p>
                </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => !uploading && setUploadModalOpen(false)}
              >
                <X className="h-4 w-4" />
              </Button>
              </div>

              <div className="mt-4">
                <div className="mb-4 grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm sm:grid-cols-2">
                  <div>
                    <p className="text-xs text-slate-500">目标团队</p>
                    <p className="mt-1 truncate font-medium text-slate-800">
                      {activeTeam?.name || "未识别团队"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">目标知识库</p>
                    <p className="mt-1 truncate font-medium text-slate-800">
                      {kb?.name || "当前知识库"}
                    </p>
                  </div>
                </div>
                <label className="mb-2 block text-sm font-medium text-slate-700">目标分类</label>
                <select
                  value={uploadCategoryId ?? ""}
                  onChange={(event) =>
                    setUploadCategoryId(event.target.value ? Number(event.target.value) : null)
                  }
                  className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-200"
                >
                  <option value="">未分类 / 按文件夹自动判断</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}（{category.document_count}）
                    </option>
                  ))}
                </select>
                <p className="mt-2 text-xs text-slate-500">
                  当前选择：{uploadCategory?.name || "未分类"}。
                </p>
              </div>

              <div
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                className={cn(
                  "mt-4 rounded-2xl border-2 border-dashed p-10 text-center transition-all",
                  dragOver
                    ? "border-blue-300 bg-blue-50/70"
                    : "border-slate-300 bg-slate-50 hover:border-slate-400",
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
                  <p className="mt-3 text-sm text-slate-700">拖拽文件到这里，或点击选择文件</p>
                    <p className="mt-1 text-xs text-slate-500">
                      支持 txt / md / pdf / docx，单文件最大 10MB，单次最多 {MAX_BATCH} 个文件
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
