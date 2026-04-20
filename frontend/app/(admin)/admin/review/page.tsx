"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import {
  approveDocument,
  listDocuments,
  publishDocument,
  rejectDocument,
  submitDocumentForReview,
  unpublishDocument,
  type DocumentDetail,
  type DocumentLifecycleStatus,
  type DocumentListItem,
} from "@/lib/api/documents";

type ReviewAction = "submit" | "approve" | "reject" | "publish" | "unpublish";
type ReviewFilter = "all" | "pending_review" | "approved" | "published" | "draft";

const actionLabels: Record<ReviewAction, string> = {
  submit: "提交审核",
  approve: "审核通过",
  reject: "退回草稿",
  publish: "发布上线",
  unpublish: "下线",
};

const statusLabels: Record<DocumentLifecycleStatus, string> = {
  draft: "草稿",
  pending_review: "待审核",
  approved: "已通过",
  published: "已发布",
  archived: "已归档",
};

const indexStatusLabels: Record<string, string> = {
  queued: "排队中",
  processing: "处理中",
  indexed: "已完成",
  failed: "失败",
};

const filterLabels: Record<ReviewFilter, string> = {
  all: "全部",
  pending_review: "待审核",
  approved: "已通过",
  published: "已发布",
  draft: "草稿",
};

function statusBadgeClass(status: DocumentLifecycleStatus): string {
  switch (status) {
    case "pending_review":
      return "bg-amber-50 text-amber-700 ring-1 ring-amber-200";
    case "approved":
      return "bg-blue-50 text-blue-700 ring-1 ring-blue-200";
    case "published":
      return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200";
    case "archived":
      return "bg-slate-100 text-slate-500 ring-1 ring-slate-200";
    default:
      return "bg-slate-100 text-slate-700 ring-1 ring-slate-200";
  }
}

function indexBadgeClass(status: string): string {
  switch (status) {
    case "indexed":
      return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200";
    case "processing":
      return "bg-sky-50 text-sky-700 ring-1 ring-sky-200";
    case "failed":
      return "bg-rose-50 text-rose-700 ring-1 ring-rose-200";
    default:
      return "bg-slate-100 text-slate-600 ring-1 ring-slate-200";
  }
}

function actionButtonClass(action: ReviewAction): string {
  switch (action) {
    case "publish":
      return "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100";
    case "unpublish":
      return "border border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100";
    case "approve":
      return "border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100";
    case "reject":
      return "border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100";
    default:
      return "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50";
  }
}

