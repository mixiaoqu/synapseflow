"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckSquare,
  Clock3,
  FileClock,
  FileSearch,
  FolderOpen,
  Loader2,
  RefreshCcw,
} from "lucide-react";

import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { Button } from "@/components/ui/button";
import { listDocuments, type DocumentListItem } from "@/lib/api/documents";
import { listKnowledgeBases, type KnowledgeBaseWithCount } from "@/lib/api/knowledgeBases";

const FETCH_PAGE_SIZE = 100;
const RECENT_WINDOW_MS = 24 * 60 * 60 * 1000;

type ActivityTone = "default" | "success" | "warning" | "danger";

type DashboardActivity = {
  id: string;
  label: string;
  title: string;
  detail: string;
  timestamp: string;
  href: string;
  tone: ActivityTone;
};

type TaskItem = {
  label: string;
  count: number;
  href: string;
  actionLabel: string;
  icon: React.ComponentType<{ className?: string }>;
  tone: ActivityTone;
};

function toTimestamp(value: string | null | undefined): number {
  if (!value) return 0;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function isToday(value: string | null | undefined): boolean {
  const timestamp = toTimestamp(value);
  if (!timestamp) return false;
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  return timestamp >= todayStart.getTime();
}

function isRecent(value: string | null | undefined): boolean {
  const timestamp = toTimestamp(value);
  if (!timestamp) return false;
  return Date.now() - timestamp <= RECENT_WINDOW_MS;
}

function formatDateTime(value: string | null | undefined): string {
  const timestamp = toTimestamp(value);
  if (!timestamp) return "刚刚";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(timestamp));
}

function formatRelativeTime(value: string | null | undefined): string {
  const timestamp = toTimestamp(value);
  if (!timestamp) return "刚刚";
  const diffMinutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
  if (diffMinutes < 1) return "刚刚";
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;
  return `${Math.floor(diffHours / 24)} 天前`;
}

function toneClasses(tone: ActivityTone): {
  dot: string;
  label: string;
  icon: string;
  button: string;
} {
  switch (tone) {
    case "success":
      return {
        dot: "bg-emerald-500",
        label: "bg-emerald-50 text-emerald-700",
        icon: "text-emerald-600",
        button: "text-emerald-700 hover:text-emerald-900",
      };
    case "warning":
      return {
        dot: "bg-amber-500",
        label: "bg-amber-50 text-amber-700",
        icon: "text-amber-600",
        button: "text-amber-700 hover:text-amber-900",
      };
    case "danger":
      return {
        dot: "bg-rose-500",
        label: "bg-rose-50 text-rose-700",
        icon: "text-rose-600",
        button: "text-rose-700 hover:text-rose-900",
      };
    case "default":
    default:
      return {
        dot: "bg-sky-500",
        label: "bg-sky-50 text-sky-700",
        icon: "text-sky-600",
        button: "text-sky-700 hover:text-sky-900",
      };
  }
}

async function loadAllDocuments(teamId: number): Promise<DocumentListItem[]> {
  const firstPage = await listDocuments({
    page: 1,
    page_size: FETCH_PAGE_SIZE,
    team_id: teamId,
  });

  const totalPages = Math.ceil(firstPage.total / FETCH_PAGE_SIZE);
  if (totalPages <= 1) {
    return firstPage.items;
  }

  const pageRequests: Promise<{ items: DocumentListItem[] }>[] = [];
  for (let page = 2; page <= totalPages; page += 1) {
    pageRequests.push(
      listDocuments({
        page,
        page_size: FETCH_PAGE_SIZE,
        team_id: teamId,
      }),
    );
  }

  const restPages = await Promise.all(pageRequests);
  return firstPage.items.concat(restPages.flatMap((page) => page.items));
}

function buildKnowledgeBaseHref(knowledgeBaseId: number | null | undefined): string {
  return knowledgeBaseId ? `/admin/documents/${knowledgeBaseId}` : "/admin/documents";
}

