import {
  computed,
  nextTick,
  onBeforeUnmount,
  reactive,
  ref,
  unref,
  watch,
  type MaybeRef,
} from "vue";

import {
  widgetApi,
  type WidgetBootstrap,
  type WidgetPageContext,
  type WidgetSessionMessage,
  type WidgetSessionSummary,
} from "@/shared/api/widget";
import { consumeSseStream } from "@/shared/lib/stream/sse";
import {
  createWorkflowRun,
  reduceWorkflowRunEvent,
  type ChatWorkflowRun,
} from "@/shared/lib/stream/workflowRun";
import { AppRequestError, resolveDisplayErrorMessage } from "@/shared/utils/error";

export interface WidgetMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  retrievedDocs?: Array<Record<string, unknown>>;
  answerStatus?: string | null;
  logId?: number | null;
  feedback?: "helpful" | "not_helpful" | null;
  feedbackSubmitting?: boolean;
}

interface UseWidgetChatOptions {
  token: MaybeRef<string>;
  pageContext: MaybeRef<WidgetPageContext>;
  refreshToken: () => Promise<string>;
}

const DEFAULT_NAME = "智能助手";
const DEFAULT_GREETING = "你好，我是智能助手，可以为你解答相关问题。";
const DEFAULT_PLACEHOLDER = "输入你的问题...";

