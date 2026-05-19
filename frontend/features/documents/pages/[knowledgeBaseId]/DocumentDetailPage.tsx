"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock3,
  Edit3,
  FileText,
  Folder,
  Globe2,
  Loader2,
  RefreshCcw,
  Send,
  Trash2,
  X,
} from "lucide-react";
import { Toaster, toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  createDocumentVersion,
  deleteDocument,
  getDocument,
  indexDocument,
  publishDocument,
  replaceDocumentContent,
  submitDocumentForReview,
  unpublishDocument,
  type DocumentDetail,
  type DocumentIndexStatus,
  type DocumentLifecycleStatus,
} from "@/lib/api/documents";
import { cn } from "@/lib/utils";

type ConfirmDialogState = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  tone: "primary" | "danger";
  onConfirm: null | (() => void | Promise<void>);
};

const indexStatusMeta: Record<DocumentIndexStatus, { label: string; className: string }> = {
  queued: {
    label: "排队中",
    className: "border-slate-200 bg-slate-50 text-slate-700",
  },
  processing: {
    label: "索引中",
    className: "border-amber-200 bg-amber-50 text-amber-700",
  },
  indexed: {
    label: "索引已完成",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  failed: {
    label: "索引失败",
    className: "border-rose-200 bg-rose-50 text-rose-700",
  },
};

const lifecycleStatusMeta: Record<DocumentLifecycleStatus, { label: string; className: string }> = {
  draft: {
    label: "草稿",
    className: "border-slate-200 bg-slate-50 text-slate-700",
  },
  pending_review: {
    label: "待审核",
    className: "border-orange-200 bg-orange-50 text-orange-700",
  },
  published: {
    label: "已发布",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  archived: {
    label: "已下线",
    className: "border-slate-200 bg-slate-100 text-slate-600",
  },
};

function formatDateTime(value?: string | null) {
  if (!value) return "暂无记录";
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatFileSize(size?: number | null) {
  if (!size || size <= 0) return "-";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function buildListUrl(
  knowledgeBaseId: number,
  query: Pick<URLSearchParams, "get">,
  documentId: number,
) {
  const next = new URLSearchParams();
  for (const key of ["teamId", "categoryId"]) {
    const value = query.get(key);
    if (value) next.set(key, value);
  }
  next.set("documentId", String(documentId));
  return `/admin/documents/${knowledgeBaseId}${next.toString() ? `?${next.toString()}` : ""}`;
}

function StatusPill({
  label,
  className,
}: {
  label: string;
  className: string;
}) {
  return (
    <span className={cn("inline-flex rounded-full border px-2.5 py-1 text-xs font-medium", className)}>
      {label}
    </span>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-slate-800" title={value}>
        {value}
      </p>
    </div>
  );
}

export default function DocumentDetailPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-500">
          <Loader2 className="h-6 w-6 animate-spin" />
        </main>
      }
    >
      <DocumentDetailPageContent />
    </Suspense>
  );
}

function DocumentDetailPageContent() {
  const params = useParams<{ knowledgeBaseId: string; documentId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();

  const knowledgeBaseId = Number(params.knowledgeBaseId);
  const documentId = Number(params.documentId);

  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionKey, setActionKey] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [draftContent, setDraftContent] = useState("");
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState>({
    open: false,
    title: "",
    description: "",
    confirmLabel: "确认",
    tone: "primary",
    onConfirm: null,
  });

  const listUrl = useMemo(
    () =>
      Number.isFinite(knowledgeBaseId) && knowledgeBaseId > 0
        ? buildListUrl(knowledgeBaseId, searchParams, documentId)
        : "/admin/documents",
    [documentId, knowledgeBaseId, searchParams],
  );

  const loadDocument = useCallback(async () => {
    if (!Number.isFinite(documentId) || documentId <= 0) return;
    setLoading(true);
    try {
      const data = await getDocument(documentId);
      setDocument(data);
      setDraftContent(data.content || "");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载文档详情失败");
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    if (
      !Number.isFinite(knowledgeBaseId) ||
      knowledgeBaseId <= 0 ||
      !Number.isFinite(documentId) ||
      documentId <= 0
    ) {
      toast.error("文档地址无效");
      router.push("/admin/documents");
      return;
    }
    void loadDocument();
  }, [documentId, knowledgeBaseId, loadDocument, router]);

  const openConfirmDialog = (options: Omit<ConfirmDialogState, "open">) => {
    setConfirmDialog({ open: true, ...options });
  };

  const closeConfirmDialog = () => {
    setConfirmDialog((prev) => ({ ...prev, open: false, onConfirm: null }));
  };

  const runConfirmedAction = () => {
    const action = confirmDialog.onConfirm;
    closeConfirmDialog();
    if (!action) return;
    void Promise.resolve(action());
  };

  const runAction = async (
    key: string,
    action: () => Promise<DocumentDetail | { message?: string } | void>,
    successMessage: string,
  ) => {
    setActionKey(key);
    try {
      await action();
      toast.success(successMessage);
      await loadDocument();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "操作失败");
    } finally {
      setActionKey(null);
    }
  };

  const handleDelete = () => {
    if (!document) return;
    openConfirmDialog({
      title: "删除文档",
      description: `确认删除《${document.title}》吗？删除后不可恢复。`,
      confirmLabel: "确认删除",
      tone: "danger",
      onConfirm: async () => {
        setActionKey("delete");
        try {
          await deleteDocument(document.id);
          toast.success("文档已删除");
          router.push(listUrl);
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "删除失败");
          setActionKey(null);
        }
      },
    });
  };

  const handleSaveContent = (mode: "replace" | "version") => {
    if (!document) return;
    const content = draftContent.trim();
    if (!content) {
      toast.error("正文内容不能为空");
      return;
    }
    const action =
      mode === "replace"
        ? () => replaceDocumentContent(document.id, content)
        : () => createDocumentVersion(document.id, content);
    const successMessage = mode === "replace" ? "正文已保存并重新索引" : "已保存为新版本";

    void runAction(`save-${mode}`, async () => {
      await action();
      setEditorOpen(false);
    }, successMessage);
  };

  if (loading && !document) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        正在加载文档详情...
      </main>
    );
  }

  if (!document) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-500">
        未找到文档
      </main>
    );
  }

  const indexMeta = indexStatusMeta[document.index_status];
  const lifecycleMeta = lifecycleStatusMeta[document.status];
  const isEffective = document.index_status === "indexed" && document.status === "published" && document.is_live;
  const canSubmit = document.index_status === "indexed" && document.status === "draft" && document.is_current;
  const canPublish = document.index_status === "indexed" && document.status === "pending_review" && document.is_current;
  const canUnpublish = document.status === "published" && document.is_live;
  const canReplaceContent = !(document.status === "published" && document.is_live);
  const contentText = document.content?.trim();

  return (
    <div className="bg-slate-50">
      <Toaster position="top-right" />

      <main className="flex h-[calc(100vh-64px)] min-h-0 flex-col overflow-hidden">
        <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6">
          <div className="min-w-0">
            <Button
              variant="ghost"
              className="mb-1 h-8 rounded-full px-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              onClick={() => router.push(listUrl)}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回文档列表
            </Button>
            <div className="flex min-w-0 items-center gap-2">
              <FileText className="h-4 w-4 shrink-0 text-slate-400" />
              <h1 className="truncate text-lg font-semibold text-slate-900">{document.title}</h1>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <Button variant="outline" className="rounded-full border-slate-200" onClick={() => void loadDocument()}>
              <RefreshCcw className="mr-2 h-4 w-4" />
              刷新
            </Button>
            <Button
              className="rounded-full bg-slate-900 text-white hover:bg-slate-800"
              onClick={() => setEditorOpen(true)}
            >
              <Edit3 className="mr-2 h-4 w-4" />
              编辑正文
            </Button>
          </div>
        </header>

        <section className="flex min-h-0 flex-1 gap-6 overflow-auto px-6 py-6">
          <section className="flex min-w-0 flex-[1.45] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-5 py-4">
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <FileText className="h-4 w-4 text-blue-500" />
                  文档正文内容
                </p>
                <p className="mt-1 text-xs text-slate-500">展示系统当前用于知识库索引的文本内容</p>
              </div>
              <StatusPill label={indexMeta.label} className={indexMeta.className} />
            </div>

            <div className="min-h-0 flex-1 overflow-auto bg-slate-50/70 px-5 py-6">
              {document.index_status === "failed" ? (
                <div className="mx-auto flex min-h-full max-w-xl flex-col items-center justify-center text-center">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-rose-50 text-rose-500">
                    <AlertTriangle className="h-8 w-8" />
                  </div>
                  <h2 className="text-lg font-semibold text-slate-900">文档索引失败</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    当前文档暂时无法被问答使用。请查看失败原因，处理文件后重新索引。
                  </p>
                  <div className="mt-5 w-full rounded-2xl border border-rose-100 bg-white p-4 text-left text-sm text-slate-600">
                    <p className="font-medium text-slate-900">失败原因</p>
                    <p className="mt-2 leading-6">{document.index_error || "暂无详细原因，请尝试重新索引或重新上传文件。"}</p>
                  </div>
                  <Button
                    className="mt-5 rounded-full bg-slate-900 text-white hover:bg-slate-800"
                    disabled={actionKey === "reindex"}
                    onClick={() => void runAction("reindex", () => indexDocument(document.id), "已提交重新索引任务")}
                  >
                    {actionKey === "reindex" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCcw className="mr-2 h-4 w-4" />}
                    重新索引
                  </Button>
                </div>
              ) : document.index_status === "processing" || document.index_status === "queued" ? (
                <div className="mx-auto flex min-h-full max-w-xl flex-col items-center justify-center text-center">
                  <Loader2 className="mb-4 h-10 w-10 animate-spin text-amber-500" />
                  <h2 className="text-lg font-semibold text-slate-900">正在处理文档内容</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    系统正在提取文本并建立索引。完成后，这里会展示可用于问答的正文内容。
                  </p>
                </div>
              ) : (
                <article className="mx-auto min-h-full w-full max-w-3xl rounded-2xl border border-slate-200 bg-white px-8 py-8 shadow-sm">
                  <h2 className="break-words text-center text-2xl font-semibold text-slate-900">
                    {document.title.replace(/\.[^/.]+$/, "")}
                  </h2>
                  {contentText ? (
                    <div className="mt-8 whitespace-pre-wrap break-words text-sm leading-7 text-slate-700">
                      {contentText}
                    </div>
                  ) : (
                    <p className="mt-8 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                      该文档索引已完成，但没有可展示的正文内容。
                    </p>
                  )}
                </article>
              )}
            </div>
          </section>

          <aside className="flex min-w-[360px] flex-[0.85] flex-col gap-5">
            <section className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <Globe2 className="h-4 w-4 text-blue-500" />
                服务生效状态
              </p>
              <div
                className={cn(
                  "mt-4 flex items-start gap-3 rounded-2xl border p-4",
                  isEffective
                    ? "border-emerald-100 bg-emerald-50 text-emerald-800"
                    : "border-amber-100 bg-amber-50 text-amber-800",
                )}
              >
                {isEffective ? (
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                ) : (
                  <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
                )}
                <div>
                  <p className="font-semibold">
                    {isEffective ? "正在生效，可被用户问答使用" : "暂不可用，用户问答暂时不会使用"}
                  </p>
                  <p className="mt-1 text-xs leading-5">
                    {isEffective
                      ? "文档已完成索引并处于已发布状态，绑定该版本的应用可以命中这份内容。"
                      : "需要同时满足索引已完成、用户可见状态为已发布，并且处于生效版本。"}
                  </p>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 rounded-2xl border border-slate-100 bg-slate-50 p-4">
                <div>
                  <p className="mb-2 text-xs text-slate-500">索引状态</p>
                  <StatusPill label={indexMeta.label} className={indexMeta.className} />
                </div>
                <div>
                  <p className="mb-2 text-xs text-slate-500">用户可见状态</p>
                  <StatusPill label={lifecycleMeta.label} className={lifecycleMeta.className} />
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-sm font-semibold text-slate-900">文档基础信息</p>
              <div className="mt-4 grid gap-4">
                <div>
                  <p className="text-xs text-slate-500">所属知识库</p>
                  <p className="mt-1 flex min-w-0 items-center gap-2 text-sm font-medium text-slate-800">
                    <Globe2 className="h-4 w-4 shrink-0 text-slate-400" />
                    <span className="truncate">知识库 #{document.knowledge_base_id ?? knowledgeBaseId}</span>
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">所属分类</p>
                  <p className="mt-1 flex min-w-0 items-center gap-2 text-sm font-medium text-slate-800">
                    <Folder className="h-4 w-4 shrink-0 text-slate-400" />
                    <span className="truncate">{document.category_name || "未分类"}</span>
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <InfoRow label="文件大小" value={formatFileSize(document.size)} />
                  <InfoRow label="文档版本" value={`v${document.version}${document.is_current ? " · 当前版本" : ""}`} />
                  <InfoRow label="上传时间" value={formatDateTime(document.created_at)} />
                  <InfoRow label="最近更新" value={formatDateTime(document.updated_at)} />
                  <InfoRow label="完成索引" value={formatDateTime(document.indexed_at)} />
                  <InfoRow label="发布时间" value={formatDateTime(document.published_at)} />
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-sm font-semibold text-slate-900">管理操作</p>
              <div className="mt-4 grid gap-3">
                {canSubmit ? (
                  <Button
                    className="rounded-xl bg-blue-600 text-white hover:bg-blue-700"
                    disabled={actionKey === "submit"}
                    onClick={() =>
                      void runAction("submit", () => submitDocumentForReview(document.id), "已提交审核")
                    }
                  >
                    {actionKey === "submit" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                    提交审核
                  </Button>
                ) : null}

                {canPublish ? (
                  <Button
                    className="rounded-xl bg-emerald-600 text-white hover:bg-emerald-700"
                    disabled={actionKey === "publish"}
                    onClick={() => void runAction("publish", () => publishDocument(document.id), "文档已发布")}
                  >
                    {actionKey === "publish" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Globe2 className="mr-2 h-4 w-4" />}
                    发布上线
                  </Button>
                ) : null}

                {canUnpublish ? (
                  <Button
                    variant="outline"
                    className="rounded-xl border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100"
                    disabled={actionKey === "unpublish"}
                    onClick={() =>
                      openConfirmDialog({
                        title: "下线文档",
                        description: "下线后用户问答将不再使用这份文档内容，确认继续吗？",
                        confirmLabel: "确认下线",
                        tone: "primary",
                        onConfirm: () => runAction("unpublish", () => unpublishDocument(document.id), "文档已下线"),
                      })
                    }
                  >
                    {actionKey === "unpublish" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Clock3 className="mr-2 h-4 w-4" />}
                    下线文档
                  </Button>
                ) : null}

                <div className="grid grid-cols-2 gap-3">
                  <Button
                    variant="outline"
                    className="rounded-xl border-slate-200"
                    disabled={actionKey === "reindex" || document.index_status === "processing"}
                    onClick={() => void runAction("reindex", () => indexDocument(document.id), "已提交重新索引任务")}
                  >
                    {actionKey === "reindex" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCcw className="mr-2 h-4 w-4" />}
                    重新索引
                  </Button>
                  <Button
                    variant="outline"
                    className="rounded-xl border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                    disabled={actionKey === "delete"}
                    onClick={handleDelete}
                  >
                    {actionKey === "delete" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
                    删除文档
                  </Button>
                </div>
              </div>
            </section>
          </aside>
        </section>
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

      {editorOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm"
          onClick={() => setEditorOpen(false)}
        >
          <div
            className="flex max-h-[86vh] w-full max-w-4xl flex-col rounded-3xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-lg font-semibold text-slate-900">编辑正文内容</p>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  修改后需要重新索引。已发布并生效的文档不能直接覆盖，可保存为新版本。
                </p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setEditorOpen(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <Textarea
              value={draftContent}
              onChange={(event) => setDraftContent(event.target.value)}
              className="mt-5 min-h-[420px] resize-none rounded-2xl border-slate-200 font-mono text-sm leading-6"
            />
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <Button variant="outline" className="rounded-xl border-slate-200" onClick={() => setEditorOpen(false)}>
                取消
              </Button>
              <Button
                variant="outline"
                className="rounded-xl border-slate-200"
                disabled={actionKey === "save-version"}
                onClick={() => handleSaveContent("version")}
              >
                {actionKey === "save-version" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                保存为新版本
              </Button>
              <Button
                className="rounded-xl bg-slate-900 text-white hover:bg-slate-800"
                disabled={!canReplaceContent || actionKey === "save-replace"}
                onClick={() => handleSaveContent("replace")}
              >
                {actionKey === "save-replace" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                保存当前版本
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