function availableActions(item: DocumentListItem): ReviewAction[] {
  const indexedReady = item.index_status === "indexed";

  if (item.status === "draft" && indexedReady) {
    return ["submit"];
  }
  if (item.status === "pending_review") {
    return ["approve", "reject"];
  }
  if (item.status === "approved" && indexedReady) {
    return ["publish"];
  }
  if (item.status === "published") {
    return ["unpublish"];
  }
  return [];
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "暂无";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function AdminReviewPage() {
  const [items, setItems] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [actioningId, setActioningId] = useState<number | null>(null);
  const [activeFilter, setActiveFilter] = useState<ReviewFilter>("pending_review");

  const summary = useMemo(
    () => ({
      pendingReview: items.filter((item) => item.status === "pending_review").length,
      approved: items.filter((item) => item.status === "approved").length,
      published: items.filter((item) => item.status === "published").length,
      draft: items.filter((item) => item.status === "draft").length,
    }),
    [items],
  );

  const filteredItems = useMemo(() => {
    if (activeFilter === "all") {
      return items;
    }
    if (activeFilter === "approved") {
      return items.filter((item) => item.status === "approved");
    }
    return items.filter((item) => item.status === activeFilter);
  }, [activeFilter, items]);

  const load = async () => {
    setLoading(true);
    try {
      const response = await listDocuments({ page: 1, page_size: 100 });
      setItems(response.items);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载审核列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const applyAction = async (docId: number, action: ReviewAction) => {
    setActioningId(docId);
    try {
      let updated: DocumentDetail;
      switch (action) {
        case "submit":
          updated = await submitDocumentForReview(docId);
          break;
        case "approve":
          updated = await approveDocument(docId);
          break;
        case "reject":
          updated = await rejectDocument(docId);
          break;
        case "publish":
          updated = await publishDocument(docId);
          break;
        case "unpublish":
          updated = await unpublishDocument(docId);
          break;
      }

      setItems((prev) =>
        prev.map((item) =>
          item.id === docId
            ? {
                ...item,
                status: updated.status,
                published_at: updated.published_at,
                published_by: updated.published_by,
                reviewed_at: updated.reviewed_at,
                reviewed_by: updated.reviewed_by,
                updated_at: updated.updated_at,
              }
            : item,
        ),
      );
      toast.success(`文档已${actionLabels[action]}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "操作失败");
    } finally {
      setActioningId(null);
    }
  };

  return (
    <div className="px-6 py-8 sm:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">审核发布</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              只有通过审核并正式发布的文档才会进入前台问答链路。这里会根据文档当前状态展示可执行动作，避免误操作。
            </p>
          </div>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                刷新中
              </span>
            ) : (
              "刷新列表"
            )}
          </button>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5 shadow-sm">
            <p className="text-xs text-amber-700">待审核</p>
            <p className="mt-2 text-2xl font-semibold text-amber-900">{summary.pendingReview}</p>
          </div>
          <div className="rounded-2xl border border-blue-200 bg-blue-50/70 p-5 shadow-sm">
            <p className="text-xs text-blue-700">已通过</p>
            <p className="mt-2 text-2xl font-semibold text-blue-900">{summary.approved}</p>
          </div>
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-5 shadow-sm">
            <p className="text-xs text-emerald-700">已发布</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-900">{summary.published}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs text-slate-500">草稿</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{summary.draft}</p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-2">
          {(["pending_review", "approved", "published", "draft", "all"] as ReviewFilter[]).map(
            (filterKey) => (
              <button
                key={filterKey}
                type="button"
                onClick={() => setActiveFilter(filterKey)}
                className={`rounded-full px-4 py-2 text-sm transition ${
                  activeFilter === filterKey
                    ? "bg-slate-900 text-white"
                    : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
                }`}
              >
                {filterLabels[filterKey]}
              </button>
            ),
          )}
        </div>

        <div className="mt-6 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-slate-500">文档</th>
                <th className="px-4 py-3 text-left font-medium text-slate-500">生命周期</th>
                <th className="px-4 py-3 text-left font-medium text-slate-500">索引状态</th>
                <th className="px-4 py-3 text-left font-medium text-slate-500">最近时间</th>
                <th className="px-4 py-3 text-left font-medium text-slate-500">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-slate-500">
                    正在加载审核列表...
                  </td>
                </tr>
              ) : filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-slate-500">
                    当前筛选下暂无文档
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => {
                  const actions = availableActions(item);
                  const latestTime = item.published_at || item.reviewed_at || item.updated_at;
                  return (
                    <tr key={item.id}>
                      <td className="px-4 py-4 align-top">
                        <div className="font-medium text-slate-800">{item.title}</div>
                        <div className="mt-1 text-xs text-slate-500">
                          {item.knowledge_base_name || "未归档知识库"}
                        </div>
                        <div className="mt-1 text-xs text-slate-400">版本 v{item.version}</div>
                      </td>
                      <td className="px-4 py-4 align-top">
                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs ${statusBadgeClass(item.status)}`}>
                          {statusLabels[item.status] || item.status}
                        </span>
                      </td>
                      <td className="px-4 py-4 align-top">
                        <div className="flex flex-col gap-2">
                          <span className={`inline-flex w-fit rounded-full px-2.5 py-1 text-xs ${indexBadgeClass(item.index_status)}`}>
                            {indexStatusLabels[item.index_status] || item.index_status}
                          </span>
                          {item.index_error ? (
                            <span className="max-w-xs text-xs text-rose-600">{item.index_error}</span>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-4 py-4 align-top text-slate-600">
                        <div className="text-sm">{formatDateTime(latestTime)}</div>
                        <div className="mt-1 text-xs text-slate-400">
                          {item.published_at
                            ? "最近发布"
                            : item.reviewed_at
                              ? "最近审核"
                              : "最近更新"}
                        </div>
                      </td>
                      <td className="px-4 py-4 align-top">
                        {actions.length === 0 ? (
                          <span className="text-xs text-slate-400">
                            {item.index_status !== "indexed"
                              ? "等待索引完成后才能进入审核流转"
                              : "当前状态暂无可执行动作"}
                          </span>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {actions.map((action) => (
                              <button
                                key={action}
                                type="button"
                                disabled={actioningId === item.id}
                                onClick={() => void applyAction(item.id, action)}
                                className={`rounded-lg px-2.5 py-1.5 text-xs transition disabled:cursor-not-allowed disabled:opacity-50 ${actionButtonClass(action)}`}
                              >
                                {actioningId === item.id ? (
                                  <span className="inline-flex items-center gap-1">
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    处理中
                                  </span>
                                ) : (
                                  actionLabels[action]
                                )}
                              </button>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
