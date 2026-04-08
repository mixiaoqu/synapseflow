"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  listDocumentCategories,
  type DocumentCategory,
} from "@/lib/api/documentCategories";
import {
  listKnowledgeBases,
  type KnowledgeBaseWithCount,
} from "@/lib/api/knowledgeBases";
import {
  kbChatApi,
  type KbChatRequest,
  type KbChatSessionDetail,
  type KbChatSessionMessage,
  type KbChatSessionSummary,
  type RetrievedDoc,
} from "@/lib/api/endpoints/kbChat";
import { getStoredUser } from "@/lib/auth/session";
import { consumeSseStream } from "@/lib/stream/sse";

const SESSION_LIST_LIMIT = 30;
const ACTIVE_SESSION_STORAGE_KEY = "synapseflow.kb-chat.active-session";

export interface KbChatTurn {
  id: string;
  query: string;
  answer: string;
  retrievedDocs: RetrievedDoc[];
  error: string | null;
}

function buildActiveSessionStorageKey(): string {
  const user = getStoredUser();
  return user ? `${ACTIVE_SESSION_STORAGE_KEY}.${user.id}` : ACTIVE_SESSION_STORAGE_KEY;
}

function readStoredActiveSessionId(storageKey: string): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(storageKey);
}

function writeStoredActiveSessionId(storageKey: string, sessionId: string | null) {
  if (typeof window === "undefined") return;
  if (sessionId) {
    window.localStorage.setItem(storageKey, sessionId);
    return;
  }
  window.localStorage.removeItem(storageKey);
}

function buildTurnId(sessionId: string, index: number): string {
  return `${sessionId}-${index}`;
}

function toTurns(
  sessionId: string,
  messages: KbChatSessionMessage[],
): KbChatTurn[] {
  const turns: KbChatTurn[] = [];
  let currentTurn: KbChatTurn | null = null;

  messages.forEach((message, index) => {
    const role = message.role.trim().toLowerCase();
    const content = message.content.trim();
    if (!content) return;

    if (role === "user") {
      if (currentTurn) {
        turns.push(currentTurn);
      }
      currentTurn = {
        id: buildTurnId(sessionId, index),
        query: content,
        answer: "",
        retrievedDocs: [],
        error: null,
      };
      return;
    }

    if (role === "assistant") {
      if (!currentTurn) {
        currentTurn = {
          id: buildTurnId(sessionId, index),
          query: "",
          answer: content,
          retrievedDocs: [],
          error: null,
        };
        return;
      }
      currentTurn = {
        ...currentTurn,
        answer: currentTurn.answer ? `${currentTurn.answer}\n\n${content}` : content,
      };
    }
  });

  if (currentTurn) {
    turns.push(currentTurn);
  }

  return turns.filter((turn) => turn.query || turn.answer);
}

function mergeSessionSummary(
  current: KbChatSessionSummary | null,
  detail: KbChatSessionDetail,
): KbChatSessionSummary {
  return {
    session_id: detail.session_id,
    title: detail.title,
    preview: detail.preview ?? current?.preview ?? null,
    knowledge_base_id: detail.knowledge_base_id ?? current?.knowledge_base_id ?? null,
    knowledge_base_name: detail.knowledge_base_name ?? current?.knowledge_base_name ?? null,
    category_id: detail.category_id ?? current?.category_id ?? null,
    category_name: detail.category_name ?? current?.category_name ?? null,
    message_count: detail.message_count,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
  };
}