function buildDashboardActivities(documents: DocumentListItem[]): DashboardActivity[] {
  const activities: DashboardActivity[] = [];

  documents
    .slice()
    .sort((left, right) => toTimestamp(right.created_at) - toTimestamp(left.created_at))
    .slice(0, 5)
    .forEach((document) => {
      activities.push({
        id: `upload-${document.id}`,
        label: "上传",
        title: `《${document.title}》已上传`,
        detail: `${document.knowledge_base_name ?? "未分配知识库"} · 等待索引与审核流程`,
        timestamp: document.created_at,
        href: buildKnowledgeBaseHref(document.knowledge_base_id),
        tone: "default",
      });
    });

  documents
    .filter((document) => Boolean(document.indexed_at))
    .sort((left, right) => toTimestamp(right.indexed_at) - toTimestamp(left.indexed_at))
    .slice(0, 5)
    .forEach((document) => {
      activities.push({
        id: `indexed-${document.id}`,
        label: "索引完成",
        title: `${document.knowledge_base_name ?? "未分配知识库"} 已有文档索引完成`,
        detail:
          document.status === "pending_review"
            ? `《${document.title}》已进入待审核队列`
            : `《${document.title}》可以提交审核`,
        timestamp: document.indexed_at ?? document.updated_at,
        href:
          document.status === "pending_review"
            ? "/admin/review?filter=pending_review"
            : "/admin/review?filter=draft",
        tone: "success",
      });
    });

  documents
    .filter((document) => Boolean(document.published_at))
    .sort((left, right) => toTimestamp(right.published_at) - toTimestamp(left.published_at))
    .slice(0, 5)
    .forEach((document) => {
      activities.push({
        id: `published-${document.id}`,
        label: "已发布",
        title: `${document.knowledge_base_name ?? "未分配知识库"} 有文档发布上线`,
        detail: `《${document.title}》已进入线上问答上下文`,
        timestamp: document.published_at ?? document.updated_at,
        href: "/admin/review?filter=published",
        tone: "success",
      });
    });

  documents
    .filter((document) => document.index_status === "failed")
    .sort((left, right) => toTimestamp(right.updated_at) - toTimestamp(left.updated_at))
    .slice(0, 5)
    .forEach((document) => {
      activities.push({
        id: `failed-${document.id}`,
        label: "索引失败",
        title: `${document.knowledge_base_name ?? "未分配知识库"} 有索引失败文档`,
        detail: `《${document.title}》${document.index_error?.trim() ? `：${document.index_error.trim()}` : "需要重新处理"}`,
        timestamp: document.updated_at,
        href: buildKnowledgeBaseHref(document.knowledge_base_id),
        tone: "danger",
      });
    });

  return activities
    .sort((left, right) => toTimestamp(right.timestamp) - toTimestamp(left.timestamp))
    .slice(0, 6);
}

function SectionCard({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
      <div className="border-b border-slate-200 pb-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
          {eyebrow}
        </div>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-900">{title}</h2>
      </div>
      <div className="pt-4">{children}</div>
    </section>
  );
}

function TaskRow({ item }: { item: TaskItem }) {
  const Icon = item.icon;
  const tone = toneClasses(item.tone);

  return (
    <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white">
        <Icon className={`h-4 w-4 ${tone.icon}`} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-slate-900">{item.label}</div>
      </div>
      <div className="text-2xl font-semibold tracking-tight text-slate-900">{item.count}</div>
      <Button
        asChild
        variant="ghost"
        className={`h-9 shrink-0 rounded-xl px-3 text-sm font-medium ${tone.button}`}
      >
        <Link href={item.href}>
          {item.actionLabel}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </Button>
    </div>
  );
}

function TaskSummaryRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: ActivityTone;
}) {
  const toneStyle = toneClasses(tone);

  return (
    <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
      <div className="flex items-center gap-3">
        <span className={`h-2.5 w-2.5 rounded-full ${toneStyle.dot}`} />
        <span className="text-sm font-medium text-slate-700">{label}</span>
      </div>
      <span className="text-2xl font-semibold tracking-tight text-slate-900">{value}</span>
    </div>
  );
}

