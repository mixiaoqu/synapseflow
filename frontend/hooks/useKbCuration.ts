"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { listCollections, type CollectionWithCount } from "@/lib/api/collections";
import { reindexAll } from "@/lib/api/documents";
import {
  kbCurationApi,
  type DocumentIssue,
  type IterationRecord,
  type KbCurationResponse,
} from "@/lib/api/endpoints/kbCuration";
import type { RetrievedDoc } from "@/lib/api/endpoints/kbChat";

export const PASS_SCORE = 0.75;

export interface KbCurationResult extends KbCurationResponse {}

export function getUniqueDocumentNames(docs: RetrievedDoc[]): string[] {
  const names = new Map<number, string>();
  docs.forEach((doc) => {
    const id = doc.metadata?.document_id;
    const title = doc.metadata?.document_title;
    if (id != null && title && !names.has(id)) {
      names.set(id, title);
    }
  });
  return Array.from(names.values());
}

export function getRoundDocumentIssues(
  round: number,
  documentIssues: DocumentIssue[],
): DocumentIssue[] {
  if (!documentIssues.length) return [];
  return documentIssues.filter((issue) => issue.round === round);
}

export function useKbCuration() {
  const [query, setQuery] = useState("");
  const [maxIterations, setMaxIterations] = useState(3);
  const [collectionId, setCollectionId] = useState<number | null>(null);
  const [collections, setCollections] = useState<CollectionWithCount[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<KbCurationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [expandedRounds, setExpandedRounds] = useState<Set<number>>(new Set());

  const loadCollections = useCallback(async () => {
    try {
      setCollections(await listCollections());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void loadCollections();
  }, [loadCollections]);

  useEffect(() => {
    if (result?.iteration_history?.length) {
      setExpandedRounds(new Set(result.iteration_history.map((item) => item.round)));
    } else {
      setExpandedRounds(new Set());
    }
  }, [result]);

  const docNames = useMemo(
    () => (result ? getUniqueDocumentNames(result.retrieved_docs) : []),
    [result],
  );

  const toggleRound = useCallback((round: number) => {
    setExpandedRounds((prev) => {
      const next = new Set(prev);
      if (next.has(round)) next.delete(round);
      else next.add(round);
      return next;
    });
  }, []);

  const expandAll = useCallback(() => {
    if (result?.iteration_history?.length) {
      setExpandedRounds(new Set(result.iteration_history.map((item) => item.round)));
    }
  }, [result]);

  const collapseAll = useCallback(() => setExpandedRounds(new Set()), []);

  const submit = useCallback(async () => {
    if (!query.trim() || loading) return false;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await kbCurationApi.invoke({
        query: query.trim(),
        max_iterations: maxIterations,
        collection_id: collectionId && collectionId > 0 ? collectionId : null,
      });

      setResult(response);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "请求失败，请重试";
      setError(message);
      toast.error(message);
      return false;
    } finally {
      setLoading(false);
    }
  }, [collectionId, loading, maxIterations, query]);

  const triggerReindex = useCallback(async () => {
    setReindexing(true);
    try {
      const res = await reindexAll();
      toast.success(res.message || `已重建 ${res.indexed} 篇文档索引`);
      if (res.indexed > 0) {
        toast.info("请重新提问以获取最新检索结果");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "重建索引失败");
    } finally {
      setReindexing(false);
    }
  }, []);

  return {
    query,
    setQuery,
    maxIterations,
    setMaxIterations,
    collectionId,
    setCollectionId,
    collections,
    loading,
    result,
    error,
    reindexing,
    expandedRounds,
    docNames,
    toggleRound,
    expandAll,
    collapseAll,
    submit,
    triggerReindex,
  };
}

export type { DocumentIssue, IterationRecord, RetrievedDoc };