export function useKbChat() {
  const [query, setQuery] = useState("");
  const [knowledgeBaseId, setKnowledgeBaseId] = useState<number | null>(null);
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseWithCount[]>([]);
  const [categories, setCategories] = useState<DocumentCategory[]>([]);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [turns, setTurns] = useState<KbChatTurn[]>([]);
  const [sessions, setSessions] = useState<KbChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());
  const [mobileTab, setMobileTab] = useState<"chat" | "sources">("chat");

  const activeTurnIdRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const hasRestoredSessionRef = useRef(false);
  const storageKeyRef = useRef<string>(buildActiveSessionStorageKey());

  const loading = submitLoading || sessionLoading;

  const persistActiveSessionId = useCallback((sessionId: string | null) => {
    writeStoredActiveSessionId(storageKeyRef.current, sessionId);
  }, []);

  const loadKnowledgeBases = useCallback(async () => {
    try {
      setKnowledgeBases(await listKnowledgeBases());
    } catch {
      /* ignore */
    }
  }, []);

  const loadSessions = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setHistoryLoading(true);
    }

    try {
      setSessions(await kbChatApi.listSessions(SESSION_LIST_LIMIT));
    } catch {
      if (!options?.silent) {
        toast.error("加载历史会话失败");
      }
    } finally {
      if (!options?.silent) {
        setHistoryLoading(false);
      }
    }
  }, []);

  const resetConversation = useCallback(() => {
    setTurns([]);
    setExpandedChunks(new Set());
    setMobileTab("chat");
    setActiveSessionId(null);
    sessionIdRef.current = null;
    persistActiveSessionId(null);
  }, [persistActiveSessionId]);

  const openSession = useCallback(
    async (sessionId: string) => {
      if (!sessionId) return false;

      setSessionLoading(true);
      setMobileTab("chat");

      try {
        const detail = await kbChatApi.getSession(sessionId);
        const nextSummary = mergeSessionSummary(
          sessions.find((item) => item.session_id === sessionId) ?? null,
          detail,
        );

        setSessions((prev) => {
          const exists = prev.some((item) => item.session_id === sessionId);
          if (!exists) {
            return [nextSummary, ...prev];
          }
          return prev.map((item) => (item.session_id === sessionId ? nextSummary : item));
        });
        setTurns(toTurns(detail.session_id, detail.messages));
        setExpandedChunks(new Set());
        setActiveSessionId(detail.session_id);
        sessionIdRef.current = detail.session_id;
        persistActiveSessionId(detail.session_id);
        setKnowledgeBaseId(detail.knowledge_base_id ?? null);
        setCategoryId(detail.category_id ?? null);
        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : "加载会话失败";
        toast.error(message);
        return false;
      } finally {
        setSessionLoading(false);
      }
    },
    [persistActiveSessionId, sessions],
  );

  useEffect(() => {
    void loadKnowledgeBases();
    void loadSessions();
  }, [loadKnowledgeBases, loadSessions]);

  useEffect(() => {
    if (!knowledgeBaseId || knowledgeBaseId <= 0) {
      setCategories([]);
      setCategoryId(null);
      return;
    }

    let cancelled = false;

    const run = async () => {
      try {
        const items = await listDocumentCategories(knowledgeBaseId);
        if (cancelled) return;
        setCategories(items);
        setCategoryId((prev) =>
          prev && items.some((item) => item.id === prev) ? prev : null,
        );
      } catch {
        if (!cancelled) {
          setCategories([]);
          setCategoryId(null);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [knowledgeBaseId]);

  useEffect(() => {
    if (historyLoading || hasRestoredSessionRef.current) return;

    hasRestoredSessionRef.current = true;
    const storedSessionId = readStoredActiveSessionId(storageKeyRef.current);
    if (storedSessionId && sessions.some((item) => item.session_id === storedSessionId)) {
      void openSession(storedSessionId);
      return;
    }

    if (storedSessionId) {
      persistActiveSessionId(null);
    }

    if (sessions.length > 0) {
      void openSession(sessions[0].session_id);
    }
  }, [historyLoading, openSession, persistActiveSessionId, sessions]);

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

  const activeSession = useMemo(
    () => sessions.find((item) => item.session_id === activeSessionId) ?? null,
    [activeSessionId, sessions],
  );

  const knowledgeBaseLabel = useMemo(() => {
    if (knowledgeBaseId && knowledgeBaseId > 0) {
      const kbLabel =
        knowledgeBases.find((kb) => kb.id === knowledgeBaseId)?.name ??
        activeSession?.knowledge_base_name ??
        "Selected knowledge base";
      if (categoryId && categoryId > 0) {
        const categoryLabel =
          categories.find((item) => item.id === categoryId)?.name ??
          activeSession?.category_name ??
          "Selected category";
        return `${kbLabel} / ${categoryLabel}`;
      }
      return kbLabel;
    }
    return "All knowledge bases";
  }, [activeSession, categories, categoryId, knowledgeBaseId, knowledgeBases]);

  const expandAllChunks = useCallback(() => {
    if (!lastTurn?.retrievedDocs.length) return;
    setExpandedChunks(new Set(lastTurn.retrievedDocs.map((_, i) => `${lastTurn.id}-${i}`)));
  }, [lastTurn]);

  const collapseAllChunks = useCallback(() => setExpandedChunks(new Set()), []);

  const submit = useCallback(
    async (request?: Partial<KbChatRequest> & { query?: string }) => {
      const nextQuery = request?.query?.trim() ?? query.trim();
      const nextKnowledgeBaseId =
        request?.knowledge_base_id !== undefined
          ? request.knowledge_base_id
          : knowledgeBaseId;
      const nextCategoryId =
        request?.category_id !== undefined ? request.category_id : categoryId;

      if (!nextQuery || loading) return false;

      const turnId = crypto.randomUUID();
      let completed = false;

      activeTurnIdRef.current = turnId;
      setSubmitLoading(true);
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
          category_id: nextCategoryId && nextCategoryId > 0 ? nextCategoryId : null,
          session_id: sessionIdRef.current,
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
              completed = true;
              const answer = event.data.answer;
              const docs = event.data.retrieved_docs;
              const sessionId = event.data.session_id;
              if (typeof sessionId === "string" && sessionId) {
                sessionIdRef.current = sessionId;
                setActiveSessionId(sessionId);
                persistActiveSessionId(sessionId);
              }
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

        if (completed) {
          await loadSessions({ silent: true });
        }
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
        setSubmitLoading(false);
        activeTurnIdRef.current = null;
      }
    },
    [categoryId, knowledgeBaseId, loadSessions, loading, persistActiveSessionId, query],
  );

  return {
    query,
    setQuery,
    knowledgeBaseId,
    setKnowledgeBaseId,
    categoryId,
    setCategoryId,
    knowledgeBases,
    categories,
    loading,
    submitLoading,
    sessionLoading,
    historyLoading,
    turns,
    sessions,
    activeSessionId,
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
    openSession,
    submit,
  };
}
