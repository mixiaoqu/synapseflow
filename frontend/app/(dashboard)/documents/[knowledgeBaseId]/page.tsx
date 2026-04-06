"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChangeEvent, DragEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Eye,
  FileClock,
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

import { AnswerMarkdown } from "@/components/kb-chat/AnswerMarkdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
const MAX_BATCH = 100;
const PAGE_SIZE_OPTIONS = [20, 50, 100];

type StatusValue = "all" | DocumentIndexStatus;
type DetailTabValue = "preview" | "edit" | "versions";
type ConfirmDialogState = {
  open: boolean;
  title: string;
  description: string;
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
  return new Date(value).toLocaleString("zh-CN");
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
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
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
  const previewScrollRef = useRef<HTMLDivElement | null>(null);
  const previewArticleRef = useRef<HTMLElement | null>(null);

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
      router.push("/documents");
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
          router.push("/documents");
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

  useEffect(() => {
    if (!Number.isFinite(kbId) || kbId <= 0) return;

    let cancelled = false;

    const run = async () => {
      setLoadingDocs(true);

      try {
        const result = await listDocuments({
          page: docPage,
          page_size: docPageSize,
          keyword: keyword || undefined,
          knowledge_base_id: kbId,
          category_id: selectedCategoryId ?? undefined,
          team_id: teamId ?? undefined,
        });

        if (cancelled) return;

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
      } catch (error) {
        if (!cancelled) {
          toast.error(error instanceof Error ? error.message : "加载文档列表失败");
          setDocs([]);
          setDocsTotal(0);
        }
      } finally {
        if (!cancelled) setLoadingDocs(false);
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
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
      setReloadToken((value) => value + 1);
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [docs]);

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

  const reload = () => setReloadToken((value) => value + 1);

  const openDocumentsList = () => {
    requestDiscardDraft({
      title: "离开当前文档工作台？",
      description: "你还没有保存当前修改。现在返回知识库列表，会直接丢失这部分编辑内容。",
      confirmLabel: "放弃修改并返回",
      onConfirm: () => router.push("/documents"),
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

  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    if (searchInput.trim()) {
      searchTimeoutRef.current = setTimeout(() => {
        setKeyword(searchInput.trim());
        setDocPage(1);
      }, 500);
    } else if (keyword) {
      setKeyword("");
      setDocPage(1);
    }

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchInput, keyword]);

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
      confirmLabel: "确认删除",
      tone: "danger",
      onConfirm: async () => {
        setDeletingKnowledgeBase(true);
        try {
          await deleteKnowledgeBase(kb.id);
          toast.success("知识库已删除");
          router.push("/documents");
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

    const validFiles = Array.from(files).filter((file) => {
      const ext = "." + (file.name.split(".").pop()?.toLowerCase() || "");
      return SUPPORTED_EXTENSIONS.includes(ext) && file.size <= MAX_SIZE;
    }).slice(0, MAX_BATCH);

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

      if (files.length > MAX_BATCH) {
        toast.success(`已上传 ${validFiles.length} 个文件，超出部分已忽略，并加入索引队列`);
      } else {
        toast.success(`已上传 ${validFiles.length} 个文件，并加入索引队列`);
      }
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
    resetEditorState();
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
    <div className="flex min-h-full flex-col bg-gray-50 text-slate-900">
      <Toaster position="top-right" richColors />

      <header className="border-b border-slate-200 bg-white px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-[1700px] flex-wrap items-end justify-between gap-3">
          <div>
            <Button
              variant="outline"
              size="sm"
              className="mb-2 border-slate-200 text-slate-600"
              onClick={openDocumentsList}
            >
              <ArrowLeft className="mr-1 h-4 w-4" />
              返回
            </Button>
            <h1 className="text-2xl font-semibold">{kb?.name || "知识库工作台"}</h1>
            <p className="text-sm text-slate-500">
              {activeTeam ? `所属团队：${activeTeam.name}` : "正在识别所属团队..."} |{" "}
              {loadingMeta ? "正在同步知识库信息..." : `共 ${kb?.document_count ?? docsTotal} 篇文档`}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
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
              className="border-slate-200 text-slate-700"
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
              className="bg-blue-600 text-white hover:bg-blue-700"
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

      <main className="min-h-0 flex-1 p-4 sm:p-6">
        <section className="mx-auto h-full max-w-[1700px] min-h-0">

          <div
              className={cn(
                "grid min-h-0 items-start gap-4",
                selectedDocListItem
                  ? "xl:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.7fr)]"
                  : "xl:grid-cols-[minmax(0,1fr)]",
              )}
            >
              <section className="min-h-0 overflow-hidden rounded-2xl border border-slate-200 bg-white xl:flex xl:h-[calc(100vh-14rem)] xl:flex-col">
                <div className="border-b border-slate-200 bg-gradient-to-br from-slate-50 to-white px-4 py-3.5">
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="relative min-w-[200px] flex-1">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                        <Input
                          value={searchInput}
                          onChange={(e) => setSearchInput(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && onSearch()}
                          placeholder="搜索文档标题"
                          className="h-10 rounded-lg border-slate-200 bg-white pl-9 pr-3 text-sm shadow-sm placeholder:text-slate-400 focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                        />
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-10 rounded-lg border-slate-200 px-4 text-slate-700 hover:bg-slate-50"
                        onClick={onSearch}
                      >
                        搜索
                      </Button>
                      {(keyword || searchInput) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-10 rounded-lg px-3 text-slate-500 hover:bg-slate-100"
                          onClick={onClearSearch}
                        >
                          <X className="mr-1 h-3.5 w-3.5" />
                          清空
                        </Button>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <div className="flex-1 min-w-[140px]">
                        <select
                          value={status}
                          onChange={(e) => setStatus(e.target.value as StatusValue)}
                          className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-sm text-slate-700 shadow-sm outline-none transition-colors hover:border-slate-300 focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                        >
                          <option value="all">全部状态</option>
                          <option value="queued">排队中</option>
                          <option value="processing">索引中</option>
                          <option value="indexed">已索引</option>
                          <option value="failed">索引失败</option>
                        </select>
                      </div>

                      <div className="flex-1 min-w-[140px]">
                        <select
                          value={docType}
                          onChange={(e) => setDocType(e.target.value)}
                          className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-sm text-slate-700 shadow-sm outline-none transition-colors hover:border-slate-300 focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                        >
                          <option value="all">全部类型</option>
                          {typeOptions.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="flex-1 min-w-[160px]">
                        <select
                          value={selectedCategoryId ?? ""}
                          onChange={(e) => {
                            setSelectedCategoryId(e.target.value ? Number(e.target.value) : null);
                            setDocPage(1);
                          }}
                          className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-sm text-slate-700 shadow-sm outline-none transition-colors hover:border-slate-300 focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                        >
                          <option value="">全部分类</option>
                          {categories.map((category) => (
                            <option key={category.id} value={category.id}>
                              {category.name}（{category.document_count}）
                            </option>
                          ))}
                        </select>
                      </div>

                      {hasActiveFilters && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-9 rounded-lg px-3 text-slate-500 hover:bg-slate-100"
                          onClick={onResetFilters}
                        >
                          <RefreshCcw className="mr-1 h-3.5 w-3.5" />
                          重置
                        </Button>
                      )}
                    </div>

                    {hasActiveFilters && (
                      <div className="flex flex-wrap items-center gap-1.5">
                        {keyword && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-1 text-xs text-blue-700">
                            关键词: {keyword}
                          </span>
                        )}
                        {status !== "all" && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700">
                            {documentIndexMeta[status].label}
                          </span>
                        )}
                        {docType !== "all" && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700">
                            {docType}
                          </span>
                        )}
                        {activeCategory && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700">
                            {activeCategory.name}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/50 px-4 py-2.5">
                  <div className="flex items-center gap-3 text-xs">
                    {loadingDocs ? (
                      <span className="text-slate-500">正在加载文档...</span>
                    ) : docsTotal > 0 ? (
                      <>
                        <span className="font-medium text-slate-700">
                          {pageStart}-{pageEnd} / {docsTotal}
                        </span>
                        {hasActiveFilters && filteredDocs.length !== docsTotal && (
                          <span className="rounded-md bg-blue-100 px-2 py-0.5 text-blue-700">
                            筛选后 {filteredDocs.length} 篇
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="text-slate-500">暂无文档</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-600">
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

                {!selectedDocListItem ? (
                  <div className="border-b border-slate-100 bg-blue-50/70 px-4 py-2 text-xs text-blue-700">
                    点击任意文档后，右侧会展开阅读优先的工作台。
                  </div>
                ) : null}

                <div className="max-h-[65vh] overflow-auto p-3 xl:min-h-0 xl:flex-1">
                  {loadingMeta || loadingDocs ? (
                    <div className="flex flex-col items-center justify-center py-12 text-slate-500">
                      <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
                      <p className="mt-3 text-sm">正在加载文档列表...</p>
                    </div>
                  ) : docs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/50 py-12 text-center">
                      <div className="rounded-full bg-slate-100 p-3">
                        <UploadCloud className="h-6 w-6 text-slate-400" />
                      </div>
                      <p className="mt-3 text-sm font-medium text-slate-700">暂无文档</p>
                      <p className="mt-1 text-xs text-slate-500">点击右上角"上传文档"开始添加内容</p>
                    </div>
                  ) : filteredDocs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/50 py-12 text-center">
                      <div className="rounded-full bg-slate-100 p-3">
                        <Search className="h-6 w-6 text-slate-400" />
                      </div>
                      <p className="mt-3 text-sm font-medium text-slate-700">没有符合条件的文档</p>
                      <p className="mt-1 text-xs text-slate-500">尝试调整筛选条件或清空搜索</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {filteredDocs.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => onSelectDocument(item.id)}
                          className={cn(
                            "group w-full rounded-lg border p-3 text-left transition-all",
                            selectedDocId === item.id
                              ? "border-blue-300 bg-blue-50 shadow-sm"
                              : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm",
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <h4 className={cn(
                                "truncate text-sm font-medium transition-colors",
                                selectedDocId === item.id ? "text-blue-900" : "text-slate-900 group-hover:text-slate-950"
                              )}>
                                {item.title}
                              </h4>
                              <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
                                {item.category_name && (
                                  <span className="inline-flex items-center gap-1">
                                    <span className="h-1 w-1 rounded-full bg-slate-400"></span>
                                    {item.category_name}
                                  </span>
                                )}
                                <span>{item.document_type || "未知"}</span>
                                <span>{formatBytes(item.size)}</span>
                                <span>{formatDate(item.updated_at)}</span>
                              </div>
                            </div>
                            <span
                              className={cn(
                                "shrink-0 rounded-md px-2 py-1 text-xs font-medium",
                                item.index_status === "indexed"
                                  ? "bg-emerald-100 text-emerald-700"
                                  : item.index_status === "failed"
                                    ? "bg-rose-100 text-rose-700"
                                    : item.index_status === "processing"
                                      ? "bg-amber-100 text-amber-700"
                                      : "bg-slate-100 text-slate-600",
                              )}
                            >
                              {documentIndexMeta[item.index_status].label}
                            </span>
                          </div>
                          {item.index_error && (
                            <p className="mt-2 rounded-md bg-rose-50 px-2 py-1 text-xs text-rose-700">
                              {item.index_error}
                            </p>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-slate-50/30 px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-600">每页</span>
                    <select
                      value={docPageSize}
                      onChange={(e) => {
                        setDocPageSize(Number(e.target.value));
                        setDocPage(1);
                      }}
                      className="h-8 rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-700 outline-none transition-colors hover:border-slate-300 focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                    >
                      {PAGE_SIZE_OPTIONS.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <span className="text-xs text-slate-600">条</span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 w-8 border-slate-200 p-0"
                      disabled={docPage <= 1 || loadingDocs}
                      onClick={() => setDocPage(1)}
                      title="首页"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                      <ChevronLeft className="-ml-2.5 h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 w-8 border-slate-200 p-0"
                      disabled={docPage <= 1 || loadingDocs}
                      onClick={() => setDocPage((prev) => Math.max(1, prev - 1))}
                      title="上一页"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </Button>
                    <span className="min-w-[80px] text-center text-xs text-slate-600">
                      {docPage} / {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 w-8 border-slate-200 p-0"
                      disabled={docPage >= totalPages || loadingDocs}
                      onClick={() => setDocPage((prev) => Math.min(totalPages, prev + 1))}
                      title="下一页"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 w-8 border-slate-200 p-0"
                      disabled={docPage >= totalPages || loadingDocs}
                      onClick={() => setDocPage(totalPages)}
                      title="末页"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                      <ChevronRight className="-ml-2.5 h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </section>

              {selectedDocListItem ? (
                <aside className="min-h-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm xl:sticky xl:top-6 xl:flex xl:h-[calc(100vh-14rem)] xl:flex-col">
                  <Tabs
                    value={detailTab}
                    onValueChange={(value) => onDetailTabChange(value as DetailTabValue)}
                    className="flex min-h-0 flex-1 flex-col"
                  >
                    <div className="border-b border-slate-200 bg-white">
                      <div className="px-5 py-4">
                        {filteredDocs.length === 0 && (
                          <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                            当前筛选条件下没有匹配的文档，显示的是之前选中的文档
                          </div>
                        )}
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0 flex-1">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                              文档工作台
                            </p>
                            <h3 className="mt-1 line-clamp-2 text-xl font-semibold text-slate-900">
                              {selectedDocListItem.title}
                            </h3>
                            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-600">
                              <Badge
                                variant="outline"
                                className="border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                              >
                                {viewingVersionLabel}
                              </Badge>
                              <Badge
                                variant="outline"
                                className={cn("px-2 py-0.5 text-xs font-medium", retrievalStatus.className)}
                              >
                                {retrievalStatus.label}
                              </Badge>
                              {selectedDocSummary ? (
                                <p className="min-w-0 truncate text-sm text-slate-500">
                                  {selectedDocSummary}
                                </p>
                              ) : null}
                            </div>
                            {primaryWarning ? (
                              <div
                                className={cn(
                                  "mt-3 rounded-xl px-3.5 py-2.5 text-sm",
                                  primaryWarning.tone === "blue"
                                    ? "border border-blue-200 bg-blue-50 text-blue-800"
                                    : primaryWarning.tone === "rose"
                                      ? "border border-rose-200 bg-rose-50 text-rose-800"
                                      : primaryWarning.tone === "slate"
                                        ? "border border-slate-200 bg-slate-50 text-slate-800"
                                        : "border border-amber-200 bg-amber-50 text-amber-800",
                                )}
                              >
                                {primaryWarning.message}
                              </div>
                            ) : null}
                          </div>
                          <div className="flex shrink-0 items-start gap-2">
                            <DropdownMenu.Root>
                              <DropdownMenu.Trigger asChild>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  className="border-slate-200 text-slate-500 hover:text-slate-900"
                                  aria-label="更多操作"
                                >
                                  更多操作
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenu.Trigger>
                              <DropdownMenu.Portal>
                                <DropdownMenu.Content
                                  side="bottom"
                                  align="end"
                                  sideOffset={8}
                                  className="z-50 min-w-[168px] rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl"
                                >
                                  <DropdownMenu.Item
                                    onSelect={() => void onDeleteOne()}
                                    disabled={!selectedDocListItem || deletingOne}
                                    className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 outline-none transition-colors hover:bg-red-50 focus:bg-red-50 data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
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

                        <TabsList className="mt-4 grid h-10 w-full grid-cols-3 rounded-xl bg-slate-100 p-1">
                          <TabsTrigger value="preview" className="gap-1.5 rounded-lg">
                            <Eye className="h-3.5 w-3.5" />
                            预览
                          </TabsTrigger>
                          <TabsTrigger value="edit" className="gap-1.5 rounded-lg">
                            <PencilLine className="h-3.5 w-3.5" />
                            编辑
                          </TabsTrigger>
                          <TabsTrigger value="versions" className="gap-1.5 rounded-lg">
                            <FileClock className="h-3.5 w-3.5" />
                            版本
                          </TabsTrigger>
                        </TabsList>
                      </div>
                    </div>

                    <TabsContent
                      value="preview"
                      ref={previewScrollRef}
                      className="mt-0 min-h-0 flex-1 overflow-y-auto"
                    >
                      <div className="px-4 py-4 sm:px-5">
                        {activeDocLoading ? (
                          <div className="flex min-h-[320px] items-center justify-center text-sm text-slate-500">
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            正在加载正文...
                          </div>
                        ) : !activeDoc?.content ? (
                          <div className="flex min-h-[320px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 text-sm text-slate-500">
                            当前文档还没有可预览的正文内容。
                          </div>
                        ) : (
                          <div
                            className={cn(
                              "grid gap-4",
                              hasPreviewHeadings
                                ? "xl:grid-cols-[240px_minmax(0,1fr)]"
                                : "xl:grid-cols-[minmax(0,1fr)]",
                            )}
                          >
                            {hasPreviewHeadings ? (
                              <aside className="pr-1 xl:sticky xl:top-4 xl:self-start">
                                <div className="rounded-2xl border border-slate-200 bg-white p-3.5">
                                  <div className="flex items-center justify-between gap-2">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                                      文档目录
                                    </p>
                                    <button
                                      type="button"
                                      onClick={scrollPreviewToTop}
                                      className="text-xs text-slate-500 transition-colors hover:text-slate-900"
                                    >
                                      回到顶部
                                    </button>
                                  </div>
                                  <div className="mt-2.5 space-y-1">
                                    {previewHeadings.map((heading) => (
                                      <button
                                        key={heading.id}
                                        type="button"
                                        onClick={() => onSelectPreviewHeading(heading.id)}
                                        className={cn(
                                          "block w-full rounded-lg px-3 py-1.5 text-left text-sm transition-colors",
                                          heading.depth === 1 ? "font-medium" : "text-slate-600",
                                          heading.depth === 2 ? "pl-4" : "",
                                          heading.depth === 3 ? "pl-6 text-[13px]" : "",
                                          "text-slate-700 hover:bg-slate-50",
                                        )}
                                      >
                                        {heading.text}
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              </aside>
                            ) : null}

                            <article
                              ref={previewArticleRef}
                              className={cn(
                                "w-full rounded-2xl border border-slate-200 bg-white px-5 py-5",
                                hasPreviewHeadings ? "mx-auto max-w-4xl" : "max-w-none",
                              )}
                            >
                              {previewSupportsMarkdown ? (
                                <AnswerMarkdown text={activeDoc.content} />
                              ) : (
                                <pre className="whitespace-pre-wrap break-words font-sans text-[15px] leading-8 text-slate-700">
                                  {activeDoc.content}
                                </pre>
                              )}
                            </article>
                          </div>
                        )}
                      </div>
                    </TabsContent>

                    <TabsContent value="edit" className="mt-0 min-h-0 flex-1">
                      <div className="flex h-full min-h-0 flex-col bg-slate-50/50">
                        <div className="border-b border-slate-200 bg-white px-5 py-3">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="space-y-1">
                              <p className="text-sm font-medium text-slate-900">
                                {isViewingCurrentVersion
                                  ? `正在编辑当前版本 v${selectedDocVersion}`
                                  : `正在基于历史版本 v${selectedDocVersion} 编辑`}
                              </p>
                              <p className="text-xs text-slate-500">
                                {isEditorDirty
                                  ? "有未保存修改"
                                  : isViewingCurrentVersion
                                    ? "当前内容与所选当前版本一致"
                                    : "保存后会生成一个新的最新版本"}
                              </p>
                            </div>
                            <p className="max-w-md text-xs leading-5 text-slate-500">
                              {isViewingLatestVersion
                                ? "推荐优先保存为新版本，覆盖当前版本会直接修改最新稿。"
                                : isViewingCurrentVersion
                                  ? "当前生效版本不是最新稿，因此不支持直接覆盖，请保存为新版本。"
                                  : "历史版本不支持直接覆盖，请保存为新版本以保留版本链。"}
                            </p>
                          </div>
                        </div>

                        <div className="min-h-0 flex-1 p-4">
                          <Textarea
                            value={editorContent}
                            onChange={(e) => {
                              setEditorContent(e.target.value);
                              if (!editing) setEditing(true);
                            }}
                            className="h-full min-h-[420px] resize-none rounded-2xl border-slate-200 bg-white font-mono text-sm leading-7 shadow-sm"
                            placeholder="在这里编辑文档内容"
                          />
                        </div>
                      </div>
                    </TabsContent>

                    <TabsContent value="versions" className="mt-0 min-h-0 flex-1 overflow-y-auto">
                      <div className="grid gap-4 p-4 xl:grid-cols-[minmax(220px,0.6fr)_minmax(0,1.4fr)]">
                        <div className="rounded-xl border border-slate-200 bg-white shadow-sm xl:sticky xl:top-4 xl:self-start">
                          <div className="border-b border-slate-100 bg-slate-50/50 px-4 py-2.5">
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-medium text-slate-700">版本历史</span>
                              {versions.length > 0 && (
                                <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                                  {versions.length} 个版本
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="max-h-[500px] overflow-y-auto px-3 py-3">
                            {loadingVersions ? (
                              <div className="flex flex-col items-center py-8 text-slate-500">
                                <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                                <p className="mt-2 text-xs">加载中...</p>
                              </div>
                            ) : versions.length === 0 ? (
                              <div className="flex flex-col items-center py-8 text-center">
                                <div className="rounded-full bg-slate-100 p-2">
                                  <FileClock className="h-5 w-5 text-slate-400" />
                                </div>
                                <p className="mt-2 text-xs text-slate-600">暂无版本记录</p>
                              </div>
                            ) : (
                              <div className="space-y-2">
                                {versions.map((item) => (
                                  <button
                                    key={item.id}
                                    type="button"
                                    onClick={() => setSelectedVersionId(item.id)}
                                    className={cn(
                                      "group w-full rounded-lg border p-2.5 text-left transition-all",
                                      selectedVersionId === item.id
                                        ? "border-blue-300 bg-blue-50 shadow-sm"
                                        : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm",
                                    )}
                                  >
                                    <div className="flex items-center justify-between gap-2">
                                      <span className={cn(
                                        "text-sm font-semibold transition-colors",
                                        selectedVersionId === item.id ? "text-blue-900" : "text-slate-900"
                                      )}>
                                        v{item.version}
                                      </span>
                                      <div className="flex flex-wrap items-center justify-end gap-1">
                                        {item.is_current && (
                                          <span className="rounded-md bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
                                            当前
                                          </span>
                                        )}
                                        {item.is_latest && (
                                          <span className="rounded-md bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                                            最新
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                    <p className="mt-1.5 text-xs text-slate-500">
                                      {formatDateTime(item.created_at)}
                                    </p>
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
                          <div className="border-b border-slate-100 bg-slate-50/50 px-4 py-2.5">
                            <p className="text-sm font-medium text-slate-800">
                              {activeDoc
                                ? `版本 v${activeDoc.version}${
                                    isViewingCurrentVersion ? " · 当前版本" : ""
                                  }${isViewingLatestVersion ? " · 最新版本" : ""}`
                                : "版本预览"}
                            </p>
                            {activeDoc && (
                              <p className="mt-0.5 text-xs text-slate-500">
                                {formatDateTime(activeDoc.created_at)}
                              </p>
                            )}
                          </div>

                          <div className="px-5 py-5">
                            {activeDocLoading ? (
                              <div className="flex min-h-[320px] flex-col items-center justify-center text-slate-500">
                                <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
                                <p className="mt-3 text-sm">正在加载版本内容...</p>
                              </div>
                            ) : !activeDoc ? (
                              <div className="flex min-h-[320px] flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50/50 text-center">
                                <div className="rounded-full bg-slate-100 p-3">
                                  <Eye className="h-6 w-6 text-slate-400" />
                                </div>
                                <p className="mt-3 text-sm font-medium text-slate-700">选择版本查看内容</p>
                                <p className="mt-1 text-xs text-slate-500">点击左侧版本列表中的任意版本</p>
                              </div>
                            ) : (
                              <article className="mx-auto max-w-4xl rounded-xl border border-slate-200 bg-white px-6 py-6 shadow-sm">
                                {looksLikeMarkdown(activeDoc.document_type, activeDoc.content) ? (
                                  <AnswerMarkdown text={activeDoc.content} />
                                ) : (
                                  <pre className="whitespace-pre-wrap break-words font-sans text-[15px] leading-8 text-slate-700">
                                    {activeDoc.content || "暂时没有内容。"}
                                  </pre>
                                )}
                              </article>
                            )}
                          </div>
                        </div>
                      </div>
                    </TabsContent>

                    {detailTab === "preview" && isViewingCurrentVersion ? (
                      <div className="border-t border-slate-200 bg-white px-5 py-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <p
                            className={cn(
                              "text-xs",
                              selectedDocIndexStatus === "failed"
                                ? "text-rose-700"
                                : selectedDocIndexed
                                  ? "text-slate-500"
                                  : "text-amber-700",
                            )}
                          >
                            {selectedDocIndexStatus === "indexed"
                              ? "当前版本已建立索引，需要时仍可手动重新排队构建。"
                              : selectedDocIndexStatus === "processing"
                                ? "当前版本正在建立索引，完成前暂时不会参与知识库问答检索。"
                                : selectedDocIndexStatus === "queued"
                                  ? "当前版本已进入索引队列，完成前暂时不会参与知识库问答检索。"
                                  : selectedDocIndexStatus === "failed"
                                    ? `当前版本索引失败：${selectedDocIndexError || "请重新排队索引。"}`
                                    : "当前版本尚未建立索引，暂时不会参与知识库问答检索。"}
                          </p>
                          <Button
                            variant={selectedDocIndexed ? "outline" : "default"}
                            className={
                              selectedDocIndexed
                                ? "border-slate-200"
                                : selectedDocIndexStatus === "failed"
                                  ? "bg-rose-600 text-white hover:bg-rose-700"
                                  : "bg-amber-600 text-white hover:bg-amber-700"
                            }
                            onClick={() => void onReindexOne()}
                            disabled={!selectedDocListItem || indexingOne}
                          >
                            {indexingOne ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                              <RefreshCcw className="mr-2 h-4 w-4" />
                            )}
                            重新排队索引
                          </Button>
                        </div>
                      </div>
                    ) : null}

                    {detailTab === "edit" ? (
                      <div className="border-t border-slate-200 bg-white px-5 py-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="text-xs text-slate-500">
                            {isEditorDirty ? "存在未保存修改" : "当前没有本地修改"}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              variant="ghost"
                              className="text-slate-500"
                              onClick={onCancelEdit}
                              disabled={loadingDoc || (!editing && !isEditorDirty)}
                            >
                              取消修改
                            </Button>
                            <Button
                              variant="outline"
                              className="border-slate-200"
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
                              覆盖当前版本
                            </Button>
                            <Button
                              className="bg-blue-600 text-white hover:bg-blue-700"
                              onClick={() => void onSaveNewVersion()}
                              disabled={
                                loadingDoc || !selectedDoc || !isEditorDirty || savingNewVersion
                              }
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
                    ) : null}

                    {detailTab === "versions" ? (
                      <div className="border-t border-slate-200 bg-white px-5 py-4">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            className="bg-blue-600 text-white hover:bg-blue-700"
                            onClick={onEditFromVersion}
                            disabled={!activeDoc}
                          >
                            <PencilLine className="mr-2 h-4 w-4" />
                            基于该版本继续编辑
                          </Button>
                          <Button
                            variant="outline"
                            className="border-slate-200"
                            onClick={() => void onSwitchCurrentVersion()}
                            disabled={!selectedVersionId || isViewingCurrentVersion || switchingCurrentVersion}
                          >
                            {switchingCurrentVersion ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                              <FileClock className="mr-2 h-4 w-4" />
                            )}
                            {isViewingCurrentVersion ? "当前生效版本" : "切换为当前版本"}
                          </Button>
                          <Button
                            variant="outline"
                            className="border-slate-200"
                            onClick={() => setSelectedVersionId(latestVersion?.id ?? null)}
                            disabled={!latestVersion || selectedVersionId === latestVersion.id}
                          >
                            <Eye className="mr-2 h-4 w-4" />
                            查看最新版本
                          </Button>
                        </div>
                      </div>
                    ) : null}
                  </Tabs>
                </aside>
              ) : null}
            </div>
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
                    上传后的文件会自动归入当前知识库并加入索引队列；选择文件夹时会按第一层目录自动分类。
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
                  当前选择：{uploadCategory?.name || "未分类"}。如果上传文件夹，目录结构会优先用于自动建分类。
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
