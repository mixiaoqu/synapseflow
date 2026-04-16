"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bot,
  BookOpen,
  Copy,
  History,
  Keyboard,
  Library,
  Loader2,
  MessageSquare,
  PanelRight,
  Plus,
  SendHorizontal,
  Sparkles,
} from "lucide-react";
import { Toaster, toast } from "sonner";
import { AnswerMarkdown } from "@/components/kb-chat/AnswerMarkdown";
import { SourcesPanel } from "@/components/kb-chat/SourcesPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useAssistantChat } from "@/hooks/useAssistantChat";

function buildFallbackPrompts(assistantName: string): string[] {
  return [
    `${assistantName} 可以帮我解答哪些问题？`,
    `请告诉我最常见的操作流程。`,
    `如果我是新用户，应该从哪里开始？`,
  ];
}

function StreamingSkeleton() {
  return (
    <div className="space-y-2.5 py-1" aria-hidden>
      <div className="h-4 w-full max-w-[95%] rounded-md bg-slate-200/80" />
      <div className="h-4 w-full max-w-[88%] rounded-md bg-slate-200/80" />
      <div className="h-4 w-full max-w-[72%] rounded-md bg-slate-200/70" />
    </div>
  );
}

export default function KbChatPage() {
  const {
    teamId,
    setTeamId,
    teams,
    teamsLoading,
    selectedTeam,
    assistants,
    assistantsLoading,
    selectedAssistant,
    setSelectedAssistantId,
    query,
    setQuery,
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
    lastTurn,
    sourceDocs,
    toggleChunk,
    expandAllChunks,
    collapseAllChunks,
    resetConversation,
    openSession,
    submit,
  } = useAssistantChat();

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({
      top: el.scrollHeight,
      behavior: loading ? "auto" : "smooth",
    });
  }, [loading, turns]);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const submitted = await submit();
    if (!submitted) return;
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const onTextareaKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== "Enter") return;
    if (e.shiftKey) return;
    if (e.nativeEvent.isComposing) return;
    if (e.metaKey || e.ctrlKey) {
      e.preventDefault();
      void handleSubmit();
    }
  };

  const suggestedPrompts = selectedAssistant?.suggested_prompts ?? [];
  const effectivePrompts =
    suggestedPrompts.length > 0
      ? suggestedPrompts
      : selectedAssistant
        ? buildFallbackPrompts(selectedAssistant.name)
        : [];

  const assistantHeader = selectedAssistant ? (
    <div className="mb-4 rounded-2xl border border-teal-200/80 bg-gradient-to-r from-teal-50/80 to-emerald-50/40 px-4 py-3 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-teal-500 to-emerald-600 text-white shadow-md">
          <Bot className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-900">{selectedAssistant.name}</span>
            <span className="rounded-full bg-teal-100 px-2 py-0.5 text-[11px] text-teal-700 font-medium">
              {selectedAssistant.slug}
            </span>
          </div>
          {selectedAssistant.description && (
            <p className="mt-0.5 text-xs text-slate-500 line-clamp-1">
              {selectedAssistant.description}
            </p>
          )}
        </div>
      </div>
      {selectedAssistant.welcome_message && (
        <div className="mt-2 flex items-start gap-2">
          <MessageSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-600" />
          <p className="text-xs text-teal-800 leading-relaxed">
            {selectedAssistant.welcome_message}
          </p>
        </div>
      )}
      {effectivePrompts.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {effectivePrompts.slice(0, 3).map((prompt) => (
            <button
              key={prompt}
              type="button"
              disabled={loading}
              onClick={() => {
                setQuery(prompt);
                requestAnimationFrame(() => textareaRef.current?.focus());
              }}
              className="rounded-full border border-teal-200/80 bg-white px-2.5 py-1 text-[11px] text-slate-600 shadow-sm transition-all hover:border-teal-400 hover:bg-teal-50 disabled:opacity-50"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}
    </div>
  ) : null;

  const chatColumn = (
    <section className="flex h-full min-h-0 min-w-0 flex-1 flex-col rounded-2xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.04]">
      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 scroll-smooth md:px-6"
      >
        {turns.length === 0 ? (
          <div className="relative mx-auto flex max-w-lg flex-col items-center justify-center py-14 text-center">
            {sessionLoading ? (
              <div className="flex flex-col items-center gap-3 rounded-2xl border border-teal-100 bg-teal-50/80 px-6 py-8 text-center shadow-sm">
                <Loader2 className="h-6 w-6 animate-spin text-teal-600" />
                <div>
                  <p className="text-sm font-medium text-slate-700">正在恢复历史会话</p>
                  <p className="mt-1 text-xs text-slate-500">稍等一下，旧消息马上回来。</p>
                </div>
              </div>
            ) : !selectedAssistant ? (
              <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-emerald-700 text-white shadow-lg shadow-teal-600/25">
                  <Bot className="h-7 w-7" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">
                    {assistantsLoading ? "加载助手列表中..." : "当前项目下没有可用助手"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {assistantsLoading
                      ? "请稍候"
                      : "请联系管理员配置助手后再来使用。"}
                  </p>
                </div>
              </div>
            ) : (
              <>
                <div
                  className="pointer-events-none absolute inset-0 -z-10 opacity-[0.35]"
                  style={{
                    backgroundImage:
                      "radial-gradient(circle at 1px 1px, rgb(148 163 184 / 0.45) 1px, transparent 0)",
                    backgroundSize: "20px 20px",
                  }}
                />
                <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-emerald-700 text-white shadow-lg shadow-teal-600/25">
                  <Sparkles className="h-8 w-8" />
                </div>
                <h2 className="text-lg font-semibold text-slate-800">开始提问</h2>
                <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-500">
                  选择下方助手后，输入你想咨询的问题，系统会基于该助手绑定的知识库检索资料并生成回答。
                </p>
                {effectivePrompts.length > 0 && (
                  <>
                    <p className="mt-8 text-[11px] font-semibold uppercase tracking-widest text-slate-400">
                      推荐问题
                    </p>
                    <div className="mt-3 flex w-full max-w-md flex-col gap-2">
                      {effectivePrompts.slice(0, 3).map((item) => (
                        <button
                          key={item}
                          type="button"
                          disabled={loading}
                          onClick={() => {
                            setQuery(item);
                            requestAnimationFrame(() => textareaRef.current?.focus());
                          }}
                          className="rounded-xl border border-slate-200/90 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm transition-all hover:border-teal-300 hover:bg-teal-50/40 hover:shadow-md disabled:opacity-50 active:scale-[0.99]"
                        >
                          {item}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-10">
            {assistantHeader}

            {sessionLoading ? (
              <div className="flex items-center gap-2 rounded-xl border border-teal-100 bg-teal-50/80 px-4 py-3 text-sm text-teal-700">
                <Loader2 className="h-4 w-4 animate-spin" />
                正在加载历史会话...
              </div>
            ) : null}

            <AnimatePresence initial={false}>
              {turns.map((turn) => (
                <motion.div
                  key={turn.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                  className="space-y-4"
                >
                  {turn.query ? (
                    <div className="flex justify-end">
                      <div className="max-w-[min(100%,36rem)] rounded-2xl rounded-br-md bg-gradient-to-br from-teal-600 to-emerald-700 px-4 py-3.5 text-[15px] leading-relaxed text-white shadow-md shadow-teal-700/20">
                        {turn.query}
                      </div>
                    </div>
                  ) : null}

                  <div className="flex justify-start">
                    <div className="w-full max-w-[min(100%,40rem)] rounded-2xl rounded-bl-md border border-slate-100 bg-slate-50/95 px-4 py-4 shadow-sm">
                      <div className="mb-3 flex items-center justify-between gap-2 border-b border-slate-200/60 pb-2">
                        <span className="flex items-center gap-2 text-xs font-medium text-slate-500">
                          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-teal-100 text-teal-700">
                            <Library className="h-3.5 w-3.5" />
                          </span>
                          {selectedAssistant?.name ?? "助手"}回答
                        </span>
                        {turn.answer ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-8 gap-1 px-2 text-xs text-slate-600"
                            onClick={() => {
                              void navigator.clipboard.writeText(turn.answer).then(() => {
                                toast.success("已复制本轮回答");
                              });
                            }}
                          >
                            <Copy className="h-3.5 w-3.5" />
                            复制
                          </Button>
                        ) : null}
                      </div>

                      {turn.error ? (
                        <p className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-600">
                          {turn.error}
                        </p>
                      ) : null}

                      {!turn.error &&
                      !turn.answer &&
                      loading &&
                      turn.id === turns[turns.length - 1]?.id ? (
                        <div className="space-y-3">
                          <div className="flex items-center gap-2 text-sm text-slate-500">
                            <Loader2 className="h-4 w-4 animate-spin text-teal-600" />
                            正在检索资料并生成回答...
                          </div>
                          <StreamingSkeleton />
                        </div>
                      ) : null}

                      {turn.answer ? <AnswerMarkdown text={turn.answer} /> : null}
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      <Separator className="shrink-0 opacity-60" />

      <div className="shrink-0 border-t border-slate-200/90 bg-white/95 px-3 py-2.5 shadow-[0_-6px_24px_-10px_rgba(15,23,42,0.12)] backdrop-blur-sm md:px-4">
        <form onSubmit={handleSubmit} className="mx-auto max-w-3xl space-y-2">
          <div className="space-y-1">
            <div className="flex items-center justify-between gap-2">
              <label htmlFor="kb-query" className="text-xs font-medium text-slate-600">
                问题
              </label>
              <span className="hidden items-center gap-1 text-[10px] text-slate-400 sm:inline-flex">
                <Keyboard className="h-3 w-3" />
                Ctrl+Enter 发送 · Shift+Enter 换行
              </span>
            </div>
            <Textarea
              ref={textareaRef}
              id="kb-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onTextareaKeyDown}
              placeholder={
                selectedAssistant?.placeholder_text
                  ? selectedAssistant.placeholder_text
                  : "输入你想咨询的问题..."
              }
              disabled={loading || selectedAssistant == null}
              rows={2}
              className="!min-h-[44px] max-h-[min(200px,32vh)] resize-y rounded-lg border-slate-200 bg-white py-2 text-sm leading-snug focus-visible:ring-2 focus-visible:ring-teal-600/40 md:text-[15px]"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
              <label
                htmlFor="kb-team"
                className="shrink-0 whitespace-nowrap text-xs text-slate-500"
              >
                项目
              </label>
              <select
                id="kb-team"
                value={teamId ?? ""}
                onChange={(e) => {
                  const nextValue = e.target.value ? Number(e.target.value) : null;
                  setTeamId(nextValue);
                  setSelectedAssistantId(null);
                }}
                disabled={loading || teamsLoading}
                className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-sm text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-600/30 sm:min-w-[160px] sm:w-auto"
              >
                <option value="">全部项目</option>
                {teams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
              <label
                htmlFor="assistant-select"
                className="shrink-0 whitespace-nowrap text-xs text-slate-500"
              >
                助手
              </label>
              <select
                id="assistant-select"
                value={selectedAssistant?.id ?? ""}
                onChange={(e) => {
                  const nextValue = e.target.value ? Number(e.target.value) : null;
                  setSelectedAssistantId(nextValue);
                }}
                disabled={loading || assistantsLoading || teamId == null}
                className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-sm text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-600/30 sm:min-w-[180px] sm:w-auto disabled:bg-slate-50 disabled:text-slate-400"
              >
                {assistants.length === 0 && teamId != null ? (
                  <option value="">当前项目无助手</option>
                ) : (
                  <option value="">
                    {assistantsLoading ? "加载中..." : "请选择助手"}
                  </option>
                )}
                {assistants.map((assistant) => (
                  <option key={assistant.id} value={assistant.id}>
                    {assistant.name}
                  </option>
                ))}
              </select>
            </div>

            <Button
              type="submit"
              disabled={loading || !query.trim() || selectedAssistant == null}
              className="h-9 gap-1.5 rounded-lg bg-gradient-to-r from-teal-600 to-emerald-600 px-4 text-sm shadow-md shadow-teal-600/20 hover:from-teal-700 hover:to-emerald-700"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  生成中
                </>
              ) : (
                <>
                  <SendHorizontal className="h-4 w-4" />
                  发送
                </>
              )}
            </Button>
          </div>

          {selectedTeam && assistants.length === 0 && !assistantsLoading ? (
            <p className="text-[11px] text-amber-700/90">
              当前项目下还没有配置助手，请联系管理员添加。
            </p>
          ) : null}
        </form>
      </div>
    </section>
  );

  const sourcesAside = (
    <aside className="flex h-full min-h-0 overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.04] lg:w-[min(100%,400px)] lg:shrink-0">
      <SourcesPanel
        knowledgeBaseLabel={selectedAssistant?.name ?? "助手"}
        sourceDocs={sourceDocs}
        lastTurn={lastTurn}
        loading={loading}
        expandedChunks={expandedChunks}
        onToggleChunk={toggleChunk}
        onExpandAll={expandAllChunks}
        onCollapseAll={collapseAllChunks}
      />
    </aside>
  );

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-gradient-to-br from-slate-50 via-white to-teal-50/20">
      <Toaster position="top-right" richColors />

      <header className="shrink-0 border-b border-slate-200/80 bg-white/85 px-4 py-3.5 backdrop-blur-md sm:px-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-teal-600 to-emerald-700 text-white shadow-lg shadow-teal-600/25">
              <BookOpen className="h-5 w-5" aria-hidden />
            </div>
            <div className="min-w-0">
              <h1 className="text-lg font-semibold tracking-tight text-slate-900 sm:text-xl">
                知识库问答
              </h1>
              <p className="mt-0.5 max-w-xl text-xs leading-snug text-slate-500 sm:text-sm">
                基于助手配置的知识库进行问答，支持流式输出，并展示命中的资料摘录。
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex min-w-[230px] max-w-full items-center gap-2 rounded-lg border border-slate-200 bg-white/90 px-2.5 py-1.5 shadow-sm">
              <History className="h-4 w-4 shrink-0 text-slate-400" />
              <select
                value={activeSessionId ?? ""}
                onChange={(e) => {
                  const nextSessionId = e.target.value;
                  if (!nextSessionId) return;
                  void openSession(nextSessionId);
                }}
                disabled={loading || historyLoading || sessions.length === 0}
                className="min-w-0 flex-1 bg-transparent text-sm text-slate-700 outline-none"
              >
                <option value="">
                  {historyLoading ? "加载历史会话..." : sessions.length > 0 ? "选择历史会话" : "暂无历史会话"}
                </option>
                {sessions.map((session) => (
                  <option key={session.session_id} value={session.session_id}>
                    {session.title}
                  </option>
                ))}
              </select>
              {sessionLoading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-teal-600" />
              ) : null}
            </div>

            <Button
              type="button"
              variant="outline"
              size="sm"
              className="shrink-0 gap-1.5 rounded-lg border-slate-200 text-slate-600 hover:bg-slate-50"
              onClick={() => {
                resetConversation();
                requestAnimationFrame(() => textareaRef.current?.focus());
              }}
            >
              <Plus className="h-3.5 w-3.5" />
              新建对话
            </Button>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col p-3 sm:p-4 lg:min-h-[calc(100dvh-7.5rem)]">
        <div className="flex min-h-0 flex-1 flex-col lg:hidden">
          <Tabs
            value={mobileTab}
            onValueChange={(value) => setMobileTab(value as "chat" | "sources")}
            className="flex min-h-0 flex-1 flex-col gap-0"
          >
            <TabsList className="grid h-11 w-full shrink-0 grid-cols-2 rounded-xl bg-slate-100/90 p-1">
              <TabsTrigger
                value="chat"
                className="gap-1.5 rounded-lg data-[state=active]:shadow-sm"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                对话
              </TabsTrigger>
              <TabsTrigger
                value="sources"
                className="gap-1.5 rounded-lg data-[state=active]:shadow-sm"
              >
                <PanelRight className="h-3.5 w-3.5" />
                摘录
                {sourceDocs.length > 0 ? (
                  <Badge
                    variant="secondary"
                    className="ml-0.5 h-5 min-w-5 px-1 text-[10px] tabular-nums"
                  >
                    {sourceDocs.length}
                  </Badge>
                ) : null}
              </TabsTrigger>
            </TabsList>
            <TabsContent
              value="chat"
              className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden data-[state=inactive]:hidden"
            >
              {chatColumn}
            </TabsContent>
            <TabsContent
              value="sources"
              className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden data-[state=inactive]:hidden"
            >
              {sourcesAside}
            </TabsContent>
          </Tabs>
        </div>

        <div className="hidden min-h-0 flex-1 gap-4 overflow-hidden lg:flex lg:flex-row">
          {chatColumn}
          {sourcesAside}
        </div>
      </div>
    </div>
  );
}