function createId(prefix: string) {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function toMessage(message: WidgetSessionMessage): WidgetMessage | null {
  const role = message.role.trim().toLowerCase();
  if ((role !== "user" && role !== "assistant") || !message.content.trim()) {
    return null;
  }
  return {
    id: createId(role),
    role,
    content: message.content,
    retrievedDocs: message.retrieved_docs ?? [],
    answerStatus: message.answer_status ?? null,
    logId: message.log_id ?? null,
    feedback: null,
    feedbackSubmitting: false,
  };
}

function errorMessage(error: unknown, fallback: string) {
  if (error instanceof AppRequestError && error.status === 401) {
    return "会话已过期，请重新打开助手。";
  }
  return error instanceof Error && error.message ? error.message : fallback;
}

function resolveCompletedAnswer(streamedAnswer: string, completedAnswer: unknown) {
  if (typeof completedAnswer !== "string") {
    return streamedAnswer;
  }

  const finalAnswer = completedAnswer.trim();
  if (!finalAnswer) {
    return streamedAnswer;
  }

  const streamed = streamedAnswer.trim();
  if (streamed.length > finalAnswer.length && streamed.startsWith(finalAnswer)) {
    return streamedAnswer;
  }

  return completedAnswer;
}

export function useWidgetChat(options: UseWidgetChatOptions) {
  const token = computed(() => unref(options.token).trim());
  const pageContext = computed(() => ({ ...unref(options.pageContext) }));
  const assistantName = ref(DEFAULT_NAME);
  const greeting = ref(DEFAULT_GREETING);
  const placeholder = ref(DEFAULT_PLACEHOLDER);
  const suggestions = ref<string[]>([]);
  const contextLabel = ref("");
  const messages = ref<WidgetMessage[]>([]);
  const sessions = ref<WidgetSessionSummary[]>([]);
  const currentSessionId = ref<string | null>(null);
  const isInitializing = ref(true);
  const isTyping = ref(false);
  const isLoadingSessions = ref(false);
  const error = ref<string | null>(null);
  const activityText = ref("");
  const workflowRun = ref<ChatWorkflowRun | null>(null);
  const scrollRef = ref<HTMLElement | null>(null);
  let abortController: AbortController | null = null;
  let bootstrapRequestId = 0;

  async function withTokenRefresh<T>(request: (requestToken: string) => Promise<T>) {
    const currentToken = token.value;
    try {
      return await request(currentToken);
    } catch (err) {
      if (!(err instanceof AppRequestError) || err.status !== 401) {
        throw err;
      }
      const nextToken = (await options.refreshToken()).trim();
      if (!nextToken || nextToken === currentToken) {
        throw err;
      }
      return request(nextToken);
    }
  }

  function applyBootstrap(bootstrap: WidgetBootstrap) {
    assistantName.value = bootstrap.assistant_name || DEFAULT_NAME;
    greeting.value =
      bootstrap.page_config?.assistant_intro?.trim() ||
      bootstrap.welcome_message ||
      DEFAULT_GREETING;
    placeholder.value = bootstrap.placeholder_text || DEFAULT_PLACEHOLDER;
    suggestions.value = bootstrap.page_config
      ? [...bootstrap.page_config.suggested_questions]
      : [...bootstrap.suggested_prompts];
    contextLabel.value = [
      bootstrap.project_name,
      bootstrap.app_name,
      bootstrap.page_config?.page_name,
    ]
      .filter(Boolean)
      .join(" / ");
  }

  async function loadBootstrap(resetConversation: boolean) {
    const requestId = ++bootstrapRequestId;
    if (resetConversation) {
      messages.value = [];
      currentSessionId.value = null;
      sessions.value = [];
      workflowRun.value = null;
      isInitializing.value = true;
    }
    error.value = null;
    try {
      const bootstrap = await withTokenRefresh((requestToken) =>
        widgetApi.bootstrap(requestToken, pageContext.value),
      );
      if (requestId === bootstrapRequestId) {
        applyBootstrap(bootstrap);
      }
    } catch (err) {
      if (requestId === bootstrapRequestId) {
        error.value = errorMessage(err, "初始化助手失败。");
      }
    } finally {
      if (requestId === bootstrapRequestId) {
        isInitializing.value = false;
      }
    }
  }

  async function scrollToBottom() {
    await nextTick();
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight;
    }
  }

  function stopGenerating() {
    abortController?.abort();
    abortController = null;
    isTyping.value = false;
    activityText.value = "";
    workflowRun.value = null;
  }

  function startNewConversation() {
    stopGenerating();
    messages.value = [];
    currentSessionId.value = null;
    error.value = null;
    workflowRun.value = null;
  }

  async function sendMessage(content: string) {
    const query = content.trim();
    if (!query || isTyping.value || !token.value) {
      return;
    }

    const assistantMessage = reactive<WidgetMessage>({
      id: createId("assistant"),
      role: "assistant",
      content: "",
      retrievedDocs: [],
      answerStatus: null,
      logId: null,
      feedback: null,
      feedbackSubmitting: false,
    });
    messages.value.push(
      { id: createId("user"), role: "user", content: query },
      assistantMessage,
    );
    error.value = null;
    activityText.value = "正在连接助手...";
    workflowRun.value = createWorkflowRun(null, activityText.value);
    isTyping.value = true;
    await scrollToBottom();

    const controller = new AbortController();
    abortController = controller;
    try {
      const stream = await withTokenRefresh((requestToken) =>
        widgetApi.stream(
          requestToken,
          {
            query,
            session_id: currentSessionId.value,
            page_context: pageContext.value,
          },
          controller.signal,
        ),
      );
      await consumeSseStream(stream, (event) => {
        if (controller.signal.aborted) {
          return;
        }
        workflowRun.value = reduceWorkflowRunEvent(workflowRun.value, event);
        if (event.type === "token" && typeof event.data.text === "string") {
          assistantMessage.content += event.data.text;
        } else if (event.type === "retrieved") {
          const docs = event.data.retrieved_docs;
          if (Array.isArray(docs)) {
            assistantMessage.retrievedDocs = docs as Array<Record<string, unknown>>;
          }
        } else if (event.type === "activity") {
          const text = event.data.activity_text ?? event.data.message;
          activityText.value = typeof text === "string" ? text : activityText.value;
        } else if (event.type === "complete") {
          assistantMessage.content = resolveCompletedAnswer(
            assistantMessage.content,
            event.data.answer,
          );
          if (typeof event.data.session_id === "string") {
            currentSessionId.value = event.data.session_id;
          }
          if (typeof event.data.log_id === "number") {
            assistantMessage.logId = event.data.log_id;
          }
          if (typeof event.data.answer_status === "string") {
            assistantMessage.answerStatus = event.data.answer_status;
          }
          if (Array.isArray(event.data.retrieved_docs)) {
            assistantMessage.retrievedDocs = event.data.retrieved_docs as Array<
              Record<string, unknown>
            >;
          }
          activityText.value = "";
        } else if (event.type === "error") {
          const raw = typeof event.data.message === "string" ? event.data.message : null;
          const message = resolveDisplayErrorMessage(raw, "请求失败，请稍后重试。");
          assistantMessage.content = message;
          error.value = message;
          activityText.value = "";
        }
        void scrollToBottom();
      });
    } catch (err) {
      if (!controller.signal.aborted) {
        const message = errorMessage(err, "请求失败，请稍后重试。");
        assistantMessage.content = message;
        error.value = message;
        workflowRun.value = reduceWorkflowRunEvent(workflowRun.value, {
          type: "error",
          data: { message },
          run_id: workflowRun.value?.id ?? null,
        });
      }
    } finally {
      if (abortController === controller) {
        abortController = null;
      }
      isTyping.value = false;
      activityText.value = "";
      await scrollToBottom();
    }
  }

  async function loadSessions() {
    if (isLoadingSessions.value || !token.value) {
      return;
    }
    isLoadingSessions.value = true;
    try {
      sessions.value = await withTokenRefresh((requestToken) =>
        widgetApi.listSessions(requestToken),
      );
    } catch (err) {
      error.value = errorMessage(err, "加载历史对话失败。");
    } finally {
      isLoadingSessions.value = false;
    }
  }

  async function selectSession(sessionId: string) {
    stopGenerating();
    try {
      const detail = await withTokenRefresh((requestToken) =>
        widgetApi.getSession(requestToken, sessionId),
      );
      currentSessionId.value = sessionId;
      messages.value = detail.messages
        .map(toMessage)
        .filter((message): message is WidgetMessage => message !== null);
      workflowRun.value = null;
      await scrollToBottom();
    } catch (err) {
      error.value = errorMessage(err, "加载历史对话失败。");
    }
  }

  async function deleteSession(sessionId: string) {
    try {
      await withTokenRefresh((requestToken) => widgetApi.deleteSession(requestToken, sessionId));
      sessions.value = sessions.value.filter((session) => session.session_id !== sessionId);
      if (currentSessionId.value === sessionId) {
        startNewConversation();
      }
    } catch (err) {
      error.value = errorMessage(err, "删除历史对话失败。");
    }
  }

  async function submitFeedback(message: WidgetMessage, value: "helpful" | "not_helpful") {
    if (!message.logId || message.feedbackSubmitting) {
      return;
    }
    message.feedbackSubmitting = true;
    try {
      await withTokenRefresh((requestToken) =>
        widgetApi.submitFeedback(requestToken, message.logId as number, value),
      );
      message.feedback = value;
    } catch (err) {
      error.value = errorMessage(err, "提交反馈失败。");
    } finally {
      message.feedbackSubmitting = false;
    }
  }

  watch(
    token,
    (nextToken, previousToken) => {
      if (!previousToken || !nextToken) {
        void loadBootstrap(true);
      }
    },
    { immediate: true },
  );

  watch(
    () => pageContext.value.page_type,
    (nextPageType, previousPageType) => {
      if (previousPageType && nextPageType !== previousPageType) {
        void loadBootstrap(false);
      }
    },
  );

  onBeforeUnmount(stopGenerating);

  return {
    activityText,
    assistantName,
    contextLabel,
    currentSessionId,
    deleteSession,
    error,
    greeting,
    isInitializing,
    isLoadingSessions,
    isTyping,
    loadSessions,
    messages,
    placeholder,
    scrollRef,
    selectSession,
    sendMessage,
    sessions,
    startNewConversation,
    stopGenerating,
    submitFeedback,
    suggestions,
    workflowRun,
  };
}
