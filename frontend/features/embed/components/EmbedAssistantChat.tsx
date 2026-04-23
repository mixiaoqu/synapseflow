"use client";

import { useEffect, useRef, useState } from "react";
import {
  Bot,
  CheckCircle2,
  Copy,
  FileText,
  Loader2,
  MessageSquare,
  SendHorizontal,
  Square,
  ThumbsDown,
  ThumbsUp,
  X,
  Zap,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { AnswerMarkdown } from "@/components/ask/AnswerMarkdown";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { useEmbeddedAssistant } from "../hooks/useEmbeddedAssistant";
import { EmbedSessionHistoryPanel } from "./EmbedSessionHistoryPanel";

function getDocTitle(doc: { metadata?: Record<string, unknown> }): string {
  const title = doc.metadata?.document_title;
  if (typeof title === "string" && title.trim()) return title.trim();
  const sourcePath = doc.metadata?.source_path;
  if (typeof sourcePath === "string" && sourcePath.trim()) {
    return sourcePath.split(/[\\/]/).filter(Boolean).pop() || sourcePath;
  }
  return "知识库片段";
}

export function EmbedAssistantChat() {
  const {
    assistantName,
    isInitializing,
    messages,
    isTyping,
    streamStatus,
    retrievedCount: rawRetrievedCount,
    currentSessionId,
    greeting,
    placeholder,
    suggestions,
    contextLabel,
    error,
    scrollRef,
    handleSendMessage,
    handleStopGenerating,
    handleNewSession,
    handleSelectSession,
    handleSubmitFeedback,
  } = useEmbeddedAssistant();
  const retrievedCount = rawRetrievedCount ?? 0;

  const [inputValue, setInputValue] = useState("");
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = "auto";
    inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`;
  }, [inputValue]);

  const onSend = () => {
    const query = inputValue.trim();
    if (!query || isTyping) return;
    void handleSendMessage(query);
    setInputValue("");
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  };

  const handleCopy = async (messageId: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMessageId(messageId);
      window.setTimeout(() => setCopiedMessageId(null), 1200);
    } catch {
      setCopiedMessageId(null);
    }
  };

  const requestClose = () => {
    window.parent?.postMessage({ type: "synapseflow.embed.close" }, "*");
  };

  if (isInitializing) {
    return (
      <div className="flex h-[100dvh] w-full items-center justify-center bg-white">
        <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="relative flex h-[100dvh] w-full flex-col overflow-hidden bg-[#f7f8fa]">
      <header className="z-20 flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-blue-600">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <span className="truncate text-[15px] font-semibold text-slate-900">
            {assistantName}
          </span>
          <span className="rounded bg-blue-600 px-1.5 py-0.5 text-[10px] font-medium text-white">
            AI
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <EmbedSessionHistoryPanel
            currentSessionId={currentSessionId}
            onSelectSession={(sessionId) => void handleSelectSession(sessionId)}
            onNewSession={handleNewSession}
          />
          <Button
            variant="ghost"
            size="icon"
            onClick={requestClose}
            className="h-8 w-8 rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            title="关闭"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {contextLabel ? (
          <div className="shrink-0 border-b border-slate-200 bg-[#f8f9fa] px-4 py-3">
            <div className="text-xs font-medium text-blue-600">当前应用</div>
            <div className="mt-1 truncate text-sm text-slate-700">{contextLabel}</div>
          </div>
        ) : null}

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-smooth">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6 sm:px-5 lg:max-w-4xl">
              {messages.length === 0 && (
                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-600">
                      <Bot className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-[15px] font-semibold text-slate-900">
                        {assistantName}
                      </div>
                      <p className="mt-2 whitespace-pre-wrap text-[14px] leading-6 text-slate-600">
                        {greeting}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-center text-sm text-red-600">
                  {error}
                </div>
              )}

              <AnimatePresence initial={false}>
                {messages.map((message, index) => {
                  const isUser = message.role === "user";
                  const docs = message.retrievedDocs ?? [];
                  const hasDocs = docs.length > 0;
                  const isLast = index === messages.length - 1;
                  const isStreamingAssistant = !isUser && isTyping && isLast;

                  return (
                    <motion.div
                      key={message.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={cn(
                        "group/message flex w-full flex-col",
                        isUser ? "items-end" : "items-start",
                      )}
                    >
                      <div className="flex max-w-full items-start gap-2">
                        {!isUser && (
                          <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-blue-200 bg-blue-50">
                            <Bot className="h-4 w-4 text-blue-600" />
                          </div>
                        )}

                        <div className="flex max-w-[calc(100%-2.5rem)] flex-col gap-1.5">
                          <div
                            className={cn(
                              "relative px-4 py-3 text-[15px] leading-relaxed shadow-sm",
                              isUser
                                ? "rounded-[20px] rounded-br-sm bg-blue-600 text-white"
                                : "rounded-[20px] rounded-bl-sm border border-slate-200 bg-white pr-11 text-slate-800",
                            )}
                          >
                            {isUser ? (
                              <div className="whitespace-pre-wrap">{message.content}</div>
                            ) : (
                              <div className="relative max-w-none">
                                {message.content ? (
                                  <>
                                    <AnswerMarkdown text={message.content} />
                                    {isStreamingAssistant && (
                                      <span className="ml-1 inline-block h-[15px] w-2 animate-pulse rounded-sm bg-blue-500 align-middle" />
                                    )}
                                  </>
                                ) : isStreamingAssistant ? (
                                  <div className="flex min-w-[220px] items-center gap-2 text-sm text-slate-600">
                                    <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                                    <span>{streamStatus ?? "正在处理..."}</span>
                                    {typeof retrievedCount === "number" && retrievedCount > 0 && (
                                      <span className="text-xs text-slate-400">
                                        匹配 {retrievedCount} 条
                                      </span>
                                    )}
                                  </div>
                                ) : (
                                  <AnswerMarkdown text={message.content} />
                                )}
                              </div>
                            )}

                            {!isUser && message.content && (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => void handleCopy(message.id, message.content)}
                                className={cn(
                                  "absolute right-2 top-2 h-7 w-7 rounded-full border border-slate-200 bg-white/95 text-slate-400 opacity-0 shadow-sm backdrop-blur transition-all hover:bg-slate-50 hover:text-slate-700 focus-visible:opacity-100 group-hover/message:opacity-100",
                                  copiedMessageId === message.id &&
                                    "border-emerald-200 bg-emerald-50 text-emerald-600 opacity-100 hover:bg-emerald-50 hover:text-emerald-600",
                                )}
                                title={copiedMessageId === message.id ? "已复制" : "复制"}
                              >
                                {copiedMessageId === message.id ? (
                                  <CheckCircle2 className="h-3.5 w-3.5" />
                                ) : (
                                  <Copy className="h-3.5 w-3.5" />
                                )}
                              </Button>
                            )}
                          </div>

                          {isStreamingAssistant && message.content && streamStatus && (
                            <div className="flex items-center gap-1.5 pl-1 text-[11px] leading-none text-slate-400">
                              <Loader2 className="h-3 w-3 animate-spin text-blue-500" />
                              <span>{streamStatus}</span>
                            </div>
                          )}

                          {!isUser && !isTyping && (
                            <div className="mt-1 space-y-2 pl-1">
                              {message.answerStatus === "insufficient" && !hasDocs ? (
                                <div className="rounded-lg bg-amber-50 px-2.5 py-2 text-xs text-amber-700">
                                  未检索到足够相关的知识库内容
                                </div>
                              ) : null}

                              {hasDocs && (
                                <div className="flex flex-wrap gap-2">
                                  {docs.slice(0, 4).map((doc, docIndex) => (
                                    <div
                                      key={`${message.id}-doc-${docIndex}`}
                                      className="flex max-w-[180px] items-center gap-1.5 rounded-full bg-slate-50 px-2.5 py-1 text-[11px] text-slate-500"
                                      title={getDocTitle(doc)}
                                    >
                                      <FileText className="h-3 w-3 shrink-0 text-blue-500" />
                                      <span className="truncate">{getDocTitle(doc)}</span>
                                    </div>
                                  ))}
                                </div>
                              )}

                              <div className="flex items-center gap-2 border-t border-slate-100 pt-2">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  disabled={!message.logId}
                                  onClick={() => void handleSubmitFeedback(message.id, "helpful")}
                                  className={cn(
                                    "h-8 w-8 rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition-colors hover:border-amber-200 hover:bg-amber-50 hover:text-amber-600 disabled:cursor-not-allowed disabled:opacity-50",
                                    message.feedbackValue === "helpful"
                                      ? "border-amber-200 bg-amber-100 text-amber-700 hover:bg-amber-100 hover:text-amber-700"
                                      : "",
                                  )}
                                  title="有帮助"
                                >
                                  <ThumbsUp className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  disabled={!message.logId}
                                  onClick={() =>
                                    void handleSubmitFeedback(message.id, "not_helpful")
                                  }
                                  className={cn(
                                    "h-8 w-8 rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-50",
                                    message.feedbackValue === "not_helpful"
                                      ? "border-red-200 bg-red-100 text-red-700 hover:bg-red-100 hover:text-red-700"
                                      : "",
                                  )}
                                  title="没有帮助"
                                >
                                  <ThumbsDown className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>

              {isTyping && messages[messages.length - 1]?.role === "user" && (
                <div className="flex max-w-full items-end gap-2">
                  <div className="mb-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-blue-200 bg-blue-50">
                    <Bot className="h-4 w-4 text-blue-600" />
                  </div>
                  <div className="flex min-w-[200px] flex-col gap-2 rounded-[20px] rounded-bl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-2 text-sm text-slate-600">
                      <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                      正在检索知识库...
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full w-2/3 animate-pulse rounded-full bg-blue-500" />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="shrink-0 border-t border-slate-200 bg-[#f7f8fa] p-3 md:p-4">
            <div className="mx-auto w-full max-w-3xl lg:max-w-4xl">
              {messages.length === 0 && suggestions.length > 0 && (
                <div className="mb-4">
                  <div className="mb-3 flex items-center gap-1.5 px-1 text-xs font-medium text-slate-500">
                    <Zap className="h-4 w-4 fill-amber-400 text-amber-400" />
                    你可能想问
                  </div>
                  <div className="flex flex-col gap-2.5">
                    {suggestions.map((suggestion, index) => (
                      <button
                        key={`${suggestion}-${index}`}
                        type="button"
                        onClick={() => void handleSendMessage(suggestion)}
                        className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm transition-all hover:border-blue-400 hover:text-blue-600"
                      >
                        <MessageSquare className="h-4 w-4 shrink-0 text-blue-500 opacity-80" />
                        <span className="truncate">{suggestion}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition-all focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20">
                <textarea
                  ref={inputRef}
                  value={inputValue}
                  onChange={(event) => setInputValue(event.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={placeholder}
                  disabled={Boolean(error && messages.length === 0)}
                  className="max-h-[120px] min-h-[44px] w-full resize-none bg-transparent p-3 text-[14px] outline-none placeholder:text-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
                  rows={1}
                />

                <div className="flex items-center justify-between border-t border-slate-100 px-2 py-2">
                  <div className="text-[11px] text-slate-400">Shift + Enter 换行</div>

                  {isTyping ? (
                    <Button
                      size="sm"
                      onClick={handleStopGenerating}
                      className="h-8 rounded-lg bg-red-50 px-3 text-red-600 hover:bg-red-100"
                    >
                      <Square className="mr-1.5 h-3.5 w-3.5 fill-current" />
                      停止
                    </Button>
                  ) : (
                    <Button
                      size="icon"
                      onClick={onSend}
                      disabled={!inputValue.trim() || Boolean(error && messages.length === 0)}
                      className={cn(
                        "h-8 w-8 rounded-lg transition-all",
                        inputValue.trim()
                          ? "bg-blue-600 text-white shadow-md hover:bg-blue-700"
                          : "bg-slate-100 text-slate-400",
                      )}
                    >
                      <SendHorizontal className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
      </main>
    </div>
  );
}
