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
  Sparkles,
  Square,
  ThumbsDown,
  ThumbsUp,
  User,
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

function TypingDots() {
  return (
    <div className="flex items-center gap-1 px-1 py-0.5">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="inline-block h-1.5 w-1.5 rounded-full bg-blue-400"
          animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.1, 0.8] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}

function getThinkingPhase(status: string | null, retrievedCount: number) {
  const detail = status ?? "正在匹配相关内容";

  if (/整理|组织|已匹配|未匹配/.test(detail)) {
    return {
      main: "正在组织答案",
      detail,
    };
  }

  if (/生成|回答|回复/.test(detail)) {
    return {
      main: "正在生成回复",
      detail,
    };
  }

  return {
    main: "正在检索知识库",
    detail: retrievedCount > 0 ? `已匹配 ${retrievedCount} 条相关内容` : detail,
  };
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
  const thinkingPhase = getThinkingPhase(streamStatus, retrievedCount);

  const [inputValue, setInputValue] = useState("");
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [isFocused, setIsFocused] = useState(false);
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
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;

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

  if (isInitializing) {
    return (
      <div className="flex h-[100dvh] w-full flex-col items-center justify-center gap-4 bg-white">
        <motion.div
          className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-200"
          animate={{ scale: [1, 1.08, 1] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
        >
          <Sparkles className="h-6 w-6 text-white" />
        </motion.div>
        <p className="text-sm text-slate-400">正在初始化助手...</p>
      </div>
    );
  }

  return (
    <div className="relative flex h-[100dvh] w-full flex-col overflow-hidden bg-[#f5f6f8]">

      {/* Header */}
      <header className="relative z-20 flex h-14 shrink-0 items-center justify-between border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur-md">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-blue-500 via-indigo-500 to-violet-500" />

        <div className="flex min-w-0 items-center gap-2.5">
          <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-md shadow-blue-200">
            <Bot className="h-4 w-4 text-white" />
            <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-emerald-500" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="truncate text-[14px] font-semibold text-slate-800">
                {assistantName}
              </span>
              <span className="rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-white shadow-sm">
                AI
              </span>
            </div>
            <div className="text-[11px] text-emerald-500">● 在线服务中</div>
          </div>
        </div>

        <div className="flex shrink-0 items-center">
          <EmbedSessionHistoryPanel
            currentSessionId={currentSessionId}
            onSelectSession={(sessionId) => void handleSelectSession(sessionId)}
            onNewSession={handleNewSession}
          />
        </div>
      </header>

      {/* ── Context label ── */}
      <AnimatePresence>
        {contextLabel ? (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className="shrink-0 border-b border-blue-100 bg-blue-50/60 px-4 py-2"
          >
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-blue-400">
                当前应用
              </span>
              <span className="text-[11px] font-medium text-blue-700">{contextLabel}</span>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {/* ── Messages ── */}
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-smooth">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-0 px-4 py-5 lg:max-w-4xl">

            {/* Welcome bubble */}
            {messages.length === 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
                className="flex w-full flex-col items-start"
              >
                <div className="flex max-w-full items-end gap-2">
                  <div className="mb-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow shadow-blue-200">
                    <Bot className="h-3.5 w-3.5 text-white" />
                  </div>
                  <div className="max-w-[calc(100%-2.25rem)]">
                    <div className="rounded-[18px] rounded-bl-[4px] border border-slate-200/80 bg-white px-4 py-3 text-[14px] leading-relaxed text-slate-800 shadow-sm">
                      <p className="whitespace-pre-wrap">{greeting}</p>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Error banner */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.97 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.97 }}
                  className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-center text-sm text-red-600"
                >
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Message list */}
            <AnimatePresence initial={false}>
              {messages.map((message, index) => {
                const isUser = message.role === "user";
                const previousMessage = messages[index - 1];
                const startsNewTurn = isUser && previousMessage != null;
                const docs = message.retrievedDocs ?? [];
                const hasDocs = docs.length > 0;
                const isLast = index === messages.length - 1;
                const isStreamingAssistant = !isUser && isTyping && isLast;

                return (
                  <motion.div
                    key={message.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25 }}
                    className={cn(
                      "group/message flex w-full flex-col",
                      isUser ? "items-end" : "items-start",
                      index === 0 ? "" : startsNewTurn ? "mt-8" : "mt-2",
                    )}
                  >
                    <div
                      className={cn(
                        "flex w-full max-w-full items-start gap-2",
                        isUser ? "justify-end" : "justify-start",
                      )}
                    >
                      {/* Bot avatar */}
                      {!isUser && (
                        <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow shadow-blue-200">
                          <Bot className="h-3.5 w-3.5 text-white" />
                        </div>
                      )}

                      <div
                        className={cn(
                          "flex min-w-0 flex-col gap-1.5",
                          isUser
                            ? "max-w-[85%] items-end"
                            : "w-full max-w-[85%] items-start",
                        )}
                      >
                        {/* Bubble */}
                        <div
                          className={cn(
                            "relative max-w-full text-[14px] leading-relaxed",
                            isUser
                              ? "rounded-[18px] rounded-tr-[4px] bg-blue-600 px-4 py-2.5 text-left text-white shadow-md shadow-blue-200/50"
                              : "w-full rounded-[18px] rounded-tl-[4px] border border-slate-200/80 bg-white px-4 py-3 text-slate-800 shadow-sm",
                          )}
                        >
                          {isUser ? (
                            <div className="max-w-full whitespace-pre-wrap break-words">
                              {message.content}
                            </div>
                          ) : (
                            <div className="relative max-w-none">
                              {message.content ? (
                                <>
                                  <AnswerMarkdown text={message.content} />
                                  {isStreamingAssistant && (
                                    <span className="ml-1 inline-block h-[14px] w-1.5 animate-pulse rounded-sm bg-blue-400 align-middle" />
                                  )}
                                </>
                              ) : isStreamingAssistant ? (
                                <div className="flex min-w-[180px] items-center gap-2.5 text-[13px] text-slate-500">
                                  <TypingDots />
                                  <span>{streamStatus ?? "正在处理..."}</span>
                                  {retrievedCount > 0 && (
                                    <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] text-blue-500">
                                      {retrievedCount} 条
                                    </span>
                                  )}
                                </div>
                              ) : (
                                <AnswerMarkdown text={message.content} />
                              )}
                            </div>
                          )}

                          {/* Copy button */}
                          {!isUser && message.content && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => void handleCopy(message.id, message.content)}
                              className={cn(
                                "absolute right-2 top-2 h-6 w-6 rounded-lg border border-slate-200 bg-white/95 text-slate-400 opacity-0 shadow-sm backdrop-blur-sm transition-all hover:bg-slate-50 hover:text-slate-600 focus-visible:opacity-100 group-hover/message:opacity-100",
                                copiedMessageId === message.id &&
                                  "border-emerald-200 bg-emerald-50 text-emerald-600 opacity-100 hover:bg-emerald-50 hover:text-emerald-600",
                              )}
                              title={copiedMessageId === message.id ? "已复制" : "复制"}
                            >
                              {copiedMessageId === message.id ? (
                                <CheckCircle2 className="h-3 w-3" />
                              ) : (
                                <Copy className="h-3 w-3" />
                              )}
                            </Button>
                          )}
                        </div>

                        {/* Stream status pill */}
                        <AnimatePresence>
                          {isStreamingAssistant && message.content && streamStatus && (
                            <motion.div
                              initial={{ opacity: 0, y: -4 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0 }}
                              className="flex items-center gap-1.5 pl-1 text-[11px] text-slate-400"
                            >
                              <Loader2 className="h-3 w-3 animate-spin text-blue-400" />
                              <span>{streamStatus}</span>
                            </motion.div>
                          )}
                        </AnimatePresence>

                        {/* Source docs + feedback */}
                        {!isUser && !isTyping && (
                          <div className="mt-0.5 space-y-2 pl-0.5">
                            {message.answerStatus === "insufficient" && !hasDocs ? (
                              <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="flex items-center gap-1.5 rounded-lg bg-amber-50 px-3 py-2 text-[12px] text-amber-700"
                              >
                                <span className="text-amber-400">⚠</span>
                                未检索到足够相关的知识库内容
                              </motion.div>
                            ) : null}

                            {hasDocs && (
                              <div className="flex flex-wrap gap-1.5">
                                {docs.slice(0, 4).map((doc, docIndex) => (
                                  <div
                                    key={`${message.id}-doc-${docIndex}`}
                                    className="flex max-w-[160px] items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-500 shadow-sm"
                                    title={getDocTitle(doc)}
                                  >
                                    <FileText className="h-3 w-3 shrink-0 text-blue-400" />
                                    <span className="truncate">{getDocTitle(doc)}</span>
                                  </div>
                                ))}
                                {docs.length > 4 ? (
                                  <div
                                    className="flex items-center rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-500"
                                    title={`还有 ${docs.length - 4} 个参考来源`}
                                  >
                                    +{docs.length - 4}
                                  </div>
                                ) : null}
                              </div>
                            )}

                            {/* Feedback */}
                            <div className="flex items-center gap-1.5 pt-0.5">
                              <Button
                                variant="ghost"
                                size="icon"
                                disabled={!message.logId}
                                onClick={() => void handleSubmitFeedback(message.id, "helpful")}
                                className={cn(
                                  "h-7 w-7 rounded-lg border border-slate-200 bg-white text-slate-400 shadow-sm transition-all hover:border-emerald-200 hover:bg-emerald-50 hover:text-emerald-600 disabled:cursor-not-allowed disabled:opacity-40",
                                  message.feedbackValue === "helpful"
                                    ? "border-emerald-200 bg-emerald-50 text-emerald-600"
                                    : "",
                                )}
                                title="有帮助"
                              >
                                <ThumbsUp className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                disabled={!message.logId}
                                onClick={() => void handleSubmitFeedback(message.id, "not_helpful")}
                                className={cn(
                                  "h-7 w-7 rounded-lg border border-slate-200 bg-white text-slate-400 shadow-sm transition-all hover:border-red-200 hover:bg-red-50 hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-40",
                                  message.feedbackValue === "not_helpful"
                                    ? "border-red-200 bg-red-50 text-red-500"
                                    : "",
                                )}
                                title="没有帮助"
                              >
                                <ThumbsDown className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>

                      {isUser && (
                        <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white/80 text-slate-400 shadow-sm">
                          <User className="h-3.5 w-3.5" />
                        </div>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>

            {/* Bot thinking bubble (before any assistant token arrives) */}
            <AnimatePresence>
              {isTyping && messages[messages.length - 1]?.role === "user" && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 4 }}
                  className="flex items-start gap-2"
                >
                  <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow shadow-blue-200">
                    <Bot className="h-3.5 w-3.5 text-white" />
                  </div>
                  <div className="flex w-[260px] flex-col gap-2 rounded-[18px] rounded-tl-[4px] border border-slate-200/80 bg-white px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-2">
                      <TypingDots />
                      <span className="text-[12px] font-medium text-slate-500">
                        {thinkingPhase.main}
                      </span>
                    </div>
                    <div className="h-1 w-24 overflow-hidden rounded-full bg-slate-100">
                      <motion.div
                        className="h-full bg-gradient-to-r from-blue-400 to-indigo-500"
                        animate={{ x: ["-100%", "200%"] }}
                        transition={{ duration: 1.4, repeat: Infinity }}
                      />
                    </div>
                    <span className="text-[11px] text-slate-400">
                      {thinkingPhase.detail}
                    </span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

          </div>
        </div>

        {/* ── Input area ── */}
        <div className="shrink-0 border-t border-slate-200/80 bg-white/90 px-3 py-3 backdrop-blur-md md:px-4 md:py-4">
          <div className="mx-auto w-full max-w-3xl lg:max-w-4xl">

            {/* Suggestions */}
            <AnimatePresence>
              {messages.length === 0 && suggestions.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="mb-3"
                >
                  <div className="mb-2 flex items-center gap-1.5 px-0.5 text-[11px] font-semibold uppercase tracking-widest text-slate-400">
                    <Zap className="h-3 w-3 fill-amber-400 text-amber-400" />
                    热门问题
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {suggestions.map((suggestion, index) => (
                      <motion.button
                        key={`${suggestion}-${index}`}
                        type="button"
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.06 }}
                        onClick={() => void handleSendMessage(suggestion)}
                        className="group inline-flex max-w-full items-center gap-1.5 rounded-full border border-slate-200/80 bg-white px-3 py-1.5 text-left text-[12px] text-slate-600 shadow-sm transition-all hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 hover:shadow-md active:scale-[0.99]"
                      >
                        <MessageSquare className="h-3 w-3 shrink-0 text-blue-400 transition-transform group-hover:scale-110" />
                        <span className="max-w-[220px] truncate">{suggestion}</span>
                      </motion.button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Input box */}
            <div
              className={cn(
                "overflow-hidden rounded-2xl border bg-white shadow-md transition-all duration-200",
                isFocused
                  ? "border-blue-400 shadow-blue-100 ring-3 ring-blue-500/15"
                  : "border-slate-200/80 shadow-slate-100",
              )}
            >
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(event) => setInputValue(event.target.value)}
                onKeyDown={handleKeyDown}
                onFocus={() => setIsFocused(true)}
                onBlur={() => setIsFocused(false)}
                placeholder={placeholder}
                disabled={Boolean(error && messages.length === 0)}
                className="max-h-[120px] min-h-[46px] w-full resize-none bg-transparent px-4 py-3 text-[14px] leading-relaxed text-slate-800 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
                rows={1}
              />

              <div className="flex items-center justify-between border-t border-slate-100 px-3 py-2">
                <span className="text-[11px] text-slate-400">
                  Shift + Enter 换行
                </span>

                <div className="flex items-center gap-2">
                  {isTyping ? (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                    >
                      <Button
                        size="sm"
                        onClick={handleStopGenerating}
                        className="h-8 gap-1.5 rounded-xl border-0 bg-red-50 px-3 text-[13px] font-medium text-red-500 shadow-none hover:bg-red-100 hover:text-red-600"
                      >
                        <Square className="h-3 w-3 fill-current" />
                        停止生成
                      </Button>
                    </motion.div>
                  ) : (
                    <motion.div
                      animate={inputValue.trim() ? { scale: 1 } : { scale: 0.95 }}
                    >
                      <Button
                        size="icon"
                        onClick={onSend}
                        disabled={!inputValue.trim() || Boolean(error && messages.length === 0)}
                        className={cn(
                          "h-8 w-8 rounded-xl transition-all duration-200",
                          inputValue.trim()
                            ? "bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-md shadow-blue-200 hover:from-blue-600 hover:to-indigo-700 hover:shadow-lg hover:shadow-blue-300"
                            : "cursor-not-allowed bg-slate-100 text-slate-400",
                        )}
                      >
                        <SendHorizontal className="h-3.5 w-3.5" />
                      </Button>
                    </motion.div>
                  )}
                </div>
              </div>
            </div>

            {/* Footer branding */}
            <div className="mt-2 flex items-center justify-center gap-1 text-[10px] text-slate-400">
              <Sparkles className="h-2.5 w-2.5 text-blue-400" />
              Powered by LangChain RAG 知识库
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
