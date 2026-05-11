"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileStack,
  Loader2,
  PackageOpen,
} from "lucide-react";

import type { KnowledgeBaseWithCount } from "@/lib/api/knowledgeBases";
import { cn } from "@/lib/utils";

export type KnowledgeBaseWorkbenchTone =
  | "danger"
  | "warning"
  | "review"
  | "info"
  | "success"
  | "muted";

export type KnowledgeBaseWorkbenchAction =
  | "failed"
  | "indexing"
  | "pending_review"
  | "submittable"
  | "upload";

export const knowledgeBaseToneMeta: Record<
  KnowledgeBaseWorkbenchTone,
  {
    border: string;
    stripe: string;
    chip: string;
    headline: string;
    panel: string;
  }
> = {
  danger: {
    border: "border-rose-300",
    stripe: "bg-rose-500",
    chip: "border-rose-200 bg-rose-50 text-rose-700",
    headline: "text-rose-700",
    panel: "bg-rose-50/70",
  },
  warning: {
    border: "border-amber-300",
    stripe: "bg-amber-500",
    chip: "border-amber-200 bg-amber-50 text-amber-700",
    headline: "text-amber-700",
    panel: "bg-amber-50/70",
  },
  review: {
    border: "border-orange-300",
    stripe: "bg-orange-500",
    chip: "border-orange-200 bg-orange-50 text-orange-700",
    headline: "text-orange-700",
    panel: "bg-orange-50/70",
  },
  info: {
    border: "border-blue-300",
    stripe: "bg-blue-500",
    chip: "border-blue-200 bg-blue-50 text-blue-700",
    headline: "text-blue-700",
    panel: "bg-blue-50/70",
  },
  success: {
    border: "border-emerald-300",
    stripe: "bg-emerald-500",
    chip: "border-emerald-200 bg-emerald-50 text-emerald-700",
    headline: "text-emerald-700",
    panel: "bg-emerald-50/70",
  },
  muted: {
    border: "border-slate-200",
    stripe: "bg-slate-300",
    chip: "border-slate-200 bg-slate-100 text-slate-600",
    headline: "text-slate-600",
    panel: "bg-slate-50",
  },
};

export function formatKnowledgeBaseDateTime(value?: string | null) {
  if (!value) return "暂无记录";
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function getKnowledgeBaseIndexingCount(knowledgeBase: KnowledgeBaseWithCount) {
  return knowledgeBase.queued_document_count + knowledgeBase.processing_document_count;
}

export function getKnowledgeBaseStatusSummary(
  knowledgeBase: KnowledgeBaseWithCount,
): {
  label: string;
  headline: string;
  tone: KnowledgeBaseWorkbenchTone;
  action: KnowledgeBaseWorkbenchAction;
  actionLabel: string;
} {
  const indexingCount = getKnowledgeBaseIndexingCount(knowledgeBase);

  if (knowledgeBase.failed_document_count > 0) {
    return {
      label: `失败 ${knowledgeBase.failed_document_count}`,
      headline: `${knowledgeBase.failed_document_count} 份文档索引失败，需要处理`,
      tone: "danger",
      action: "failed",
      actionLabel: "查看失败项",
    };
  }

  if (indexingCount > 0) {
    return {
      label: `处理中 ${indexingCount}`,
      headline: `${indexingCount} 份文档正在排队或处理中`,
      tone: "warning",
      action: "indexing",
      actionLabel: "进入查看",
    };
  }

  if (knowledgeBase.pending_review_document_count > 0) {
    return {
      label: `待审核 ${knowledgeBase.pending_review_document_count}`,
      headline: `${knowledgeBase.pending_review_document_count} 份文档待审核`,
      tone: "review",
      action: "pending_review",
      actionLabel: "去审核",
    };
  }

  if (knowledgeBase.submittable_document_count > 0) {
    return {
      label: `待提交 ${knowledgeBase.submittable_document_count}`,
      headline: `${knowledgeBase.submittable_document_count} 份文档可提交审核`,
      tone: "info",
      action: "submittable",
      actionLabel: "去处理",
    };
  }

  if (knowledgeBase.published_document_count > 0) {
    return {
      label: `已发布 ${knowledgeBase.published_document_count}`,
      headline: `${knowledgeBase.published_document_count} 份文档已发布可用`,
      tone: "success",
      action: "upload",
      actionLabel: "上传文档",
    };
  }

  return {
    label: "尚无文档",
    headline: "先上传文档，建立这个知识库的内容",
    tone: "muted",
    action: "upload",
    actionLabel: "上传文档",
  };
}

function SummaryIcon({ tone }: { tone: KnowledgeBaseWorkbenchTone }) {
  if (tone === "danger") return <AlertTriangle className="h-3.5 w-3.5" />;
  if (tone === "warning") return <Loader2 className="h-3.5 w-3.5 animate-spin" />;
  if (tone === "review") return <Clock3 className="h-3.5 w-3.5" />;
  if (tone === "info") return <PackageOpen className="h-3.5 w-3.5" />;
  if (tone === "success") return <CheckCircle2 className="h-3.5 w-3.5" />;
  return <FileStack className="h-3.5 w-3.5" />;
}

export function KnowledgeBaseStatusSummary({
  knowledgeBase,
  className,
}: {
  knowledgeBase: KnowledgeBaseWithCount;
  className?: string;
}) {
  const summary = getKnowledgeBaseStatusSummary(knowledgeBase);
  const tone = knowledgeBaseToneMeta[summary.tone];
  const indexingCount = getKnowledgeBaseIndexingCount(knowledgeBase);
  const publishedCount = knowledgeBase.published_document_count;
  const secondaryLine =
    summary.tone === "danger"
      ? `${knowledgeBase.failed_document_count} 份异常`
      : summary.tone === "warning"
        ? `${indexingCount} 份索引中`
        : summary.tone === "success"
          ? `${publishedCount} 份可用文档`
          : summary.tone === "muted"
            ? "尚未上传文档"
            : summary.headline;

  return (
    <div className={cn("rounded-2xl border border-slate-200 bg-slate-50/70 p-4", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
              tone.chip,
            )}
          >
            <SummaryIcon tone={summary.tone} />
            {summary.label}
          </div>
          <p className={cn("mt-3 line-clamp-1 text-sm font-semibold", tone.headline)}>
            {summary.headline}
          </p>
          <p className="mt-1 text-xs text-slate-500">{secondaryLine}</p>
        </div>
        <div className={cn("mt-1 h-8 w-1 rounded-full", tone.stripe)} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600">
          文档 {knowledgeBase.document_count}
        </span>
        <span className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600">
          已发布 {publishedCount}
        </span>
        {knowledgeBase.failed_document_count > 0 ? (
          <span className="rounded-full bg-rose-50 px-2.5 py-1 text-xs text-rose-700">
            异常 {knowledgeBase.failed_document_count}
          </span>
        ) : null}
        {indexingCount > 0 ? (
          <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs text-amber-700">
            索引中 {indexingCount}
          </span>
        ) : null}
      </div>
    </div>
  );
}
