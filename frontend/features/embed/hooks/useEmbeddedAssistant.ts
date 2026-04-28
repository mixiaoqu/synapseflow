"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { v4 as uuidv4 } from "uuid";

import { embedApi } from "@/lib/api/endpoints/embed";
import type { EmbedPageConfig, EmbedPageContext } from "@/lib/api/endpoints/embed";
import type {
  AskRetrievedDoc,
  AskSessionMessage,
} from "@/lib/api/endpoints/ask";
import { consumeSseStream } from "@/lib/stream/sse";

const DEFAULT_ASSISTANT_NAME = "智能助手";
const DEFAULT_GREETING = "你好，我是智能助手，可以为你解答相关问题。";

function formatEmbedError(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : fallback;
  if (/token expired/i.test(message)) {
    return "会话已过期，请重新打开助手";
  }
  if (/invalid embedded assistant token/i.test(message)) {
    return "会话凭证无效，请重新打开助手";
  }
  if (/embedded assistant token is required/i.test(message)) {
    return "缺少访问凭证，请重新打开助手";
  }
  if (/active project application not found/i.test(message)) {
    return "当前项目应用未启用或未绑定可用助手";
  }
  return message || fallback;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  retrievedDocs?: AskRetrievedDoc[];
  answerStatus?: string | null;
  logId?: number | null;
  feedbackValue?: "helpful" | "not_helpful" | null;
}

export interface Session {
  id: string;
  title: string;
  createdAt: string;
  preview?: string | null;
}

function toMessages(messages: AskSessionMessage[]): Message[] {
  return messages
    .filter((message) => {
      const role = message.role.trim().toLowerCase();
      return (role === "user" || role === "assistant") && message.content.trim();
    })
    .map((message) => ({
      id: `${message.created_at}-${uuidv4()}`,
      role: message.role.trim().toLowerCase() as "user" | "assistant",
      content: message.content,
      createdAt: message.created_at,
      retrievedDocs: message.retrieved_docs ?? [],
      answerStatus: message.answer_status ?? null,
      logId: message.log_id ?? null,
      feedbackValue: null,
    }));
}

function getNodeStatus(nodeId?: string, message?: unknown): string | null {
  if (nodeId === "retrieve") return "正在检索知识库，匹配相关内容...";
  if (nodeId === "answer") return "正在生成回答...";

  if (typeof message !== "string") return null;
  if (/retrieving/i.test(message)) return "正在检索知识库，匹配相关内容...";
  if (/generating/i.test(message)) return "正在生成回答...";
  if (/starting/i.test(message)) return "正在准备问题...";
  return message;
}

