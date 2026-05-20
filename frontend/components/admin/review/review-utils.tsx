import type { ReactNode } from "react";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Clock3,
  FileText,
  Loader2,
  Rocket,
} from "lucide-react";

import type {
  DocumentDetail,
  DocumentLifecycleStatus,
  DocumentListItem,
} from "@/lib/api/documents";

export type ReviewAction =
  | "submit"
  | "approve_publish"
  | "reject"
  | "unpublish";

export type ReviewFilter =
  | "all"
  | "draft"
  | "pending_review"
  | "published";

type StatusMeta = {
  label: string;
  className: string;
  icon: ReactNode;
};

type ActionMeta = {
  label: string;
  batchLabel: string;
  successMessage: string;
};

export const REVIEW_FILTER_ORDER: ReviewFilter[] = [
  "draft",
  "pending_review",
  "published",
  "all",
];

export const reviewFilterLabels: Record<ReviewFilter, string> = {
  all: "全部",
  draft: "草稿",
  pending_review: "待审核",
  published: "已发布",
};

export const reviewActionMeta: Record<ReviewAction, ActionMeta> = {
  submit: {
    label: "提交审核",
    batchLabel: "批量提交审核",
    successMessage: "文档已提交审核",
  },
  approve_publish: {
    label: "审核并发布",
    batchLabel: "批量审核并发布",
    successMessage: "文档已审核并发布",
  },
  reject: {
    label: "退回",
    batchLabel: "批量退回",
    successMessage: "文档已退回草稿",
  },
  unpublish: {
    label: "下线",
    batchLabel: "批量下线",
    successMessage: "文档已从问答上下文中下线",
  },
};

export function getReviewActionLabel(
  action: ReviewAction,
  status?: DocumentLifecycleStatus | null,
): string {
  if (action === "approve_publish") {
    return status === "archived" ? "重新上线" : reviewActionMeta[action].label;
  }
  return reviewActionMeta[action].label;
}

export function getReviewActionBatchLabel(
  action: ReviewAction,
  status?: DocumentLifecycleStatus | null,
): string {
  if (action === "approve_publish") {
    return status === "archived" ? "批量重新上线" : reviewActionMeta[action].batchLabel;
  }
  return reviewActionMeta[action].batchLabel;
}

export function getReviewActionSuccessMessage(
  action: ReviewAction,
  status?: DocumentLifecycleStatus | null,
): string {
  if (action === "approve_publish") {
    return status === "archived" ? "文档已重新上线" : reviewActionMeta[action].successMessage;
  }
  return reviewActionMeta[action].successMessage;
}

export const lifecycleMeta: Record<DocumentLifecycleStatus, StatusMeta> = {
  draft: {
    label: "草稿",
    className: "border-slate-200/80 bg-slate-100 text-slate-700",
    icon: <FileText className="h-3.5 w-3.5" />,
  },
  pending_review: {
    label: "待审核",
    className: "border-amber-200/70 bg-amber-50 text-amber-700",
    icon: <Clock3 className="h-3.5 w-3.5" />,
  },
  published: {
    label: "已发布",
    className: "border-emerald-200/70 bg-emerald-50 text-emerald-700",
    icon: <Rocket className="h-3.5 w-3.5" />,
  },
  archived: {
    label: "已归档",
    className: "border-slate-200/80 bg-slate-100 text-slate-500",
    icon: <Archive className="h-3.5 w-3.5" />,
  },
};

export const indexStatusMeta: Record<
  DocumentListItem["index_status"],
  StatusMeta
> = {
  queued: {
    label: "排队中",
    className: "border-slate-200/80 bg-slate-100 text-slate-600",
    icon: <Clock3 className="h-3.5 w-3.5" />,
  },
  processing: {
    label: "处理中",
    className: "border-sky-200/70 bg-sky-50 text-sky-700",
    icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
  },
  indexed: {
    label: "索引完成",
    className: "border-emerald-200/70 bg-emerald-50 text-emerald-700",
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
  },
  failed: {
    label: "索引失败",
    className: "border-rose-200/70 bg-rose-50 text-rose-700",
    icon: <AlertTriangle className="h-3.5 w-3.5" />,
  },
};

export function availableReviewActions(
  item: Pick<DocumentListItem, "status" | "index_status">,
): ReviewAction[] {
  const indexedReady = item.index_status === "indexed";

  if (item.status === "draft" && indexedReady) {
    return ["submit"];
  }
  if (item.status === "pending_review") {
    return ["approve_publish", "reject"];
  }
  if (item.status === "archived" && indexedReady) {
    return ["approve_publish"];
  }
  if (item.status === "published") {
    return ["unpublish"];
  }
  return [];
}

export function actionButtonClass(action: ReviewAction): string {
  switch (action) {
    case "approve_publish":
      return "bg-slate-900 text-white hover:bg-slate-800";
    case "reject":
      return "border border-rose-200 bg-white text-rose-600 hover:bg-rose-50";
    case "unpublish":
      return "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50";
    case "submit":
      return "border border-blue-200 bg-white text-blue-700 hover:bg-blue-50";
    default:
      return "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50";
  }
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "暂无";

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
    hour12: false,
  }).format(date);
}

export function getLatestActivityAt(item: DocumentListItem): string {
  return item.published_at || item.reviewed_at || item.updated_at || item.created_at;
}

export function getTimelineLabel(item: DocumentListItem): string {
  if (item.published_at) return "最近发布";
  if (item.reviewed_at) return "最近审核";
  return "最近更新";
}

export function sortReviewDocuments(
  items: DocumentListItem[],
): DocumentListItem[] {
  return [...items].sort((left, right) => {
    return (
      new Date(getLatestActivityAt(right)).getTime() -
      new Date(getLatestActivityAt(left)).getTime()
    );
  });
}

export function looksLikeMarkdown(
  documentType: string | null | undefined,
  content: string,
): boolean {
  const normalizedType = (documentType || "").toLowerCase();
  if (normalizedType === "md" || normalizedType === "markdown") return true;
  return /(^|\n)\s{0,3}(#{1,6}\s|[-*]\s|\d+\.\s|>\s|```)/.test(content);
}

export function applyDocumentDetailToListItem(
  item: DocumentListItem,
  detail: DocumentDetail,
): DocumentListItem {
  return {
    ...item,
    title: detail.title,
    document_type: detail.document_type,
    size: detail.size,
    version: detail.version,
    is_current: detail.is_current,
    is_latest: detail.is_latest,
    is_live: detail.is_live,
    knowledge_base_id: detail.knowledge_base_id,
    category_id: detail.category_id,
    category_name: detail.category_name,
    source_path: detail.source_path,
    status: detail.status,
    published_at: detail.published_at,
    published_by: detail.published_by,
    reviewed_at: detail.reviewed_at,
    reviewed_by: detail.reviewed_by,
    index_status: detail.index_status,
    index_error: detail.index_error,
    indexed_at: detail.indexed_at,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
  };
}
