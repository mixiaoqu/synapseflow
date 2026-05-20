import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";

import {
  embedApi,
  type EmbedAssistantBootstrap,
  type EmbedPageConfig,
  type EmbedPageContext,
} from "@/shared/api/embed";
import { consumeSseStream } from "@/shared/lib/stream/sse";
import { AppRequestError } from "@/shared/utils/error";

interface RetrievedDoc {
  content?: string;
  metadata?: Record<string, unknown>;
}

export interface EmbedMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  retrievedDocs?: RetrievedDoc[];
  answerStatus?: string | null;
  logId?: number | null;
  feedbackValue?: string | null;
  feedbackSubmitting?: boolean;
}

function findMessageById(messages: EmbedMessage[], messageId: string) {
  return messages.find((message) => message.id === messageId) ?? null;
}

const DEFAULT_ASSISTANT_NAME = "智能助手";
const DEFAULT_GREETING = "你好，我是智能助手，可以为你解答相关问题。";
const DEFAULT_PLACEHOLDER = "输入你的问题...";

function createMessageId(prefix: string) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatEmbedError(error: unknown, fallbackMessage: string) {
  const message =
    error instanceof AppRequestError || error instanceof Error ? error.message : fallbackMessage;

  if (/token expired/i.test(message)) {
    return "会话已过期，请重新打开助手。";
  }
  if (/invalid embedded assistant token/i.test(message)) {
    return "会话凭证无效，请重新打开助手。";
  }
  if (/embedded assistant token is required/i.test(message)) {
    return "缺少访问凭证，请重新打开助手。";
  }
  if (/active project application not found/i.test(message)) {
    return "当前应用未启用，或尚未绑定可用助手。";
  }

  return message || fallbackMessage;
}

function buildContextLabel(bootstrap: EmbedAssistantBootstrap, pageConfig: EmbedPageConfig | null) {
  const segments = [bootstrap.project_name, bootstrap.app_name];
  if (pageConfig?.page_name) {
    segments.push(pageConfig.page_name);
  }
  return segments.filter(Boolean).join(" / ");
}

