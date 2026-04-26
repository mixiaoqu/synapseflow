"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Clock3, LoaderCircle, RefreshCw, X } from "lucide-react";

import {
  type ActiveIndexingJob,
  getIndexingPanelSummary,
  type IndexingPanelSummary,
} from "@/lib/api/documents";

function t(value: string): string {
  return value;
}

function formatRelativeTime(value: string | null): string {
  if (!value) return t("\u521a\u521a");
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return t("\u521a\u521a");
  const diffMs = Date.now() - timestamp;
  const diffMinutes = Math.max(0, Math.floor(diffMs / 60000));
  if (diffMinutes < 1) return t("\u521a\u521a");
  if (diffMinutes < 60) return `${diffMinutes} ${t("\u5206\u949f\u524d")}`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} ${t("\u5c0f\u65f6\u524d")}`;
  return `${Math.floor(diffHours / 24)} ${t("\u5929\u524d")}`;
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-500">
      {label}
    </div>
  );
}

function JobCard({ job }: { job: ActiveIndexingJob }) {
  const completed = job.indexed + job.failed;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">{job.title}</p>
          <p className="mt-1 text-xs text-slate-500">
            {job.knowledge_base_name ? `${job.knowledge_base_name} · ` : ""}
            {t("\u6392\u961f")} {job.queued} · {t("\u5904\u7406\u4e2d")} {job.processing} · {t("\u5df2\u5b8c\u6210")} {job.indexed}
            {job.failed > 0 ? ` · ${t("\u5931\u8d25")} ${job.failed}` : ""}
          </p>
        </div>
        <span className="rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700">
          {job.progress_percent}%
        </span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-gradient-to-r from-sky-500 to-cyan-400 transition-all"
          style={{ width: `${job.progress_percent}%` }}
        />
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
        <span>{job.total > 0 ? `${completed} / ${job.total}` : t("\u7b49\u5f85\u5f00\u59cb")}</span>
        <span>{formatRelativeTime(job.updated_at)}</span>
      </div>
    </div>
  );
}

export function BackgroundTasksPanel({
  documentsHref = "/admin/documents",
}: {
  documentsHref?: string;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<IndexingPanelSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const badgeCount = useMemo(() => {
    if (!summary) return 0;
    if (summary.failed > 0) return summary.failed;
    return summary.queued + summary.processing;
  }, [summary]);

  const fetchSummary = useCallback(async () => {
    try {
      setLoading(true);
      const nextSummary = await getIndexingPanelSummary();
      setSummary(nextSummary);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("\u540e\u53f0\u4efb\u52a1\u72b6\u6001\u52a0\u8f7d\u5931\u8d25"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSummary();
    const timer = window.setInterval(() => {
      void fetchSummary();
    }, 8000);
    return () => {
      window.clearInterval(timer);
    };
  }, [fetchSummary]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/95 px-4 py-2.5 text-sm font-medium text-slate-700 shadow-lg shadow-slate-900/5 backdrop-blur transition hover:border-sky-300 hover:text-sky-700"
      >
        {summary?.has_active ? (
          <LoaderCircle className="h-4 w-4 animate-spin text-sky-600" />
        ) : summary?.failed ? (
          <AlertTriangle className="h-4 w-4 text-rose-600" />
        ) : (
          <Clock3 className="h-4 w-4 text-slate-500" />
        )}
        <span>{t("\u540e\u53f0\u4efb\u52a1")}</span>
        {badgeCount > 0 ? (
          <span
            className={`inline-flex min-w-5 items-center justify-center rounded-full px-1.5 py-0.5 text-[11px] font-semibold ${
              summary?.failed ? "bg-rose-100 text-rose-700" : "bg-sky-100 text-sky-700"
            }`}
          >
            {badgeCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="fixed bottom-24 right-6 z-50 w-[380px] max-w-[calc(100vw-2rem)] overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl shadow-slate-900/15">
          <div className="border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">{t("\u540e\u53f0\u4efb\u52a1")}</h3>
                <p className="mt-1 text-xs text-slate-500">
                  {t("\u67e5\u770b\u771f\u5b9e\u4efb\u52a1\u7ea7\u522b\u7684\u7d22\u5f15\u8fdb\u5ea6\uff0c\u4e0d\u518d\u6309\u77e5\u8bc6\u5e93\u63a8\u65ad\u3002")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-full p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                aria-label={t("\u5173\u95ed\u540e\u53f0\u4efb\u52a1\u9762\u677f")}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="max-h-[70vh] overflow-y-auto px-5 py-4">
            <div className="grid grid-cols-4 gap-2">
              {[
                { label: t("\u6392\u961f"), value: summary?.queued ?? 0, tone: "bg-amber-50 text-amber-700" },
                { label: t("\u5904\u7406\u4e2d"), value: summary?.processing ?? 0, tone: "bg-sky-50 text-sky-700" },
                { label: t("\u5df2\u5b8c\u6210"), value: summary?.indexed ?? 0, tone: "bg-emerald-50 text-emerald-700" },
                { label: t("\u5931\u8d25"), value: summary?.failed ?? 0, tone: "bg-rose-50 text-rose-700" },
              ].map((item) => (
                <div key={item.label} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <div className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${item.tone}`}>
                    {item.label}
                  </div>
                  <div className="mt-2 text-lg font-semibold text-slate-900">{item.value}</div>
                </div>
              ))}
            </div>

            <div className="mt-5 flex items-center justify-between">
              <h4 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                {t("\u8fdb\u884c\u4e2d")}
              </h4>
              <button
                type="button"
                onClick={() => void fetchSummary()}
                className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 transition hover:text-sky-700"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                {t("\u5237\u65b0")}
              </button>
            </div>

            <div className="mt-3 space-y-3">
              {summary?.active_jobs?.length ? (
                summary.active_jobs.map((job) => <JobCard key={job.job_id} job={job} />)
              ) : (
                <EmptyState label={t("\u5f53\u524d\u6ca1\u6709\u6b63\u5728\u6267\u884c\u7684\u7d22\u5f15\u4efb\u52a1\u3002")} />
              )}
            </div>

            <div className="mt-6">
              <h4 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                {t("\u6700\u8fd1\u5931\u8d25")}
              </h4>
              <div className="mt-3 space-y-3">
                {summary?.recent_failed?.length ? (
                  summary.recent_failed.map((item) => (
                    <div key={`${item.job_id}-${item.document_id}`} className="rounded-2xl border border-rose-100 bg-rose-50/70 px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-900">{item.title}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            {item.job_title}
                            {item.knowledge_base_name ? ` · ${item.knowledge_base_name}` : ""}
                            {" · "}
                            {formatRelativeTime(item.updated_at)}
                          </p>
                        </div>
                        <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-medium text-rose-700">
                          {t("\u5931\u8d25")}
                        </span>
                      </div>
                      {item.index_error ? (
                        <p className="mt-2 line-clamp-2 text-xs text-rose-700">{item.index_error}</p>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <EmptyState label={t("\u6700\u8fd1\u6ca1\u6709\u65b0\u7684\u5931\u8d25\u4efb\u52a1\u3002")} />
                )}
              </div>
            </div>

            {error ? (
              <div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">
                {error}
              </div>
            ) : null}
          </div>

          <div className="border-t border-slate-200 bg-slate-50 px-5 py-3">
            <Link
              href={documentsHref}
              className="inline-flex items-center text-sm font-medium text-sky-700 transition hover:text-sky-900"
            >
              {t("\u524d\u5f80\u6587\u6863\u5e93\u67e5\u770b\u8be6\u60c5")}
            </Link>
          </div>
        </div>
      ) : null}
    </>
  );
}