function ActivityRow({ item }: { item: DashboardActivity }) {
  const tone = toneClasses(item.tone);

  return (
    <Link
      href={item.href}
      className="group flex items-start gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 transition hover:border-slate-300 hover:bg-white"
    >
      <div className="mt-1 flex h-8 min-w-8 items-center justify-center rounded-full bg-white">
        <span className={`h-2.5 w-2.5 rounded-full ${tone.dot}`} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${tone.label}`}>
            {item.label}
          </span>
          <span className="text-xs text-slate-400">{formatDateTime(item.timestamp)}</span>
        </div>
        <p className="mt-2 text-sm font-medium text-slate-900">{item.title}</p>
        <p className="mt-1 text-sm leading-6 text-slate-500">{item.detail}</p>
      </div>
      <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500" />
    </Link>
  );
}

export function AdminWorkbench() {
  const { teamId, selectedTeam, teamsLoading } = useTeamScope();
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  const loadDashboard = useCallback(
    async (silent = false) => {
      if (teamId == null) {
        setDocuments([]);
        setKnowledgeBases([]);
        setLoading(false);
        setRefreshing(false);
        return;
      }

      if (silent) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      try {
        const [nextKnowledgeBases, nextDocuments] = await Promise.all([
          listKnowledgeBases(teamId),
          loadAllDocuments(teamId),
        ]);
        setKnowledgeBases(nextKnowledgeBases);
        setDocuments(nextDocuments);
        setError(null);
        setLastUpdatedAt(new Date().toISOString());
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "工作台数据加载失败");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [teamId],
  );

  useEffect(() => {
    if (teamsLoading) return;
    void loadDashboard();
  }, [loadDashboard, teamsLoading]);

  const summary = useMemo(() => {
    const queuedCount = documents.filter((item) => item.index_status === "queued").length;
    const processingCount = documents.filter((item) => item.index_status === "processing").length;
    const failedIndexCount = documents.filter((item) => item.index_status === "failed").length;
    const submittableCount = documents.filter(
      (item) => item.status === "draft" && item.index_status === "indexed",
    ).length;
    const pendingReviewCount = documents.filter((item) => item.status === "pending_review").length;
    const publishedCount = documents.filter((item) => item.status === "published").length;
    const todayUploadedCount = documents.filter((item) => isToday(item.created_at)).length;
    const recentCompletedCount = documents.filter((item) => isRecent(item.indexed_at)).length;
    const emptyKnowledgeBaseCount = knowledgeBases.filter((item) => item.document_count === 0).length;

    return {
      queuedCount,
      processingCount,
      failedIndexCount,
      submittableCount,
      pendingReviewCount,
      publishedCount,
      todayUploadedCount,
      recentCompletedCount,
      emptyKnowledgeBaseCount,
      openActionCount: submittableCount + pendingReviewCount + failedIndexCount,
    };
  }, [documents, knowledgeBases]);

  const tasks = useMemo<TaskItem[]>(
    () => [
      {
        label: "可提交审核",
        count: summary.submittableCount,
        href: "/admin/review?filter=draft",
        actionLabel: "去处理",
        icon: FileSearch,
        tone: "default",
      },
      {
        label: "待审核",
        count: summary.pendingReviewCount,
        href: "/admin/review?filter=pending_review",
        actionLabel: "去审核",
        icon: CheckSquare,
        tone: "warning",
      },
      {
        label: "索引失败",
        count: summary.failedIndexCount,
        href: "/admin/documents",
        actionLabel: "查看失败",
        icon: AlertTriangle,
        tone: "danger",
      },
      {
        label: "空知识库",
        count: summary.emptyKnowledgeBaseCount,
        href: "/admin/documents",
        actionLabel: "去整理",
        icon: FolderOpen,
        tone: "warning",
      },
    ],
    [
      summary.emptyKnowledgeBaseCount,
      summary.failedIndexCount,
      summary.pendingReviewCount,
      summary.submittableCount,
    ],
  );

  const activities = useMemo(() => buildDashboardActivities(documents), [documents]);

  if (teamsLoading || loading) {
    return (
      <div className="flex min-h-full items-center justify-center bg-slate-50 px-6 py-8 text-sm text-slate-500 sm:px-8">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        正在加载管理工作台...
      </div>
    );
  }

  if (teamId == null) {
    return (
      <div className="min-h-full bg-slate-50 px-6 py-8 sm:px-8">
        <div className="mx-auto max-w-4xl rounded-[28px] border border-slate-200 bg-white px-8 py-14 text-center shadow-sm">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-slate-500">
            <BookOpen className="h-6 w-6" />
          </div>
          <h1 className="mt-5 text-2xl font-semibold tracking-tight text-slate-900">请选择团队</h1>
          <p className="mt-3 text-sm leading-7 text-slate-500">
            工作台数据会跟随顶部团队范围切换，先选择一个团队再查看待办与最近活动。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-slate-50 px-6 py-8 sm:px-8">
      <div className="mx-auto max-w-[1320px] space-y-6">
        <section className="rounded-[28px] border border-slate-200 bg-white px-6 py-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-600">
                <span className="text-base font-semibold text-slate-900">
                  当前团队：{selectedTeam?.name ?? "未选择"}
                </span>
                <span>今日新增 {summary.todayUploadedCount}</span>
                <span>待处理 {summary.openActionCount}</span>
                <span>已发布 {summary.publishedCount}</span>
                <span className={summary.failedIndexCount > 0 ? "font-medium text-rose-700" : ""}>
                  失败 {summary.failedIndexCount}
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs text-slate-400">最近更新：{formatRelativeTime(lastUpdatedAt)}</span>
              <Button
                type="button"
                variant="outline"
                onClick={() => void loadDashboard(true)}
                disabled={refreshing}
                className="h-10 rounded-xl border-slate-200 bg-white px-4 text-slate-700 hover:bg-slate-50"
              >
                {refreshing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    刷新中
                  </>
                ) : (
                  <>
                    <RefreshCcw className="h-4 w-4" />
                    刷新
                  </>
                )}
              </Button>
            </div>
          </div>
        </section>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]">
          <SectionCard eyebrow="Action Queue" title="待处理">
            <div className="space-y-3">
              {tasks.map((task) => (
                <TaskRow key={task.label} item={task} />
              ))}
            </div>
          </SectionCard>

          <SectionCard eyebrow="Background Tasks" title="后台任务">
            <div className="space-y-3">
              <TaskSummaryRow
                label="索引中"
                value={summary.queuedCount + summary.processingCount}
                tone="default"
              />
              <TaskSummaryRow label="失败" value={summary.failedIndexCount} tone="danger" />
              <TaskSummaryRow label="最近完成" value={summary.recentCompletedCount} tone="success" />
            </div>

            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-600">
              {summary.failedIndexCount > 0 ? (
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
                  <p>当前团队还有索引失败文档，建议先回到知识库页处理失败原因。</p>
                </div>
              ) : summary.queuedCount + summary.processingCount > 0 ? (
                <div className="flex items-start gap-3">
                  <Clock3 className="mt-0.5 h-4 w-4 shrink-0 text-sky-600" />
                  <p>当前还有文档在排队或索引中，完成后就可以进入审核流程。</p>
                </div>
              ) : (
                <div className="flex items-start gap-3">
                  <CheckSquare className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  <p>当前团队没有未完成的索引任务，可以直接处理审核与发布动作。</p>
                </div>
              )}
            </div>
          </SectionCard>
        </div>

        <SectionCard eyebrow="Recent Activity" title="最近活动">
          <div className="space-y-3">
            {activities.length > 0 ? (
              activities.map((activity) => <ActivityRow key={activity.id} item={activity} />)
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-5 py-10 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-500">
                  <FileClock className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-sm font-semibold text-slate-900">最近还没有新的活动</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  可以先上传文档或进入审核页开始处理工作流。
                </p>
              </div>
            )}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
