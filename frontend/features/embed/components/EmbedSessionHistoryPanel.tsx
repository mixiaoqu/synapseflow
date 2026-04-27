"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "next/navigation";
import {
  Bot,
  Clock,
  Loader2,
  MessageSquare,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import type { AskSessionSummary } from "@/lib/api/endpoints/ask";
import { embedApi } from "@/lib/api/endpoints/embed";
import { cn } from "@/lib/utils";
import type { Session } from "../hooks/useEmbeddedAssistant";

const SESSION_LIST_LIMIT = 30;

interface EmbedSessionHistoryPanelProps {
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
}

function toSession(item: AskSessionSummary): Session {
  return {
    id: item.session_id,
    title: item.title || "新对话",
    createdAt: item.updated_at || item.created_at,
    preview: item.preview ?? null,
  };
}

function formatPanelError(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function formatSessionTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  if (diffMs >= 0 && diffMs < 60 * 1000) return "刚刚";
  if (diffMs >= 0 && diffMs < 60 * 60 * 1000) {
    return `${Math.max(1, Math.floor(diffMs / 60000))} 分钟前`;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function EmbedSessionHistoryPanel({
  currentSessionId,
  onSelectSession,
  onNewSession,
}: EmbedSessionHistoryPanelProps) {
  const searchParams = useSearchParams();
  const token = searchParams.get("token")?.trim() || "";

  const [isOpen, setIsOpen] = useState(false);
  const [historyKeyword, setHistoryKeyword] = useState("");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);

  const filteredSessions = useMemo(() => {
    const keyword = historyKeyword.trim().toLowerCase();
    if (!keyword) return sessions;
    return sessions.filter(
      (session) =>
        session.title.toLowerCase().includes(keyword) ||
        (session.preview ?? "").toLowerCase().includes(keyword),
    );
  }, [historyKeyword, sessions]);

  const loadSessions = useCallback(async () => {
    if (!token) return;

    setIsLoading(true);
    setError(null);
    try {
      const response = await embedApi.listSessions(token, SESSION_LIST_LIMIT);
      setSessions(response.map(toSession));
    } catch (err) {
      setError(formatPanelError(err, "加载历史会话失败"));
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!isOpen) return;
    void loadSessions();
  }, [isOpen, loadSessions]);

  const handleSelect = (sessionId: string) => {
    onSelectSession(sessionId);
    setIsOpen(false);
  };

  const handleDelete = async (sessionId: string) => {
    if (!sessionId || !token || deletingSessionId) return;

    setDeletingSessionId(sessionId);
    setError(null);
    try {
      await embedApi.deleteSession(token, sessionId);
      setSessions((current) => current.filter((session) => session.id !== sessionId));
      if (currentSessionId === sessionId) {
        onNewSession();
      }
    } catch (err) {
      setError(formatPanelError(err, "删除会话失败"));
    } finally {
      setDeletingSessionId(null);
    }
  };

  const overlay = (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[9999]">
            {/* Backdrop — animated, blurred */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="absolute inset-0 bg-slate-900/20 backdrop-blur-[2px]"
              onClick={() => setIsOpen(false)}
            />

            {/* Panel — spring slide-in from right */}
            <motion.aside
              initial={{ x: "100%", opacity: 0.6 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: "100%", opacity: 0 }}
              transition={{ type: "spring", stiffness: 320, damping: 32 }}
              style={{
                width: "clamp(280px, 44vw, 400px)",
                maxWidth: "calc(100vw - 12px)",
              }}
              className="absolute bottom-2 right-2 top-2 flex flex-col overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-2xl shadow-slate-300/40"
            >
              {/* 4. Panel header */}
              <div className="shrink-0 border-b border-slate-100 bg-white px-4 pb-3 pt-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow shadow-blue-200">
                      <Clock className="h-3.5 w-3.5 text-white" />
                    </div>
                    <span className="text-[14px] font-semibold text-slate-800">历史会话</span>
                    {sessions.length > 0 && (
                      <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-500">
                        {sessions.length}
                      </span>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setIsOpen(false)}
                    className="h-7 w-7 rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                    title="关闭历史会话"
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>

                {/* Search */}
                <div className="relative mt-3">
                  <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    value={historyKeyword}
                    onChange={(event) => setHistoryKeyword(event.target.value)}
                    placeholder="搜索历史会话..."
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-8 pr-4 text-[13px] outline-none transition-all focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-500/15"
                  />
                </div>
              </div>

              {/* Session list */}
              <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
                <AnimatePresence>
                  {error ? (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="mb-2 rounded-xl border border-red-100 bg-red-50 px-3 py-2 text-[12px] text-red-600"
                    >
                      {error}
                    </motion.div>
                  ) : null}
                </AnimatePresence>

                {isLoading ? (
                  <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                    <Loader2 className="mb-3 h-6 w-6 animate-spin text-blue-500" />
                    <p className="text-[12px]">加载中...</p>
                  </div>
                ) : filteredSessions.length === 0 ? (
                  /* 6. Empty state */
                  <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                    <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100">
                      <MessageSquare className="h-6 w-6 opacity-40" />
                    </div>
                    <p className="text-[13px] font-medium text-slate-500">
                      {sessions.length === 0 ? "暂无历史对话" : "没有匹配的会话"}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-400">
                      {sessions.length === 0 ? "开始第一次对话吧" : "换个关键词试试"}
                    </p>
                  </div>
                ) : (
                  /* 5. Session items */
                  <div className="space-y-1.5">
                    <AnimatePresence initial={false}>
                      {filteredSessions.map((session, index) => (
                        <motion.div
                          key={session.id}
                          initial={{ opacity: 0, x: 12 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: -8, height: 0 }}
                          transition={{ delay: index * 0.03, duration: 0.2 }}
                          className={cn(
                            "group relative flex items-start gap-2 rounded-xl border px-3 py-2.5 transition-all",
                            currentSessionId === session.id
                              ? "border-blue-200 bg-blue-50"
                              : "border-transparent bg-transparent hover:border-slate-200 hover:bg-slate-50",
                          )}
                        >
                          <button
                            type="button"
                            onClick={() => handleSelect(session.id)}
                            className="flex min-w-0 flex-1 items-start gap-2.5 text-left"
                          >
                            <div
                              className={cn(
                                "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors",
                                currentSessionId === session.id
                                  ? "bg-blue-100 text-blue-600"
                                  : "bg-slate-100 text-slate-500 group-hover:bg-blue-100 group-hover:text-blue-600",
                              )}
                            >
                              <Bot className="h-3.5 w-3.5" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div
                                className={cn(
                                  "truncate text-[13px] font-medium leading-5",
                                  currentSessionId === session.id
                                    ? "text-blue-700"
                                    : "text-slate-700",
                                )}
                              >
                                {session.title}
                              </div>
                              {session.preview && (
                                <div className="mt-0.5 truncate text-[11px] leading-4 text-slate-400">
                                  {session.preview}
                                </div>
                              )}
                              <div className="mt-1 text-[10px] text-slate-400">
                                {formatSessionTime(session.createdAt)}
                              </div>
                            </div>
                          </button>

                          {/* Delete button — Trash2 icon */}
                          <Button
                            variant="ghost"
                            size="icon"
                            disabled={deletingSessionId === session.id}
                            onClick={() => void handleDelete(session.id)}
                            title="删除会话"
                            className="h-6 w-6 shrink-0 self-center rounded-lg text-slate-300 opacity-0 hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 disabled:opacity-40"
                          >
                            {deletingSessionId === session.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Trash2 className="h-3 w-3" />
                            )}
                          </Button>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                )}
              </div>

              {/* 7. Footer — dashed new session button */}
              <div className="shrink-0 border-t border-slate-100 px-3 py-3">
                <button
                  type="button"
                  onClick={() => {
                    onNewSession();
                    setIsOpen(false);
                  }}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-blue-300 bg-blue-50/50 py-2.5 text-[13px] font-medium text-blue-600 transition-all hover:border-blue-400 hover:bg-blue-100/60 hover:shadow-sm active:scale-[0.99]"
                >
                  <Plus className="h-4 w-4" />
                  新建会话
                </button>
              </div>
            </motion.aside>
          </div>
        )}
      </AnimatePresence>
  );

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setIsOpen(true)}
        className="h-8 w-8 rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        title="历史会话"
      >
        <Clock className="h-4 w-4" />
      </Button>
      {typeof document !== "undefined" ? createPortal(overlay, document.body) : null}
    </>
  );
}
