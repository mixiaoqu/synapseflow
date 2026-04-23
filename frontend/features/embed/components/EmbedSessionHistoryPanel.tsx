"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Bot, Loader2, MessageSquare, Plus, Search, Trash, X } from "lucide-react";

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

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setIsOpen(true)}
        className="h-8 w-8 rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-700"
        title="历史会话"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-4 w-4"
        >
          <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
          <path d="M3 3v5h5" />
          <path d="M12 7v5l4 2" />
        </svg>
      </Button>

      {isOpen ? (
        <div className="fixed inset-0 z-40">
          <button
            type="button"
            aria-label="关闭历史会话"
            className="absolute inset-0 bg-slate-950/20"
            onClick={() => setIsOpen(false)}
          />
          <aside
            style={{
              width: "clamp(280px, 42vw, 420px)",
              maxWidth: "calc(100vw - 16px)",
            }}
            className="absolute bottom-2 right-2 top-16 flex min-w-0 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-2xl"
          >
            <div className="shrink-0 border-b border-slate-100 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-base font-semibold text-slate-800">历史会话</div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsOpen(false)}
                  className="h-7 w-7 rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  title="关闭历史会话"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="relative mt-3">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={historyKeyword}
                  onChange={(event) => setHistoryKeyword(event.target.value)}
                  placeholder="搜索历史会话..."
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm outline-none transition-all focus:border-blue-500 focus:bg-white focus:ring-1 focus:ring-blue-500/20"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {error ? (
                <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">
                  {error}
                </div>
              ) : null}

              {isLoading ? (
                <div className="flex items-center justify-center py-12 text-slate-400">
                  <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                </div>
              ) : filteredSessions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                  <MessageSquare className="mb-4 h-10 w-10 opacity-20" />
                  <p className="text-sm">
                    {sessions.length === 0 ? "暂无历史对话" : "没有匹配的会话"}
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredSessions.map((session) => (
                    <div
                      key={session.id}
                      className={cn(
                        "group flex items-start gap-2 rounded-xl border border-transparent p-2 transition-all",
                        currentSessionId === session.id
                          ? "bg-blue-50"
                          : "hover:border-slate-100 hover:bg-slate-50",
                      )}
                    >
                      <button
                        type="button"
                        onClick={() => handleSelect(session.id)}
                        className="flex min-w-0 flex-1 items-start gap-3 text-left"
                      >
                        <div className="mt-0.5 rounded-lg bg-blue-50 p-1.5">
                          <Bot className="h-4 w-4 text-blue-600" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-[14px] font-medium text-slate-800">
                            {session.title}
                          </div>
                          {session.preview && (
                            <div className="mt-0.5 truncate text-[12px] text-slate-500">
                              {session.preview}
                            </div>
                          )}
                          <div className="mt-1 text-[12px] text-slate-400">
                            {formatSessionTime(session.createdAt)}
                          </div>
                        </div>
                      </button>
                      <Button
                        variant="ghost"
                        size="icon"
                        disabled={deletingSessionId === session.id}
                        className="h-7 w-7 shrink-0 rounded-md text-slate-400 opacity-0 hover:bg-red-50 hover:text-red-600 group-hover:opacity-100"
                        onClick={() => void handleDelete(session.id)}
                        title="删除会话"
                      >
                        {deletingSessionId === session.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="border-t border-slate-200 p-4">
              <Button
                onClick={() => {
                  onNewSession();
                  setIsOpen(false);
                }}
                variant="outline"
                className="h-10 w-full justify-center gap-2 rounded-xl bg-white text-slate-600 hover:bg-slate-50"
              >
                <Plus className="h-4 w-4" />
                新建会话
              </Button>
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}