export function useEmbeddedAssistant() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token")?.trim() || "";

  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);
  const [assistantName, setAssistantName] = useState(DEFAULT_ASSISTANT_NAME);
  const [greeting, setGreeting] = useState(DEFAULT_GREETING);
  const [placeholder, setPlaceholder] = useState("输入你的问题...");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [contextLabel, setContextLabel] = useState("");
  const [pageContext, setPageContext] = useState<EmbedPageContext | null>(null);
  const [pageConfig, setPageConfig] = useState<EmbedPageConfig | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [retrievedCount, setRetrievedCount] = useState<number | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function initialize() {
      setIsInitializing(true);
      setError(null);

      if (!token) {
        setError("缺少内嵌访问令牌");
        setIsInitializing(false);
        return;
      }

      try {
        const bootstrap = await embedApi.bootstrap(token);
        if (cancelled) return;
        setAssistantName(bootstrap.assistant_name || DEFAULT_ASSISTANT_NAME);
        setGreeting(bootstrap.welcome_message || DEFAULT_GREETING);
        setPlaceholder(bootstrap.placeholder_text || "输入你的问题...");
        setContextLabel(
          [bootstrap.project_name, bootstrap.app_name].filter(Boolean).join(" / "),
        );
        if (bootstrap.page_config) {
          const resolvedPageConfig = bootstrap.page_config;
          setPageConfig(resolvedPageConfig);
          setPageContext({
            app_id: bootstrap.app_code,
            page_type: resolvedPageConfig.page_type,
          });
          setContextLabel(
            [bootstrap.project_name, bootstrap.app_name, resolvedPageConfig.page_name]
              .filter(Boolean)
              .join(" / "),
          );
          const assistantIntro = resolvedPageConfig.assistant_intro?.trim() || "";
          if (assistantIntro) {
            setGreeting(assistantIntro);
          }
          setSuggestions(resolvedPageConfig.suggested_questions || []);
        } else {
          setSuggestions(bootstrap.suggested_prompts || []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(formatEmbedError(err, "初始化助手失败"));
        }
      } finally {
        if (!cancelled) {
          setIsInitializing(false);
        }
      }
    }

    void initialize();

    return () => {
      cancelled = true;
      abortControllerRef.current?.abort();
    };
  }, [token]);

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom, streamStatus]);

  const handleSendMessage = useCallback(
    async (content: string) => {
      const query = content.trim();
      if (!query || isTyping || !token) return;

      const userMessage: Message = {
        id: `user-${uuidv4()}`,
        role: "user",
        content: query,
        createdAt: new Date().toISOString(),
      };
      const assistantMessageId = `assistant-${uuidv4()}`;
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        createdAt: new Date().toISOString(),
        retrievedDocs: [],
        answerStatus: null,
        logId: null,
        feedbackValue: null,
      };

      setError(null);
      setStreamStatus("正在连接助手...");
      setRetrievedCount(null);
      setMessages((current) => [...current, userMessage, assistantMessage]);
      setIsTyping(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const stream = await embedApi.stream(
          token,
          {
            query,
            session_id: currentSessionId,
            page_context: pageContext,
          },
          controller.signal,
        );

        if (controller.signal.aborted) return;

        await consumeSseStream(stream, (event) => {
          if (controller.signal.aborted) return;

          switch (event.type) {
            case "start": {
              setStreamStatus(
                getNodeStatus(event.node_id, event.data.message) ?? "正在准备问题...",
              );
              break;
            }
            case "node_start": {
              setStreamStatus(
                getNodeStatus(event.node_id, event.data.message) ?? "正在处理...",
              );
              break;
            }
            case "node_complete": {
              if (event.node_id === "retrieve") {
                const count = event.data.retrieved_count;
                if (typeof count === "number") {
                  setRetrievedCount(count);
                  setStreamStatus(
                    count > 0
                      ? "已匹配相关内容，正在生成回答..."
                      : "未匹配到相关内容，正在生成说明...",
                  );
                }
              } else if (event.node_id === "answer") {
                setStreamStatus("正在整理回答...");
              }
              break;
            }
            case "token": {
              const text = event.data.text;
              if (typeof text !== "string" || !text) return;
              setStreamStatus("正在生成回答...");
              setMessages((current) =>
                current.map((message) =>
                  message.id === assistantMessageId
                    ? { ...message, content: `${message.content}${text}` }
                    : message,
                ),
              );
              break;
            }
            case "retrieved": {
              const docs = event.data.retrieved_docs;
              if (!Array.isArray(docs)) return;
              setRetrievedCount(docs.length);
              setStreamStatus(
                docs.length > 0
                  ? "已匹配相关内容，正在生成回答..."
                  : "未匹配到相关内容，正在生成说明...",
              );
              setMessages((current) =>
                current.map((message) =>
                  message.id === assistantMessageId
                    ? { ...message, retrievedDocs: docs as AskRetrievedDoc[] }
                    : message,
                ),
              );
              break;
            }
            case "complete": {
              setStreamStatus(null);
              const answer = event.data.answer;
              const sessionId = event.data.session_id;
              const docs = event.data.retrieved_docs;
              const answerStatus =
                typeof event.data.answer_status === "string"
                  ? event.data.answer_status
                  : null;
              const logId =
                typeof event.data.log_id === "number" ? event.data.log_id : null;
              if (typeof sessionId === "string" && sessionId) {
                setCurrentSessionId(sessionId);
              }
              if (typeof answer === "string") {
                setMessages((current) =>
                  current.map((message) =>
                    message.id === assistantMessageId
                      ? {
                          ...message,
                          content: answer,
                          answerStatus,
                          logId,
                          retrievedDocs: Array.isArray(docs)
                            ? (docs as AskRetrievedDoc[])
                            : message.retrievedDocs,
                        }
                      : message,
                  ),
                );
              }
              break;
            }
            case "error": {
              setStreamStatus(null);
              const message = String(event.data.message ?? "请求失败");
              setError(message);
              setMessages((current) =>
                current.map((item) =>
                  item.id === assistantMessageId ? { ...item, content: message } : item,
                ),
              );
              break;
            }
            default:
              break;
          }
        });

      } catch (err) {
        if (controller.signal.aborted) return;
        const message = formatEmbedError(err, "请求失败");
        setError(message);
        setMessages((current) =>
          current.map((item) =>
            item.id === assistantMessageId ? { ...item, content: message } : item,
          ),
        );
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
        setStreamStatus(null);
        setIsTyping(false);
      }
    },
    [currentSessionId, isTyping, pageContext, token],
  );

  const handleStopGenerating = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setStreamStatus(null);
    setRetrievedCount(null);
    setIsTyping(false);
  }, []);

  const handleNewSession = useCallback(() => {
    handleStopGenerating();
    setMessages([]);
    setCurrentSessionId(null);
    setError(null);
    setRetrievedCount(null);
  }, [handleStopGenerating]);

  const handleSelectSession = useCallback(
    async (sessionId: string) => {
      if (!sessionId || !token) return;

      handleStopGenerating();
      setError(null);
      setCurrentSessionId(sessionId);
      setRetrievedCount(null);

      try {
        const detail = await embedApi.getSession(token, sessionId);
        setMessages(toMessages(detail.messages));
      } catch (err) {
        setError(formatEmbedError(err, "加载会话失败"));
      }
    },
    [handleStopGenerating, token],
  );

  const handleSubmitFeedback = useCallback(
    async (messageId: string, value: "helpful" | "not_helpful") => {
      const target = messages.find((message) => message.id === messageId);
      if (!token || !target?.logId) return false;

      try {
        await embedApi.submitFeedback(token, target.logId, {
          feedback_value: value,
        });
        setMessages((current) =>
          current.map((message) =>
            message.id === messageId ? { ...message, feedbackValue: value } : message,
          ),
        );
        return true;
      } catch (err) {
        setError(formatEmbedError(err, "提交反馈失败"));
        return false;
      }
    },
    [messages, token],
  );

  return {
    assistantName,
    isInitializing,
    messages,
    isTyping,
    streamStatus,
    retrievedCount,
    currentSessionId,
    greeting,
    placeholder,
    suggestions,
    contextLabel,
    pageConfig,
    error,
    scrollRef,
    handleSendMessage,
    handleStopGenerating,
    handleNewSession,
    handleSelectSession,
    handleSubmitFeedback,
  };
}
