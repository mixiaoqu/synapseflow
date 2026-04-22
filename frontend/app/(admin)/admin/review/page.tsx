"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { FilterX, Loader2, RefreshCcw, Search } from "lucide-react";
import { Toaster, toast } from "sonner";

import { BatchActionBar } from "@/components/admin/review/BatchActionBar";
import { ReviewDocumentSheet } from "@/components/admin/review/ReviewDocumentSheet";
import { ReviewTable } from "@/components/admin/review/ReviewTable";
import {
  REVIEW_FILTER_ORDER,
  applyDocumentDetailToListItem,
  availableReviewActions,
  reviewActionMeta,
  reviewFilterLabels,
  sortReviewDocuments,
  type ReviewAction,
  type ReviewFilter,
} from "@/components/admin/review/review-utils";
import { useTeamScope } from "@/components/team-scope/TeamScopeProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  listDocuments,
  publishDocument,
  rejectDocument,
  submitDocumentForReview,
  unpublishDocument,
  type DocumentDetail,
  type DocumentListItem,
} from "@/lib/api/documents";

const FETCH_PAGE_SIZE = 100;

async function runReviewAction(
  documentId: number,
  action: ReviewAction,
): Promise<DocumentDetail[]> {
  switch (action) {
    case "submit":
      return [await submitDocumentForReview(documentId)];
    case "approve_publish":
      return [await publishDocument(documentId)];
    case "reject":
      return [await rejectDocument(documentId)];
    case "unpublish":
      return [await unpublishDocument(documentId)];
  }
}

function mergeUpdatedDocuments(
  currentItems: DocumentListItem[],
  updates: DocumentDetail[],
): DocumentListItem[] {
  if (updates.length === 0) return currentItems;

  const detailMap = new Map(updates.map((detail) => [detail.id, detail]));
  return sortReviewDocuments(
    currentItems.map((item) => {
      const updated = detailMap.get(item.id);
      return updated ? applyDocumentDetailToListItem(item, updated) : item;
    }),
  );
}

