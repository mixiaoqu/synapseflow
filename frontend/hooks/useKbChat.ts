"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  listKnowledgeBases,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import {
  kbChatApi,
  type KbChatRequest,
  type RetrievedDoc,
} from "@/lib/api/endpoints/kbChat";
import { consumeSseStream } from "@/lib/stream/sse";

export interface KbChatTurn {
  id: string;
  query: string;
  answer: string;
  retrievedDocs: RetrievedDoc[];
  error: string | null;
}

export function useKbChat() {
  const [query, setQuery] = useState("");
  const [knowledgeBaseId, setKnowledgeBaseId] = useState<number | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [loading, setLoading] = useState(false);
  const [turns, setTurns] = useState<KbChatTurn[]>([]);
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());
  const [mobileTab, setMobileTab] = useState<"chat" | "sources">("chat");

  const activeTurnIdRef = useRef<string | null>(null);

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

  const toggleChunk = useCallback((key: string) => {
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const lastTurn = useMemo(
    () => (turns.length > 0 ? turns[turns.length - 1] : null),
    [turns],
  );

  const sourceDocs = lastTurn?.retrievedDocs ?? [];

  const knowledgeBaseLabel = useMemo(() => {
    if (knowledgeBaseId && knowledgeBaseId > 0) {
      return (
        knowledgeBases.find((kb) => kb.id === knowledgeBaseId)?.name ??
        "Selected knowledge base"
      );
    }
    return "All knowledge bases";
  }, [knowledgeBaseId, knowledgeBases]);

  const expandAllChunks = useCallback(() => {
    if (!lastTurn?.retrievedDocs.length) return;
    setExpandedChunks(new Set(lastTurn.retrievedDocs.map((_, i) => `${lastTurn.id}-${i}`)));
  }, [lastTurn]);

  const collapseAllChunks = useCallback(() => setExpandedChunks(new Set()), []);

  const resetConversation = useCallback(() => {
    setTurns([]);
    setExpandedChunks(new Set());
    setMobileTab("chat");
  }, []);

  const submit = useCallback(
    async (request?: Partial<KbChatRequest> & { query?: string }) => {
      const nextQuery = request?.query?.trim() ?? query.trim();
      const nextKnowledgeBaseId =
        request?.knowledge_base_id !== undefined
          ? request.knowledge_base_id
          : knowledgeBaseId;

      if (!nextQuery || loading) return false;

      const turnId = crypto.randomUUID();
      activeTurnIdRef.current = turnId;
      setLoading(true);
      setQuery("");
      setMobileTab("chat");
      setExpandedChunks(new Set());
      setTurns((prev) => [
        ...prev,
        { id: turnId, query: nextQuery, answer: "", retrievedDocs: [], error: null },
      ]);

      try {
        const stream = await kbChatApi.stream({
          query: nextQuery,
          knowledge_base_id:
            nextKnowledgeBaseId && nextKnowledgeBaseId > 0 ? nextKnowledgeBaseId : null,
        });

        await consumeSseStream(stream, (event) => {
          const turnIdForUpdate = activeTurnIdRef.current;
          if (!turnIdForUpdate) return;

          switch (event.type) {
            case "retrieved": {
              const docs = event.data.retrieved_docs;
              if (Array.isArray(docs)) {
                setTurns((prev) =>
                  prev.map((turn) =>
                    turn.id === turnIdForUpdate
                      ? { ...turn, retrievedDocs: docs as RetrievedDoc[] }
                      : turn,
                  ),
                );
              }
              break;
            }
            case "complete": {
              const answer = event.data.answer;
              const docs = event.data.retrieved_docs;
              setTurns((prev) =>
                prev.map((turn) =>
                  turn.id === turnIdForUpdate
                    ? {
                        ...turn,
                        answer: typeof answer === "string" ? answer : turn.answer,
                        retrievedDocs: Array.isArray(docs)
                          ? (docs as RetrievedDoc[])
                          : turn.retrievedDocs,
                      }
                    : turn,
                ),
              );
              break;
            }
            case "token": {
              const text = event.data.text;
              if (typeof text === "string" && text) {
                setTurns((prev) =>
                  prev.map((turn) =>
                    turn.id === turnIdForUpdate
                      ? { ...turn, answer: turn.answer + text }
                      : turn,
                  ),
                );
              }
              break;
            }
            case "error": {
              const message = String(event.data.message ?? "Streaming request failed");
              setTurns((prev) =>
                prev.map((turn) =>
                  turn.id === turnIdForUpdate ? { ...turn, error: message } : turn,
                ),
              );
              toast.error(message);
              break;
            }
            default:
              break;
          }
        });

        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : "Request failed";
        const turnIdForUpdate = activeTurnIdRef.current;
        if (turnIdForUpdate) {
          setTurns((prev) =>
            prev.map((turn) =>
              turn.id === turnIdForUpdate ? { ...turn, error: message } : turn,
            ),
          );
        }
        toast.error(message);
        return false;
      } finally {
        setLoading(false);
        activeTurnIdRef.current = null;
      }
    },
    [knowledgeBaseId, loading, query],
  );

  return {
    query,
    setQuery,
    knowledgeBaseId,
    setKnowledgeBaseId,
    knowledgeBases,
    loading,
    turns,
    expandedChunks,
    mobileTab,
    setMobileTab,
    knowledgeBaseLabel,
    lastTurn,
    sourceDocs,
    toggleChunk,
    expandAllChunks,
    collapseAllChunks,
    resetConversation,
    submit,
  };
}
