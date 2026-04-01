"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  listKnowledgeBases,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
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
  const [knowledgeBaseId, setKnowledgeBaseId] = useState<number | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<KbCurationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [expandedRounds, setExpandedRounds] = useState<Set<number>>(new Set());

  const loadKnowledgeBases = useCallback(async () => {
    try {
      setKnowledgeBases(await listKnowledgeBases());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void loadKnowledgeBases();
  }, [loadKnowledgeBases]);

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
        knowledge_base_id: knowledgeBaseId && knowledgeBaseId > 0 ? knowledgeBaseId : null,
      });

      setResult(response);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Request failed";
      setError(message);
      toast.error(message);
      return false;
    } finally {
      setLoading(false);
    }
  }, [knowledgeBaseId, loading, maxIterations, query]);

  const triggerReindex = useCallback(async () => {
    setReindexing(true);
    try {
      const res = await reindexAll();
      toast.success(res.message || `Reindexed ${res.indexed} documents`);
      if (res.indexed > 0) {
        toast.info("Run the question again to get the latest retrieval result.");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Reindex failed");
    } finally {
      setReindexing(false);
    }
  }, []);

  return {
    query,
    setQuery,
    maxIterations,
    setMaxIterations,
    knowledgeBaseId,
    setKnowledgeBaseId,
    knowledgeBases,
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
