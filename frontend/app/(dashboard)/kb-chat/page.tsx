"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BookOpen,
  Copy,
  Keyboard,
  Library,
  Loader2,
  MessageSquare,
  PanelRight,
  SendHorizontal,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Toaster, toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { AnswerMarkdown } from "@/components/kb-chat/AnswerMarkdown";
import { SourcesPanel } from "@/components/kb-chat/SourcesPanel";
import { useKbChat } from "@/hooks/useKbChat";

const SUGGESTED_PROMPTS = [
  "请根据知识库内容概括产品的核心能力或目标。",
  "和当前主题相关的流程、步骤或规范有哪些要点？",
  "有哪些需要特别注意的限制、风险或边界条件？",
];

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
    query,
    setQuery,
    knowledgeBaseId,
    setKnowledgeBaseId,
    categoryId,
    setCategoryId,
    knowledgeBases,
    categories,
    loading,
    turns,
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
    submit,
  } = useKbChat();

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({
      top: el.scrollHeight,
      behavior: loading ? "auto" : "smooth",
    });
  }, [turns, loading]);

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

  const chatColumn = (
    <section className="flex h-full min-h-0 min-w-0 flex-1 flex-col rounded-2xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.04]">
      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 scroll-smooth md:px-6"
      >
        {turns.length === 0 ? (
          <div className="relative mx-auto flex max-w-lg flex-col items-center justify-center py-14 text-center">
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
              选择检索范围并输入问题，系统会基于知识库内容检索资料并流式生成回答。
            </p>
            <p className="mt-8 text-[11px] font-semibold uppercase tracking-widest text-slate-400">
              可以这样问
            </p>
            <div className="mt-3 flex w-full max-w-md flex-col gap-2">
              {SUGGESTED_PROMPTS.map((item) => (
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
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-10">
            <AnimatePresence initial={false}>
              {turns.map((turn) => (
                <motion.div
                  key={turn.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                  className="space-y-4"
                >
                  <div className="flex justify-end">
                    <div className="max-w-[min(100%,36rem)] rounded-2xl rounded-br-md bg-gradient-to-br from-teal-600 to-emerald-700 px-4 py-3.5 text-[15px] leading-relaxed text-white shadow-md shadow-teal-700/20">
                      {turn.query}
                    </div>
                  </div>
                  <div className="flex justify-start">
                    <div className="w-full max-w-[min(100%,40rem)] rounded-2xl rounded-bl-md border border-slate-100 bg-slate-50/95 px-4 py-4 shadow-sm">
                      <div className="mb-3 flex items-center justify-between gap-2 border-b border-slate-200/60 pb-2">
                        <span className="flex items-center gap-2 text-xs font-medium text-slate-500">
                          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-teal-100 text-teal-700">
                            <Library className="h-3.5 w-3.5" />
                          </span>
                          知识库回答
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
              placeholder="输入你想从知识库了解的内容..."
              disabled={loading}
              rows={2}
              className="!min-h-[44px] max-h-[min(200px,32vh)] resize-y rounded-lg border-slate-200 bg-white py-2 text-sm leading-snug focus-visible:ring-2 focus-visible:ring-teal-600/40 md:text-[15px]"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
              <label
                htmlFor="kb-collection"
                className="shrink-0 whitespace-nowrap text-xs text-slate-500"
              >
                检索范围
              </label>
              <select
                id="kb-collection"
                value={knowledgeBaseId ?? ""}
                  onChange={(e) => {
                    const nextValue = e.target.value ? Number(e.target.value) : null;
                    setKnowledgeBaseId(nextValue);
                    setCategoryId(null);
                  }}
                className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-sm text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-600/30 sm:min-w-[180px] sm:w-auto"
                disabled={loading}
              >
                <option value="">全部知识库</option>
                {knowledgeBases.map((collection) => (
                  <option key={collection.id} value={collection.id}>
                    {collection.name}（{collection.document_count} 篇）
                  </option>
                ))}
                </select>
              </div>

              <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
                <label
                  htmlFor="kb-category"
                  className="shrink-0 whitespace-nowrap text-xs text-slate-500"
                >
                  分类
                </label>
                <select
                  id="kb-category"
                  value={categoryId ?? ""}
                  onChange={(e) =>
                    setCategoryId(e.target.value ? Number(e.target.value) : null)
                  }
                  className="h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-sm text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-600/30 sm:min-w-[180px] sm:w-auto"
                  disabled={loading || !knowledgeBaseId}
                >
                  <option value="">{knowledgeBaseId ? "全部分类" : "先选择知识库"}</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}（{category.document_count}）
                    </option>
                  ))}
                </select>
              </div>

            <Button
              type="submit"
              disabled={loading || !query.trim()}
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

          {knowledgeBases.length === 0 && (
            <p className="text-[11px] text-amber-700/90">
              当前还没有可用的文档集合，请先到“文档库”创建并上传文档。
            </p>
          )}
        </form>
      </div>
    </section>
  );

  const sourcesAside = (
    <aside className="flex h-full min-h-0 overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.04] lg:w-[min(100%,400px)] lg:shrink-0">
      <SourcesPanel
        knowledgeBaseLabel={knowledgeBaseLabel}
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
                基于已索引文档进行问答，支持流式输出，并展示命中的资料摘录。
              </p>
            </div>
          </div>

          {turns.length > 0 && (
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
              <Trash2 className="h-3.5 w-3.5" />
              清空对话
            </Button>
          )}
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
