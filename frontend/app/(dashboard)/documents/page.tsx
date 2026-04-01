"use client";

import {
  ChangeEvent,
  DragEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Database,
  Loader2,
  Plus,
  Search,
  UploadCloud,
  X,
} from "lucide-react";
import { Toaster, toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  listDocuments,
  uploadDocument,
  uploadDocumentsBatch,
  type DocumentListItem,
} from "@/lib/api/documents";
import {
  createKnowledgeBase,
  listKnowledgeBases,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import { listTeams, type Team } from "@/lib/api/teams";

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

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("zh-CN");
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

type FileValidation = {
  accepted: File[];
  invalidTypeCount: number;
  oversizeCount: number;
  overflowCount: number;
};

function validateFiles(files: File[] | FileList): FileValidation {
  const allFiles = Array.from(files);
  const acceptedBeforeCap: File[] = [];
  let invalidTypeCount = 0;
  let oversizeCount = 0;

  for (const file of allFiles) {
    const extension = "." + (file.name.split(".").pop()?.toLowerCase() || "");
    if (!SUPPORTED_EXTENSIONS.has(extension)) {
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
  const overflowCount = Math.max(acceptedBeforeCap.length - accepted.length, 0);

  return {
    accepted,
    invalidTypeCount,
    oversizeCount,
    overflowCount,
  };
}

export default function DocumentsPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState<number | null>(null);
  const [docs, setDocs] = useState<DocumentListItem[]>([]);

  const [searchInput, setSearchInput] = useState("");
  const [keyword, setKeyword] = useState("");

  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingKnowledgeBases, setLoadingKnowledgeBases] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(false);
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

    return knowledgeBases.filter((item) => {
      const name = item.name.toLowerCase();
      const description = (item.description || "").toLowerCase();
      return name.includes(q) || description.includes(q);
    });
  }, [keyword, knowledgeBases]);

  const previewMap = useMemo(() => {
    const map = new Map<number, DocumentListItem[]>();
    docs.forEach((item) => {
      if (!item.knowledge_base_id) return;
      const list = map.get(item.knowledge_base_id) ?? [];
      if (list.length < 4) list.push(item);
      map.set(item.knowledge_base_id, list);
    });
    return map;
  }, [docs]);

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

  const loadDocumentsPreview = useCallback(async () => {
    if (selectedTeamId == null) {
      setDocs([]);
      return;
    }

    setLoadingDocs(true);
    try {
      const response = await listDocuments({
        page: 1,
        page_size: 100,
        team_id: selectedTeamId,
      });
      setDocs(response.items);
    } catch {
      toast.error("加载文档预览失败");
      setDocs([]);
    } finally {
      setLoadingDocs(false);
    }
  }, [selectedTeamId]);

  useEffect(() => {
    void loadTeams();
  }, [loadTeams]);

  useEffect(() => {
    void loadKnowledgeBases();
    void loadDocumentsPreview();
  }, [loadDocumentsPreview, loadKnowledgeBases]);

  const handleSearch = () => {
    setKeyword(searchInput.trim());
  };

  const clearSearch = () => {
    setSearchInput("");
    setKeyword("");
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

  const handleCreateKnowledgeBase = async () => {
    const name = createName.trim();
    const description = createDescription.trim();
    if (!name || selectedTeamId == null) return;

    setCreatingKnowledgeBase(true);
    try {
      const created = await createKnowledgeBase(name, selectedTeamId, description || undefined);
      toast.success("知识库已创建");
      setCreateModalOpen(false);
      setCreateName("");
      setCreateDescription("");
      await loadKnowledgeBases();
      setSelectedKnowledgeBaseId(created.id);
      setUploadCollectionId(created.id);
    } catch (error: unknown) {
      toast.error((error as { message?: string }).message || "创建知识库失败");
    } finally {
      setCreatingKnowledgeBase(false);
    }
  };

  const openUploadModal = (knowledgeBaseId?: number) => {
    const targetId = knowledgeBaseId ?? selectedKnowledgeBaseId ?? knowledgeBases[0]?.id ?? null;
    if (!targetId) {
      toast.error("请先创建知识库，再上传文档");
      return;
    }

    setUploadCollectionId(targetId);
    setDragOver(false);
    setUploadModalOpen(true);
  };

  const uploadFiles = async (files: File[] | FileList | null) => {
    if (!files || files.length === 0) return;

    const { accepted, invalidTypeCount, oversizeCount, overflowCount } = validateFiles(files);

    if (accepted.length === 0) {
      toast.error("没有符合要求的文件，请检查格式或大小限制");
      return;
    }

    setUploading(true);
    try {
      const knowledgeBaseId =
        uploadCollectionId && uploadCollectionId > 0 ? uploadCollectionId : undefined;

      if (accepted.length === 1) {
        await uploadDocument(accepted[0], knowledgeBaseId);
      } else {
        await uploadDocumentsBatch(accepted, knowledgeBaseId);
      }

      const notes: string[] = [];
      if (invalidTypeCount > 0) notes.push(`${invalidTypeCount} 个格式不支持`);
      if (oversizeCount > 0) notes.push(`${oversizeCount} 个超过 10MB`);
      if (overflowCount > 0) notes.push(`${overflowCount} 个超出单次 20 个文件上限`);

      if (notes.length > 0) {
        toast.success(`已上传 ${accepted.length} 个文件，${notes.join("，")}`);
      } else {
        toast.success(`已成功上传 ${accepted.length} 个文件`);
      }

      setUploadModalOpen(false);
      await loadDocumentsPreview();
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

  const openKnowledgeBase = (knowledgeBaseId: number) => {
    const query = new URLSearchParams();
    if (selectedTeamId != null) {
      query.set("teamId", String(selectedTeamId));
    }
    const suffix = query.toString();
    router.push(`/documents/${knowledgeBaseId}${suffix ? `?${suffix}` : ""}`);
  };

  const isLoading = loadingTeams || loadingKnowledgeBases || loadingDocs;
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
                  onKeyDown={(event) => event.key === "Enter" && handleSearch()}
                  placeholder="搜索知识库名称或描述"
                  className="h-11 rounded-xl border-slate-200 bg-white pl-10 text-slate-800 placeholder:text-slate-400"
                />
              </div>
              <Button
                variant="outline"
                onClick={handleSearch}
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
            <span>
              {isLoading ? "正在同步团队与知识库内容..." : `共找到 ${displayedKnowledgeBases.length} 个知识库`}
            </span>
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
                  ? "可以试试更换关键词，或者直接新建一个知识库。"
                  : "先创建一个知识库，再上传文档、建立索引并进入详细工作区。"}
              </p>
              <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                <Button
                  onClick={openCreateModal}
                  className="rounded-xl bg-blue-600 text-white hover:bg-blue-700"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  新建知识库
                </Button>
                {keyword ? (
                  <Button
                    variant="outline"
                    className="rounded-xl border-slate-200"
                    onClick={clearSearch}
                  >
                    清空搜索
                  </Button>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {displayedKnowledgeBases.map((knowledgeBase, index) => {
                const previews = previewMap.get(knowledgeBase.id) ?? [];
                const isActive = selectedKnowledgeBaseId === knowledgeBase.id;
                const coverTheme = coverThemes[(knowledgeBase.id + index) % coverThemes.length];

                return (
                  <div
                    key={knowledgeBase.id}
                    className={cn(
                      "group overflow-hidden rounded-2xl border bg-white p-5 shadow-sm transition-all",
                      isActive
                        ? "border-blue-200 ring-2 ring-blue-100"
                        : "border-slate-200 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => setSelectedKnowledgeBaseId(knowledgeBase.id)}
                      className="block w-full text-left"
                    >
                      <div className={cn("h-28 rounded-xl bg-gradient-to-br p-4", coverTheme)}>
                        <div className="flex items-center justify-between">
                          <span className="rounded-md bg-white/70 px-2 py-1 text-xs font-medium text-slate-700">
                            知识库
                          </span>
                          <Database className="h-4 w-4 text-slate-700/70" />
                        </div>
                      </div>

                      <div className="mt-4">
                        <div className="flex items-start justify-between gap-3">
                          <h3 className="line-clamp-1 text-xl font-medium text-slate-900">
                            {knowledgeBase.name}
                          </h3>
                          <span className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-500">
                            {knowledgeBase.document_count} 篇
                          </span>
                        </div>
                        <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-500">
                          {knowledgeBase.description || "围绕单个主题集中组织文档、检索与问答。"}
                        </p>
                      </div>
                    </button>

                    <div className="mt-4 flex h-[170px] flex-col rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200">
                      <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
                        <span>最近文档预览</span>
                        <span>{formatDate(knowledgeBase.updated_at)}</span>
                      </div>

                      {previews.length > 0 ? (
                        <div className="flex-1 space-y-1 overflow-y-auto pr-1">
                          {previews.map((item) => (
                            <div
                              key={item.id}
                              className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm"
                            >
                              <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                              <span className="min-w-0 flex-1 truncate text-slate-700">
                                {item.title}
                              </span>
                              <span className="shrink-0 text-xs text-slate-400">
                                {formatBytes(item.size)}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white/70 px-3 py-5 text-center text-sm text-slate-400">
                          当前知识库还没有文档，先上传几篇材料就能开始使用。
                        </div>
                      )}
                    </div>

                    <div className="mt-4 flex items-center gap-2 border-t border-slate-200 pt-3">
                      <Button
                        variant="outline"
                        className="flex-1 rounded-xl border-slate-200"
                        onClick={() => {
                          setSelectedKnowledgeBaseId(knowledgeBase.id);
                          openUploadModal(knowledgeBase.id);
                        }}
                      >
                        <UploadCloud className="mr-2 h-4 w-4" />
                        上传到此库
                      </Button>
                      <Button
                        className="flex-1 rounded-xl bg-slate-900 text-white hover:bg-slate-800"
                        onClick={() => {
                          setSelectedKnowledgeBaseId(knowledgeBase.id);
                          openKnowledgeBase(knowledgeBase.id);
                        }}
                      >
                        进入工作区
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Button>
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
                  选择目标知识库后上传，系统会自动提取文本并建立索引。
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
                    正在上传并建立索引...
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