export default function AdminReviewPage() {
  const { teamId, selectedTeam, teamsLoading } = useTeamScope();

  const [items, setItems] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState<ReviewFilter>("pending_review");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [busyIds, setBusyIds] = useState<number[]>([]);
  const [runningBatchAction, setRunningBatchAction] = useState<ReviewAction | null>(null);
  const [previewDocumentId, setPreviewDocumentId] = useState<number | null>(null);

  const loadDocuments = useCallback(
    async (silent = false) => {
      if (teamId == null) {
        setItems([]);
        setSelectedIds([]);
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
        const loadedItems: DocumentListItem[] = [];
        let page = 1;
        let total = 0;

        do {
          const response = await listDocuments({
            page,
            page_size: FETCH_PAGE_SIZE,
            team_id: teamId,
          });

          loadedItems.push(...response.items);
          total = response.total;
          page += 1;
        } while (loadedItems.length < total);

        setItems(sortReviewDocuments(loadedItems));
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "加载审核列表失败");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [teamId],
  );

  useEffect(() => {
    if (teamsLoading) return;
    void loadDocuments();
  }, [loadDocuments, teamsLoading]);

  useEffect(() => {
    setSelectedIds((current) => current.filter((id) => items.some((item) => item.id === id)));
  }, [items]);

  const summary = useMemo(
    () => ({
      all: items.length,
      draft: items.filter((item) => item.status === "draft").length,
      pending_review: items.filter((item) => item.status === "pending_review").length,
      published: items.filter((item) => item.status === "published").length,
    }),
    [items],
  );

  const filteredItems = useMemo(() => {
    const keyword = searchQuery.trim().toLowerCase();

    return items.filter((item) => {
      const matchesFilter = activeFilter === "all" || item.status === activeFilter;
      const matchesKeyword =
        keyword.length === 0 ||
        item.title.toLowerCase().includes(keyword) ||
        (item.knowledge_base_name ?? "").toLowerCase().includes(keyword) ||
        (item.category_name ?? "").toLowerCase().includes(keyword);

      return matchesFilter && matchesKeyword;
    });
  }, [activeFilter, items, searchQuery]);

  const selectedItems = useMemo(
    () => items.filter((item) => selectedIds.includes(item.id)),
    [items, selectedIds],
  );

  const visibleBatchActions = useMemo(() => {
    const actionSet = new Set<ReviewAction>();
    selectedItems.forEach((item) => {
      availableReviewActions(item).forEach((action) => actionSet.add(action));
    });
    return Array.from(actionSet);
  }, [selectedItems]);

  const enabledBatchActions = useMemo(() => {
    if (selectedItems.length === 0) return [];

    let intersection = new Set(availableReviewActions(selectedItems[0]));
    for (const item of selectedItems.slice(1)) {
      const nextActions = new Set(availableReviewActions(item));
      intersection = new Set(
        Array.from(intersection).filter((action) => nextActions.has(action)),
      );
    }
    return Array.from(intersection);
  }, [selectedItems]);

  const batchDisableReason = useMemo(() => {
    if (selectedItems.length === 0) return null;
    if (visibleBatchActions.length > 0 && enabledBatchActions.length === 0) {
      return "所选文档状态不一致，当前没有统一可执行的批量动作。";
    }
    return null;
  }, [enabledBatchActions.length, selectedItems.length, visibleBatchActions.length]);

  const previewItem = useMemo(
    () => items.find((item) => item.id === previewDocumentId) ?? null,
    [items, previewDocumentId],
  );

  const allVisibleSelected =
    filteredItems.length > 0 &&
    filteredItems.every((item) => selectedIds.includes(item.id));
  const partiallySelected =
    filteredItems.some((item) => selectedIds.includes(item.id)) && !allVisibleSelected;

  const withBusyIds = useCallback(
    async <T,>(documentIds: number[], work: () => Promise<T>): Promise<T> => {
      setBusyIds((current) => Array.from(new Set([...current, ...documentIds])));
      try {
        return await work();
      } finally {
        setBusyIds((current) => current.filter((id) => !documentIds.includes(id)));
      }
    },
    [],
  );

  const runSingleAction = useCallback(
    async (documentId: number, action: ReviewAction): Promise<boolean> => {
      return withBusyIds([documentId], async () => {
        try {
          const updates = await runReviewAction(documentId, action);
          setItems((current) => mergeUpdatedDocuments(current, updates));
          setSelectedIds((current) => current.filter((id) => id !== documentId));
          toast.success(reviewActionMeta[action].successMessage);
          return true;
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "操作失败");
          return false;
        }
      });
    },
    [withBusyIds],
  );

  const runBatchAction = useCallback(
    async (action: ReviewAction) => {
      if (selectedItems.length === 0) return;

      const actionableItems = selectedItems.filter((item) =>
        availableReviewActions(item).includes(action),
      );

      if (actionableItems.length === 0) {
        toast.error("当前选择没有可执行的批量动作");
        return;
      }

      const actionableIds = actionableItems.map((item) => item.id);
      setRunningBatchAction(action);

      await withBusyIds(actionableIds, async () => {
        const results = await Promise.allSettled(
          actionableIds.map((documentId) => runReviewAction(documentId, action)),
        );

        const succeeded = results
          .filter(
            (result): result is PromiseFulfilledResult<DocumentDetail[]> =>
              result.status === "fulfilled",
          )
          .flatMap((result) => result.value);

        const failed = results.filter((result) => result.status === "rejected");

        if (succeeded.length > 0) {
          setItems((current) => mergeUpdatedDocuments(current, succeeded));
          setSelectedIds((current) =>
            current.filter((id) => !succeeded.some((detail) => detail.id === id)),
          );
        }

        const fullySucceededCount = results.filter(
          (result) => result.status === "fulfilled",
        ).length;

        if (failed.length === 0) {
          toast.success(`已批量完成 ${fullySucceededCount} 篇文档的处理`);
        } else if (fullySucceededCount > 0) {
          toast.warning(
            `批量处理部分完成，完成 ${fullySucceededCount} 篇，失败 ${failed.length} 篇。`,
          );
        } else {
          const firstReason = failed[0];
          toast.error(
            firstReason.status === "rejected" && firstReason.reason instanceof Error
              ? firstReason.reason.message
              : "批量处理失败",
          );
        }
      });

      setRunningBatchAction(null);
    },
    [selectedItems, withBusyIds],
  );

  return (
    <div className="min-h-full bg-slate-50 px-6 py-8 sm:px-8">
      <Toaster position="top-right" richColors />

      <div className="mx-auto max-w-[1600px] space-y-6">
        <section className="overflow-hidden rounded-[32px] border border-slate-200/80 bg-white shadow-sm">
          <div className="bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.12),_transparent_28%),linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] px-6 py-6 sm:px-7">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <div className="text-xs font-medium uppercase tracking-[0.24em] text-amber-600">
                  Review Ops
                </div>
                <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">
                  审核与发布中心
                </h1>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-500">
                  管理知识库文档的生命周期，已发布的文档才会进入问答上下文。
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <Badge className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-600">
                    当前团队：{selectedTeam?.name ?? "未选择"}
                  </Badge>
                  {selectedIds.length > 0 ? (
                    <Badge className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-amber-700">
                      已选择 {selectedIds.length} 项
                    </Badge>
                  ) : null}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {enabledBatchActions.slice(0, 2).map((action) => (
                  <Button
                    key={action}
                    type="button"
                    disabled={selectedIds.length === 0 || runningBatchAction != null}
                    onClick={() => void runBatchAction(action)}
                    className="h-11 rounded-xl bg-slate-900 px-4 text-white hover:bg-slate-800"
                  >
                    {runningBatchAction === action ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        处理中
                      </>
                    ) : (
                      reviewActionMeta[action].batchLabel
                    )}
                  </Button>
                ))}

                <Button
                  type="button"
                  variant="outline"
                  disabled={loading || refreshing || teamsLoading}
                  onClick={() => void loadDocuments(true)}
                  className="h-11 rounded-xl border-slate-200 bg-white px-4 text-slate-700 hover:bg-slate-50"
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
          </div>
        </section>

        <section className="space-y-4 rounded-[32px] border border-slate-200/80 bg-white p-5 shadow-sm">
          <div className="overflow-x-auto">
            <Tabs
              value={activeFilter}
              onValueChange={(value) => setActiveFilter(value as ReviewFilter)}
            >
              <TabsList className="h-auto gap-2 rounded-2xl bg-slate-100/80 p-1.5">
                {REVIEW_FILTER_ORDER.map((filter) => (
                  <TabsTrigger
                    key={filter}
                    value={filter}
                    className="rounded-xl px-4 py-2.5 text-sm data-[state=active]:bg-white data-[state=active]:text-slate-900"
                  >
                    <span className="flex items-center gap-2">
                      <span>{reviewFilterLabels[filter]}</span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                        {summary[filter]}
                      </span>
                    </span>
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>

          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="relative w-full max-w-xl">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="按文档标题、知识库或分类搜索..."
                className="h-11 rounded-2xl border-slate-200 bg-slate-50 pl-10 text-slate-800 placeholder:text-slate-400"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
              <span>当前列表共 {filteredItems.length} 条</span>
              {(searchQuery || selectedIds.length > 0) && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setSearchQuery("");
                    setSelectedIds([]);
                  }}
                  className="h-10 rounded-xl px-3 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                >
                  <FilterX className="h-4 w-4" />
                  清空筛选
                </Button>
              )}
            </div>
          </div>

          {selectedIds.length > 0 ? (
            <BatchActionBar
              selectedCount={selectedIds.length}
              visibleActions={visibleBatchActions}
              enabledActions={enabledBatchActions}
              runningAction={runningBatchAction}
              disableReason={batchDisableReason}
              onRunAction={(action) => void runBatchAction(action)}
              onClearSelection={() => setSelectedIds([])}
            />
          ) : null}

          <ReviewTable
            items={filteredItems}
            loading={loading}
            selectedIds={selectedIds}
            allVisibleSelected={allVisibleSelected}
            partiallySelected={partiallySelected}
            onToggleSelect={(documentId, checked) => {
              setSelectedIds((current) =>
                checked
                  ? Array.from(new Set([...current, documentId]))
                  : current.filter((id) => id !== documentId),
              );
            }}
            onToggleSelectAll={(checked) => {
              if (!checked) {
                setSelectedIds((current) =>
                  current.filter((id) => !filteredItems.some((item) => item.id === id)),
                );
                return;
              }

              setSelectedIds((current) =>
                Array.from(new Set([...current, ...filteredItems.map((item) => item.id)])),
              );
            }}
            onOpenDocument={(item) => setPreviewDocumentId(item.id)}
            onRunAction={(documentId, action) => {
              void runSingleAction(documentId, action);
            }}
            busyIds={busyIds}
          />
        </section>
      </div>

      <ReviewDocumentSheet
        open={previewDocumentId != null}
        documentId={previewDocumentId}
        listItem={previewItem}
        busy={previewDocumentId != null && busyIds.includes(previewDocumentId)}
        onOpenChange={(open) => {
          if (!open) {
            setPreviewDocumentId(null);
          }
        }}
        onRunAction={runSingleAction}
      />
    </div>
  );
}