export function useEmbeddedAssistant() {
  const route = useRoute();
  const token = computed(() => {
    const raw = route.query.token;
    return typeof raw === "string" ? raw.trim() : "";
  });

  const messages = ref<EmbedMessage[]>([]);
  const isInitializing = ref(true);
  const isTyping = ref(false);
  const assistantName = ref(DEFAULT_ASSISTANT_NAME);
  const greeting = ref(DEFAULT_GREETING);
  const placeholder = ref(DEFAULT_PLACEHOLDER);
  const suggestions = ref<string[]>([]);
  const contextLabel = ref("");
  const error = ref<string | null>(null);
  const streamStatus = ref<string | null>(null);
  const retrievedCount = ref<number | null>(null);
  const currentSessionId = ref<string | null>(null);
  const pageContext = ref<EmbedPageContext | null>(null);
  const pageConfig = ref<EmbedPageConfig | null>(null);
  const scrollContainerRef = ref<HTMLElement | null>(null);

  let activeAbortController: AbortController | null = null;

  function resetAssistantState() {
    messages.value = [];
    error.value = null;
    streamStatus.value = null;
    retrievedCount.value = null;
    currentSessionId.value = null;
  }

  async function scrollToBottom() {
    await nextTick();
    if (scrollContainerRef.value) {
      scrollContainerRef.value.scrollTop = scrollContainerRef.value.scrollHeight;
    }
  }

  function stopGenerating() {
    activeAbortController?.abort();
    activeAbortController = null;
    isTyping.value = false;
    streamStatus.value = null;
  }

  async function initialize() {
    stopGenerating();
    resetAssistantState();
    assistantName.value = DEFAULT_ASSISTANT_NAME;
    greeting.value = DEFAULT_GREETING;
    placeholder.value = DEFAULT_PLACEHOLDER;
    suggestions.value = [];
    contextLabel.value = "";
    pageContext.value = null;
    pageConfig.value = null;
    isInitializing.value = true;

    if (!token.value) {
      error.value = "缺少访问凭证，请通过嵌入预览链接进入。";
      isInitializing.value = false;
      return;
    }

    try {
      const bootstrap = await embedApi.bootstrap(token.value);
      assistantName.value = bootstrap.assistant_name || DEFAULT_ASSISTANT_NAME;
      placeholder.value = bootstrap.placeholder_text || DEFAULT_PLACEHOLDER;
      pageConfig.value = bootstrap.page_config ?? null;
      pageContext.value = bootstrap.page_config
        ? {
            app_id: bootstrap.app_code,
            page_type: bootstrap.page_config.page_type,
          }
        : null;
      contextLabel.value = buildContextLabel(bootstrap, pageConfig.value);
      greeting.value =
        bootstrap.page_config?.assistant_intro?.trim() ||
        bootstrap.welcome_message ||
        DEFAULT_GREETING;
      suggestions.value = bootstrap.page_config
        ? [...bootstrap.page_config.suggested_questions]
        : [...bootstrap.suggested_prompts];
    } catch (err) {
      error.value = formatEmbedError(err, "初始化助手失败。");
    } finally {
      isInitializing.value = false;
    }
  }

  async function sendMessage(content: string) {
    const query = content.trim();
    if (!query || isTyping.value || !token.value) {
      return;
    }

    const userMessage: EmbedMessage = {
      id: createMessageId("user"),
      role: "user",
      content: query,
      createdAt: new Date().toISOString(),
    };

    const assistantMessageId = createMessageId("assistant");
    const assistantMessage: EmbedMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      createdAt: new Date().toISOString(),
      retrievedDocs: [],
      answerStatus: null,
      logId: null,
      feedbackValue: null,
      feedbackSubmitting: false,
    };

    messages.value = [...messages.value, userMessage, assistantMessage];
    error.value = null;
    streamStatus.value = "正在连接助手...";
    retrievedCount.value = null;
    isTyping.value = true;
    await scrollToBottom();

    const controller = new AbortController();
    activeAbortController = controller;

    try {
      const stream = await embedApi.stream(
        token.value,
        {
          query,
          session_id: currentSessionId.value,
          page_context: pageContext.value,
        },
        controller.signal,
      );

      await consumeSseStream(stream, (event) => {
        if (controller.signal.aborted) {
          return;
        }

        switch (event.type) {
          case "node_complete": {
            if (event.node_id === "retrieve") {
              const count = event.data.retrieved_count;
              if (typeof count === "number") {
                retrievedCount.value = count;
                streamStatus.value =
                  count > 0 ? "已匹配相关内容，正在生成回答..." : "未匹配到相关内容，正在整理说明...";
              }
            } else if (event.node_id === "answer") {
              streamStatus.value = "正在整理回答...";
            }
            break;
          }
          case "token": {
            const text = event.data.text;
            if (typeof text !== "string" || !text) {
              break;
            }
            streamStatus.value = "正在生成回答...";
            const targetMessage = findMessageById(messages.value, assistantMessageId);
            if (targetMessage) {
              targetMessage.content += text;
            }
            break;
          }
          case "retrieved": {
            const docs = event.data.retrieved_docs;
            if (!Array.isArray(docs)) {
              break;
            }
            retrievedCount.value = docs.length;
            streamStatus.value =
              docs.length > 0 ? "已匹配相关内容，正在生成回答..." : "未匹配到相关内容，正在整理说明...";
            const targetMessage = findMessageById(messages.value, assistantMessageId);
            if (targetMessage) {
              targetMessage.retrievedDocs = docs as RetrievedDoc[];
            }
            break;
          }
          case "complete": {
            streamStatus.value = null;
            const answer = event.data.answer;
            const sessionId = event.data.session_id;
            const docs = event.data.retrieved_docs;
            const answerStatus =
              typeof event.data.answer_status === "string" ? event.data.answer_status : null;
            const logId = typeof event.data.log_id === "number" ? event.data.log_id : null;

            if (typeof sessionId === "string" && sessionId) {
              currentSessionId.value = sessionId;
            }

            const targetMessage = findMessageById(messages.value, assistantMessageId);
            if (targetMessage) {
              if (typeof answer === "string") {
                targetMessage.content = answer;
              }
              targetMessage.answerStatus = answerStatus;
              targetMessage.logId = logId;
              if (Array.isArray(docs)) {
                targetMessage.retrievedDocs = docs as RetrievedDoc[];
              }
            }
            break;
          }
          case "error": {
            const message =
              typeof event.data.message === "string" && event.data.message.trim()
                ? event.data.message.trim()
                : "请求失败";
            error.value = message;
            streamStatus.value = null;
            const targetMessage = findMessageById(messages.value, assistantMessageId);
            if (targetMessage) {
              targetMessage.content = message;
            }
            break;
          }
          default:
            break;
        }

        void scrollToBottom();
      });
    } catch (err) {
      if (!controller.signal.aborted) {
        const message = formatEmbedError(err, "请求失败。");
        error.value = message;
        const targetMessage = findMessageById(messages.value, assistantMessageId);
        if (targetMessage) {
          targetMessage.content = message;
        }
      }
    } finally {
      if (activeAbortController === controller) {
        activeAbortController = null;
      }
      isTyping.value = false;
      streamStatus.value = null;
      await scrollToBottom();
    }
  }

  function startNewConversation() {
    stopGenerating();
    resetAssistantState();
  }

  async function submitFeedback(logId: number, feedbackValue: string) {
    const targetMessage = messages.value.find((message) => message.logId === logId) ?? null;
    if (!targetMessage || targetMessage.feedbackSubmitting) {
      return;
    }

    targetMessage.feedbackSubmitting = true;
    try {
      await embedApi.submitFeedback(token.value, logId, {
        feedback_value: feedbackValue,
      });
      targetMessage.feedbackValue = feedbackValue;
    } finally {
      targetMessage.feedbackSubmitting = false;
    }
  }

  watch(token, () => {
    void initialize();
  }, { immediate: true });

  watch(
    () => messages.value.length,
    () => {
      void scrollToBottom();
    },
  );

  onBeforeUnmount(() => {
    stopGenerating();
  });

  return {
    assistantName,
    contextLabel,
    currentSessionId,
    error,
    greeting,
    isInitializing,
    isTyping,
    messages,
    pageConfig,
    placeholder,
    retrievedCount,
    scrollContainerRef,
    streamStatus,
    suggestions,
    sendMessage,
    submitFeedback,
    startNewConversation,
    stopGenerating,
    token,
  };
}
