"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChangeEvent, DragEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Database,
  FileText,
  Loader2,
  MoreHorizontal,
  Plus,
  Search,
  UploadCloud,
  X,
  type LucideIcon,
} from "lucide-react";
import { Toaster, toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  uploadDocument,
  uploadDocumentsBatch,
  type DocumentIndexStatus,
} from "@/lib/api/documents";
import {
  createKnowledgeBase,
  listKnowledgeBases,
  type KnowledgeBaseStatus,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import { listTeams, type Team } from "@/lib/api/teams";
import { cn } from "@/lib/utils";

const ACCEPT_FILES = ".txt,.md,.pdf,.docx";
const SUPPORTED_EXTENSIONS = new Set([".txt", ".md", ".pdf", ".docx"]);
const MAX_SIZE = 10 * 1024 * 1024;
const MAX_BATCH = 20;
const coverThemes = [
  "from-emerald-200/90 via-cyan-200/80 to-sky-300/70",
  "from-amber-200/90 via-orange-200/80 to-rose-300/70",
  "from-violet-200/90 via-indigo-200/80 to-cyan-300/70",
  "from-lime-200/90 via-emerald-200/80 to-teal-300/70",
  "from-pink-200/90 via-fuchsia-200/80 to-blue-300/70",
  "from-slate-200/90 via-zinc-200/80 to-stone-300/70",
];

const statusMeta: Record<
  KnowledgeBaseStatus,
  { label: string; icon: LucideIcon; chip: string; dot: string }
> = {
  available: {
    label: "可用",
    icon: CheckCircle2,
    chip: "border-emerald-200 bg-emerald-50 text-emerald-700",
    dot: "bg-emerald-500",
  },
  indexing: {
    label: "索引中",
    icon: Clock3,
    chip: "border-amber-200 bg-amber-50 text-amber-700",
    dot: "bg-amber-500",
  },
  error: {
    label: "有异常",
    icon: AlertTriangle,
    chip: "border-rose-200 bg-rose-50 text-rose-700",
    dot: "bg-rose-500",
  },
  empty: {
    label: "空库",
    icon: FileText,
    chip: "border-slate-200 bg-slate-100 text-slate-600",
    dot: "bg-slate-400",
  },
};

function formatDateTime(value?: string | null) {
  if (!value) return "暂无";
  return new Date(value).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

const documentIndexStatusMeta: Record<
  DocumentIndexStatus,
  { label: string; chip: string }
> = {
  queued: {
    label: "排队中",
    chip: "bg-slate-100 text-slate-700",
  },
  processing: {
    label: "索引中",
    chip: "bg-amber-50 text-amber-700",
  },
  indexed: {
    label: "已索引",
    chip: "bg-emerald-50 text-emerald-700",
  },
  failed: {
    label: "失败",
    chip: "bg-rose-50 text-rose-700",
  },
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
  const accepted = acceptedBeforeCap.slice(0, MAX_BATCH);
  return {
    accepted,
    invalidTypeCount,
    oversizeCount,
    overflowCount: Math.max(acceptedBeforeCap.length - accepted.length, 0),
  };
}

export default function DocumentsPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState<number | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingKnowledgeBases, setLoadingKnowledgeBases] = useState(false);
  const [creatingKnowledgeBase, setCreatingKnowledgeBase] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadCollectionId, setUploadCollectionId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const activeTeam = useMemo(
    () => teams.find((item) => item.id === selectedTeamId) ?? null,
    [selectedTeamId, teams],
  );
  const displayedKnowledgeBases = useMemo(() => {
    const q = keyword.trim().toLowerCase();
    if (!q) return knowledgeBases;
    return knowledgeBases.filter((item) =>
      [item.name, item.description || ""].some((value) => value.toLowerCase().includes(q)),
    );
  }, [keyword, knowledgeBases]);

  const loadTeams = useCallback(async () => {
    setLoadingTeams(true);
    try {
      const list = await listTeams();
      setTeams(list);
      setSelectedTeamId((prev) => prev ?? list[0]?.id ?? null);
    } catch {
      toast.error("加载团队失败");
    } finally {
      setLoadingTeams(false);
    }
  }, []);

  const loadKnowledgeBases = useCallback(async () => {
    if (selectedTeamId == null) {
      setKnowledgeBases([]);
      setSelectedKnowledgeBaseId(null);
      setUploadCollectionId(null);
      return;
    }
    setLoadingKnowledgeBases(true);
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
      toast.error("加载知识库失败");
      setKnowledgeBases([]);
      setSelectedKnowledgeBaseId(null);
      setUploadCollectionId(null);
    } finally {
      setLoadingKnowledgeBases(false);
    }
  }, [selectedTeamId]);

  useEffect(() => {
    void loadTeams();
  }, [loadTeams]);

  useEffect(() => {
    void loadKnowledgeBases();
  }, [loadKnowledgeBases]);

  useEffect(() => {
    if (!knowledgeBases.some((item) => item.status === "indexing")) return undefined;
    const timer = window.setTimeout(() => {
      void loadKnowledgeBases();
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [knowledgeBases, loadKnowledgeBases]);

  const openCreateModal = () => {
    if (selectedTeamId == null) return toast.error("请先选择团队");
    setCreateName("");
    setCreateDescription("");
    setCreateModalOpen(true);
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
    router.push(`/documents/${knowledgeBaseId}${query.toString() ? `?${query.toString()}` : ""}`);
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

  const uploadFiles = async (files: File[] | FileList | null) => {
    if (!files || files.length === 0) return;
    const { accepted, invalidTypeCount, oversizeCount, overflowCount } = validateFiles(files);
    if (accepted.length === 0) return toast.error("没有符合要求的文件，请检查格式或大小限制");

    setUploading(true);
    try {
      const knowledgeBaseId =
        uploadCollectionId && uploadCollectionId > 0 ? uploadCollectionId : undefined;
      if (accepted.length === 1) await uploadDocument(accepted[0], knowledgeBaseId);
      else await uploadDocumentsBatch(accepted, knowledgeBaseId);

      const notes: string[] = [];
      if (invalidTypeCount > 0) notes.push(`${invalidTypeCount} 个格式不支持`);
      if (oversizeCount > 0) notes.push(`${oversizeCount} 个超过 10MB`);
      if (overflowCount > 0) notes.push(`${overflowCount} 个超出单次 20 个文件上限`);
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

  const isLoading = loadingTeams || loadingKnowledgeBases;
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

          {teams.length > 1 ? (
            <div className="mt-5 flex flex-wrap items-center gap-2">
              {teams.map((team) => (
                <button
                  key={team.id}
                  type="button"
                  onClick={() => setSelectedTeamId(team.id)}
                  className={cn(
                    "rounded-full border px-3.5 py-1.5 text-sm transition-colors",
                    selectedTeamId === team.id
                      ? "border-blue-200 bg-blue-50 text-blue-700"
                      : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50",
                  )}
                >
                  {team.name}
                </button>
              ))}
            </div>
          ) : null}

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
              {displayedKnowledgeBases.map((knowledgeBase, index) => {
                const active = selectedKnowledgeBaseId === knowledgeBase.id;
                const theme = coverThemes[(knowledgeBase.id + index) % coverThemes.length];
                const meta = statusMeta[knowledgeBase.status];
                const StatusIcon = meta.icon;
                return (
                  <div
                    key={knowledgeBase.id}
                    className={cn(
                      "overflow-hidden rounded-2xl border bg-white p-5 shadow-sm transition-all",
                      active
                        ? "border-blue-200 ring-2 ring-blue-100"
                        : "border-slate-200 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => setSelectedKnowledgeBaseId(knowledgeBase.id)}
                      className="block w-full text-left"
                    >
                      <div className={cn("rounded-2xl bg-gradient-to-br p-4", theme)}>
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <span className="inline-flex rounded-md bg-white/70 px-2 py-1 text-xs font-medium text-slate-700">知识库</span>
                            <h3 className="mt-4 line-clamp-2 text-xl font-semibold text-slate-900">{knowledgeBase.name}</h3>
                          </div>
                          <div className={cn("inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium", meta.chip)}>
                            <span className={cn("h-2 w-2 rounded-full", meta.dot)} />
                            <StatusIcon className="h-3.5 w-3.5" />
                            {meta.label}
                          </div>
                        </div>
                      </div>

                      <p className="mt-4 line-clamp-2 min-h-[48px] text-sm leading-6 text-slate-500">
                        {knowledgeBase.description || "围绕单个主题集中组织文档、检索与问答。"}
                      </p>
                    </button>

                    <div className="mt-4 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-xl border border-slate-200 bg-white/80 p-3">
                          <p className="text-xs text-slate-400">文档总数</p>
                          <p className="mt-2 text-lg font-semibold text-slate-900">{knowledgeBase.document_count}</p>
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-white/80 p-3">
                          <p className="text-xs text-slate-400">已索引 / 处理中 / 失败</p>
                          <p className="mt-2 text-lg font-semibold text-slate-900">
                            {knowledgeBase.indexed_document_count} /{" "}
                            {knowledgeBase.queued_document_count + knowledgeBase.processing_document_count} /{" "}
                            {knowledgeBase.failed_document_count}
                          </p>
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-white/80 p-3">
                          <p className="text-xs text-slate-400">最近更新时间</p>
                          <p className="mt-2 text-sm font-medium text-slate-700">
                            {formatDateTime(knowledgeBase.last_document_updated_at || knowledgeBase.updated_at)}
                          </p>
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-white/80 p-3">
                          <p className="text-xs text-slate-400">最近上传时间</p>
                          <p className="mt-2 text-sm font-medium text-slate-700">
                            {formatDateTime(knowledgeBase.last_uploaded_at)}
                          </p>
                        </div>
                      </div>

                      <div className="mt-4 border-t border-slate-200 pt-4">
                        <div className="mb-3 flex items-center justify-between text-xs text-slate-400">
                          <span>最近 3 篇文档</span>
                          <span>{knowledgeBase.document_count} 篇文档</span>
                        </div>
                        {knowledgeBase.recent_documents.length > 0 ? (
                          <div className="space-y-2">
                            {knowledgeBase.recent_documents.map((item) => {
                              const indexMeta = documentIndexStatusMeta[item.index_status];
                              return (
                                <div key={item.id} className="rounded-xl border border-slate-200 bg-white px-3 py-2.5">
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="min-w-0">
                                      <p className="truncate text-sm font-medium text-slate-800">{item.title}</p>
                                      <p className="mt-1 text-xs text-slate-400">上传于 {formatDateTime(item.created_at)}</p>
                                    </div>
                                    <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium", indexMeta.chip)}>
                                      {indexMeta.label}
                                    </span>
                                  </div>
                                  <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                                    <span>{item.document_type || "未知类型"}</span>
                                    <span>{formatBytes(item.size)}</span>
                                  </div>
                                  {item.index_error ? (
                                    <p className="mt-2 text-xs text-rose-600">{item.index_error}</p>
                                  ) : null}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="flex items-center justify-center rounded-xl border border-dashed border-slate-200 bg-white/80 px-3 py-8 text-center text-sm text-slate-400">
                            当前知识库还没有文档，先上传几篇材料就能开始使用。
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="mt-4 flex items-center gap-2 border-t border-slate-200 pt-3">
                      <Button variant="outline" className="flex-1 rounded-xl border-slate-200" onClick={() => {
                        setSelectedKnowledgeBaseId(knowledgeBase.id);
                        openKnowledgeBase(knowledgeBase.id);
                      }}>
                        进入工作台
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Button>
                      <Button variant="outline" className="flex-1 rounded-xl border-slate-200" onClick={() => {
                        setSelectedKnowledgeBaseId(knowledgeBase.id);
                        openUploadModal(knowledgeBase.id);
                      }}>
                        <UploadCloud className="mr-2 h-4 w-4" />
                        上传文档
                      </Button>
                      <DropdownMenu.Root>
                        <DropdownMenu.Trigger asChild>
                          <Button variant="outline" size="icon" className="rounded-xl border-slate-200 px-0" aria-label="更多操作">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenu.Trigger>
                        <DropdownMenu.Portal>
                          <DropdownMenu.Content side="bottom" align="end" sideOffset={8} className="z-50 min-w-[160px] rounded-xl border border-slate-200 bg-white p-1.5 text-sm shadow-xl">
                            <DropdownMenu.Item onSelect={() => openKnowledgeBase(knowledgeBase.id)} className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2 text-slate-700 outline-none transition-colors hover:bg-slate-100 focus:bg-slate-100">
                              <ArrowRight className="h-4 w-4" />
                              进入工作台
                            </DropdownMenu.Item>
                            <DropdownMenu.Item onSelect={() => openUploadModal(knowledgeBase.id)} className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2 text-slate-700 outline-none transition-colors hover:bg-slate-100 focus:bg-slate-100">
                              <UploadCloud className="h-4 w-4" />
                              上传文档
                            </DropdownMenu.Item>
                            <DropdownMenu.Item onSelect={() => void navigator.clipboard.writeText(String(knowledgeBase.id)).then(() => toast.success("知识库 ID 已复制")).catch(() => toast.error("复制失败"))} className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-3 py-2 text-slate-700 outline-none transition-colors hover:bg-slate-100 focus:bg-slate-100">
                              <FileText className="h-4 w-4" />
                              复制知识库 ID
                            </DropdownMenu.Item>
                          </DropdownMenu.Content>
                        </DropdownMenu.Portal>
                      </DropdownMenu.Root>
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
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  为当前团队创建一个新的知识库，后续可以继续上传文档并进入详细工作区。
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
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-all",
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
                      支持 txt / md / pdf / docx，单文件最大 10MB，单次最多 20 个文件
                    </p>
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
