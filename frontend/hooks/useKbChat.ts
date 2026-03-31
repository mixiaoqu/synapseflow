"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { listCollections, type CollectionWithCount } from "@/lib/api/collections";
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
  const [collectionId, setCollectionId] = useState<number | null>(null);
  const [collections, setCollections] = useState<CollectionWithCount[]>([]);
  const [loading, setLoading] = useState(false);
  const [turns, setTurns] = useState<KbChatTurn[]>([]);
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());
  const [mobileTab, setMobileTab] = useState<"chat" | "sources">("chat");

  const activeTurnIdRef = useRef<string | null>(null);

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

  const collectionLabel = useMemo(() => {
    if (collectionId && collectionId > 0) {
      return collections.find((c) => c.id === collectionId)?.name ?? "指定集合";
    }
    return "全部知识库";
  }, [collectionId, collections]);

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
      const nextCollectionId =
        request?.collection_id !== undefined ? request.collection_id : collectionId;

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
          collection_id:
            nextCollectionId && nextCollectionId > 0 ? nextCollectionId : null,
        });

        await consumeSseStream(stream, (event) => {
          const tid = activeTurnIdRef.current;
          if (!tid) return;

          switch (event.type) {
            case "retrieved": {
              const docs = event.data.retrieved_docs;
              if (Array.isArray(docs)) {
                setTurns((prev) =>
                  prev.map((turn) =>
                    turn.id === tid
                      ? { ...turn, retrievedDocs: docs as RetrievedDoc[] }
                      : turn,
                  ),
                );
              }
              break;
            }
            case "token": {
              const text = event.data.text;
              if (typeof text === "string" && text) {
                setTurns((prev) =>
                  prev.map((turn) =>
                    turn.id === tid
                      ? { ...turn, answer: turn.answer + text }
                      : turn,
                  ),
                );
              }
              break;
            }
            case "error": {
              const message = String(event.data.message ?? "流式问答失败");
              setTurns((prev) =>
                prev.map((turn) =>
                  turn.id === tid ? { ...turn, error: message } : turn,
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
        const message = error instanceof Error ? error.message : "请求失败";
        const tid = activeTurnIdRef.current;
        if (tid) {
          setTurns((prev) =>
            prev.map((turn) =>
              turn.id === tid ? { ...turn, error: message } : turn,
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
    [collectionId, loading, query],
  );

  return {
    query,
    setQuery,
    collectionId,
    setCollectionId,
    collections,
    loading,
    turns,
    expandedChunks,
    mobileTab,
    setMobileTab,
    collectionLabel,
    lastTurn,
    sourceDocs,
    toggleChunk,
    expandAllChunks,
    collapseAllChunks,
    resetConversation,
    submit,
  };
}
