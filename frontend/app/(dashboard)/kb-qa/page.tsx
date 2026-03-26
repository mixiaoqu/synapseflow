'use client';

/**
 * 知识库单轮问答：检索 + 流式回答；对话区 + 资料摘录 + 底部提问栏。
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { listCollections, type CollectionWithCount } from '@/lib/api/collections';
import { API_V1 } from '@/lib/api/config';
import { Toaster, toast } from 'sonner';
import ReactMarkdown from 'react-markdown';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Copy,
  FolderOpen,
  Keyboard,
  Library,
  Loader2,
  MessageSquare,
  PanelRight,
  SendHorizontal,
  Sparkles,
  Trash2,
  UnfoldVertical,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface StreamEnvelope {
  type: string;
  data: Record<string, unknown>;
}

function parseSseBlock(block: string): StreamEnvelope | null {
  const m = block.match(/event:\s*\w+\ndata:\s*(.+)/s);
  if (!m) return null;
  let raw = m[1].trim();
  if (raw.endsWith('\n')) raw = raw.replace(/\n+$/, '');
  try {
    const o = JSON.parse(raw) as StreamEnvelope;
    if (typeof o.type === 'string' && o.data && typeof o.data === 'object') return o;
  } catch {
    return null;
  }
  return null;
}

interface RetrievedDoc {
  content: string;
  metadata?: {
    document_id?: number;
    document_title?: string;
    chunk_index?: number;
  };
}

interface QATurn {
  id: string;
  query: string;
  answer: string;
  retrievedDocs: RetrievedDoc[];
  error: string | null;
}

const SUGGESTED_PROMPTS = [
  '请根据知识库简要说明核心功能或目标是什么？',
  '相关流程、步骤或规范有哪些要点？',
  '有哪些需要特别注意的限制或风险？',
];

function truncateText(s: string, max: number): string {
  const t = s.replace(/\s+/g, ' ').trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

function SourceChunkCard({
  doc,
  index,
  expanded,
  onToggle,
}: {
  doc: RetrievedDoc;
  index: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const title =
    doc.metadata?.document_title?.trim() ||
    `摘录片段 ${index + 1}`;
  const body = doc.content?.trim() || '';
  const previewLen = 220;
  const needsExpand = body.length > previewLen;

  return (
    <div className="rounded-xl border border-slate-200/90 bg-white/90 shadow-sm ring-1 ring-slate-900/[0.02] transition-shadow hover:shadow-md">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-2.5 px-3.5 py-3 text-left rounded-xl hover:bg-teal-50/40 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-teal-600 mt-0.5" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-slate-400 mt-0.5" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-800">{title}</span>
            {doc.metadata?.chunk_index != null && (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-normal tabular-nums">
                块 #{doc.metadata.chunk_index}
              </Badge>
            )}
          </div>
          <p className="mt-1.5 text-xs text-slate-600 leading-relaxed">
            {expanded || !needsExpand ? body : truncateText(body, previewLen)}
          </p>
          {needsExpand && (
            <span className="text-[11px] font-medium text-teal-700 mt-1.5 inline-block">
              {expanded ? '收起' : '展开全文'}
            </span>
          )}
        </div>
      </button>
    </div>
  );
}

function AnswerMarkdown({ text }: { text: string }) {
  return (
    <div className="text-[15px] leading-7 text-slate-800 selection:bg-teal-100 selection:text-slate-900">
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
          ul: ({ children }) => (
            <ul className="mb-3 list-disc pl-5 space-y-1.5 last:mb-0 marker:text-teal-600">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-3 list-decimal pl-5 space-y-1.5 last:mb-0">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
          pre: ({ children }) => (
            <pre className="my-2 overflow-x-auto rounded-xl bg-slate-900 p-3.5 text-[13px] font-mono text-slate-100 border border-slate-700/50">
              {children}
            </pre>
          ),
          code: ({ className, children, ...props }) => {
            const block = Boolean(className);
            if (block) {
              return (
                <code className={cn('font-mono text-inherit', className)} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code
                className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[13px] font-mono text-slate-800"
                {...props}
              >
                {children}
              </code>
            );
          },
          h1: ({ children }) => (
            <h3 className="text-base font-semibold text-slate-900 mt-4 mb-2 first:mt-0">{children}</h3>
          ),
          h2: ({ children }) => (
            <h3 className="text-base font-semibold text-slate-900 mt-4 mb-2 first:mt-0">{children}</h3>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-semibold text-slate-900 mt-3 mb-1.5">{children}</h3>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
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

interface SourcesPanelProps {
  collectionLabel: string;
  sourceDocs: RetrievedDoc[];
  lastTurn: QATurn | null;
  loading: boolean;
  expandedChunks: Set<string>;
  onToggleChunk: (key: string) => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  className?: string;
}

function SourcesPanel({
  collectionLabel,
  sourceDocs,
  lastTurn,
  loading,
  expandedChunks,
  onToggleChunk,
  onExpandAll,
  onCollapseAll,
  className,
}: SourcesPanelProps) {
  const uniqueDocCount = new Set(
    sourceDocs
      .map((d) => d.metadata?.document_id)
      .filter((id): id is number => id != null),
  ).size;
  const canExpandOps = lastTurn && sourceDocs.length > 0;

  return (
    <div className={cn('flex min-h-0 flex-1 flex-col overflow-hidden bg-gradient-to-b from-white to-slate-50/50', className)}>
      <div className="shrink-0 border-b border-slate-100/90 px-4 py-3.5">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <PanelRight className="h-4 w-4 text-teal-600" />
              本轮资料摘录
            </h2>
            <p className="mt-1 text-xs text-slate-500 leading-relaxed">
              检索到的原文片段，可与左侧回答对照
            </p>
          </div>
          {canExpandOps ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 shrink-0 gap-1 px-2 text-xs text-slate-600"
              onClick={() => {
                const allKeys = sourceDocs.map((_, i) => `${lastTurn!.id}-${i}`);
                const allExpanded = allKeys.every((k) => expandedChunks.has(k));
                if (allExpanded) onCollapseAll();
                else onExpandAll();
              }}
            >
              <UnfoldVertical className="h-3.5 w-3.5" />
              {sourceDocs.length > 0 &&
              sourceDocs.every((_, i) => expandedChunks.has(`${lastTurn!.id}-${i}`))
                ? '全部收起'
                : '全部展开'}
            </Button>
          ) : null}
        </div>
        <div className="mt-2.5 flex flex-wrap gap-2">
          <Badge variant="outline" className="font-normal text-slate-600 border-slate-200">
            <FolderOpen className="h-3 w-3 mr-1 opacity-70" />
            {collectionLabel}
          </Badge>
          {sourceDocs.length > 0 && (
            <Badge className="font-normal bg-teal-600/10 text-teal-800 hover:bg-teal-600/15 border border-teal-200/60">
              {sourceDocs.length} 条片段
              {uniqueDocCount > 0 ? ` · ${uniqueDocCount} 个文档` : ''}
            </Badge>
          )}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3 space-y-2.5 overscroll-contain">
        {!lastTurn ? (
          <p className="text-xs text-slate-400 px-1 py-8 text-center leading-relaxed">
            发送问题后，这里会展示检索摘录，便于核对答案是否有据可依。
          </p>
        ) : sourceDocs.length === 0 ? (
          <div className="px-1 py-8 text-center">
            <p className="text-xs text-slate-500 leading-relaxed">
              {loading
                ? '正在检索…'
                : '本轮未返回摘录。若已上传文档仍无结果，请到「文档库」检查索引。'}
            </p>
          </div>
        ) : (
          sourceDocs.map((doc, i) => {
            const key = `${lastTurn.id}-${i}`;
            return (
              <SourceChunkCard
                key={key}
                doc={doc}
                index={i}
                expanded={expandedChunks.has(key)}
                onToggle={() => onToggleChunk(key)}
              />
            );
          })
        )}
      </div>
    </div>
  );
}

export default function KbQAPage() {
  const [query, setQuery] = useState('');
  const [collectionId, setCollectionId] = useState<number | null>(null);
  const [collections, setCollections] = useState<CollectionWithCount[]>([]);
  const [loading, setLoading] = useState(false);
  const [turns, setTurns] = useState<QATurn[]>([]);
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());
  const [mobileTab, setMobileTab] = useState<'chat' | 'sources'>('chat');

  const activeTurnIdRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const loadCollections = useCallback(async () => {
    try {
      setCollections(await listCollections());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void loadCollections();
  }, [loadCollections]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    // 流式输出时避免 smooth + layout 动画叠加导致气泡区域抖动，用 auto 跟底
    el.scrollTo({
      top: el.scrollHeight,
      behavior: loading ? 'auto' : 'smooth',
    });
  }, [turns, loading]);

  const toggleChunk = (key: string) => {
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const expandAllChunks = () => {
    const t = turns[turns.length - 1];
    if (!t?.retrievedDocs.length) return;
    setExpandedChunks(new Set(t.retrievedDocs.map((_, i) => `${t.id}-${i}`)));
  };

  const collapseAllChunks = () => setExpandedChunks(new Set());

  const collectionLabel =
    collectionId && collectionId > 0
      ? collections.find((c) => c.id === collectionId)?.name ?? '指定集合'
      : '全部知识库';

  const lastTurn = turns.length > 0 ? turns[turns.length - 1] : null;
  const sourceDocs = lastTurn?.retrievedDocs ?? [];

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const q = query.trim();
    if (!q || loading) return;

    const turnId = crypto.randomUUID();
    activeTurnIdRef.current = turnId;
    setLoading(true);
    setQuery('');
    setMobileTab('chat');
    setTurns((prev) => [
      ...prev,
      { id: turnId, query: q, answer: '', retrievedDocs: [], error: null },
    ]);
    setExpandedChunks(new Set());

    try {
      const res = await fetch(`${API_V1}/kb-qa/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: q,
          collection_id: collectionId && collectionId > 0 ? collectionId : null,
        }),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(
          typeof errBody.detail === 'string' ? errBody.detail : `HTTP ${res.status}`,
        );
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('无法读取响应流');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const block of parts) {
          if (!block.trim()) continue;
          const env = parseSseBlock(block);
          if (!env) continue;

          const tid = activeTurnIdRef.current;
          if (!tid) continue;

          switch (env.type) {
            case 'retrieved': {
              const docs = env.data.retrieved_docs;
              if (Array.isArray(docs)) {
                setTurns((prev) =>
                  prev.map((t) =>
                    t.id === tid ? { ...t, retrievedDocs: docs as RetrievedDoc[] } : t,
                  ),
                );
              }
              break;
            }
            case 'token': {
              const t = env.data.text;
              if (typeof t === 'string' && t) {
                setTurns((prev) =>
                  prev.map((row) =>
                    row.id === tid ? { ...row, answer: row.answer + t } : row,
                  ),
                );
              }
              break;
            }
            case 'done':
              break;
            case 'error': {
              const msg = String(env.data.message ?? '流式失败');
              setTurns((prev) =>
                prev.map((row) => (row.id === tid ? { ...row, error: msg } : row)),
              );
              toast.error(msg);
              break;
            }
            default:
              break;
          }
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : '请求失败';
      const tid = activeTurnIdRef.current;
      if (tid) {
        setTurns((prev) =>
          prev.map((row) => (row.id === tid ? { ...row, error: msg } : row)),
        );
      }
      toast.error(msg);
    } finally {
      setLoading(false);
      activeTurnIdRef.current = null;
      textareaRef.current?.focus();
    }
  };

  const onTextareaKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== 'Enter') return;
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
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 md:px-6 scroll-smooth"
      >
        {turns.length === 0 ? (
          <div className="relative mx-auto flex max-w-lg flex-col items-center justify-center py-14 text-center">
            <div
              className="pointer-events-none absolute inset-0 -z-10 opacity-[0.35]"
              style={{
                backgroundImage: `radial-gradient(circle at 1px 1px, rgb(148 163 184 / 0.45) 1px, transparent 0)`,
                backgroundSize: '20px 20px',
              }}
            />
            <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-emerald-700 text-white shadow-lg shadow-teal-600/25">
              <Sparkles className="h-8 w-8" />
            </div>
            <h2 className="text-lg font-semibold text-slate-800">开始提问</h2>
            <p className="mt-2 text-sm text-slate-500 leading-relaxed max-w-sm">
              选择检索范围，输入问题。系统将检索相关片段并流式生成回答。
            </p>
            <p className="mt-8 text-[11px] font-semibold uppercase tracking-widest text-slate-400">
              试试这样问
            </p>
            <div className="mt-3 flex w-full max-w-md flex-col gap-2">
              {SUGGESTED_PROMPTS.map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={loading}
                  onClick={() => {
                    setQuery(s);
                    requestAnimationFrame(() => textareaRef.current?.focus());
                  }}
                  className="rounded-xl border border-slate-200/90 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm transition-all hover:border-teal-300 hover:bg-teal-50/40 hover:shadow-md disabled:opacity-50 active:scale-[0.99]"
                >
                  {s}
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
                  transition={{ duration: 0.2, ease: 'easeOut' }}
                  className="space-y-4"
                >
                  <div className="flex justify-end">
                    <div className="max-w-[min(100%,36rem)] rounded-2xl rounded-br-md bg-gradient-to-br from-teal-600 to-emerald-700 px-4 py-3.5 text-[15px] leading-relaxed text-white shadow-md shadow-teal-700/20">
                      {turn.query}
                    </div>
                  </div>
                  <div className="flex justify-start">
                    <div className="max-w-[min(100%,40rem)] w-full rounded-2xl rounded-bl-md border border-slate-100 bg-slate-50/95 px-4 py-4 shadow-sm">
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
                                toast.success('已复制本回答');
                              });
                            }}
                          >
                            <Copy className="h-3.5 w-3.5" />
                            复制
                          </Button>
                        ) : null}
                      </div>
                      {turn.error ? (
                        <p className="text-sm text-red-600 rounded-lg bg-red-50 px-3 py-2 border border-red-100">
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
                            正在检索并生成回答…
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

      <Separator className="opacity-60 shrink-0" />

      <div className="shrink-0 border-t border-slate-200/90 bg-white/95 px-3 py-2.5 shadow-[0_-6px_24px_-10px_rgba(15,23,42,0.12)] backdrop-blur-sm md:px-4">
        <form
          onSubmit={handleSubmit}
          className="mx-auto max-w-3xl space-y-2"
        >
          <div className="space-y-1">
            <div className="flex items-center justify-between gap-2">
              <label htmlFor="kb-query" className="text-xs font-medium text-slate-600">
                问题
              </label>
              <span className="hidden sm:inline-flex items-center gap-1 text-[10px] text-slate-400">
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
              placeholder="输入要从知识库了解的内容…"
              disabled={loading}
              rows={2}
              className="!min-h-[44px] max-h-[min(200px,32vh)] resize-y border-slate-200 bg-white py-2 text-sm leading-snug rounded-lg focus-visible:ring-2 focus-visible:ring-teal-600/40 md:text-[15px]"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
              <label htmlFor="kb-collection" className="text-xs text-slate-500 shrink-0 whitespace-nowrap">
                检索范围
              </label>
              <select
                id="kb-collection"
                value={collectionId ?? ''}
                onChange={(e) =>
                  setCollectionId(e.target.value ? Number(e.target.value) : null)
                }
                className="h-9 w-full sm:w-auto sm:min-w-[180px] rounded-lg border border-slate-200 bg-white px-2.5 text-sm text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-600/30"
                disabled={loading}
              >
                <option value="">全部知识库</option>
                {collections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}（{c.document_count} 篇）
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
          {collections.length === 0 && (
            <p className="text-[11px] text-amber-700/90">
              暂无文档集合，请先在「文档库」中创建并上传文档。
            </p>
          )}
        </form>
      </div>
    </section>
  );

  const sourcesPanel = (
    <aside className="flex h-full min-h-0 overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.04] lg:w-[min(100%,400px)] lg:shrink-0">
      <SourcesPanel
        collectionLabel={collectionLabel}
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

      <header className="shrink-0 border-b border-slate-200/80 bg-white/85 backdrop-blur-md px-4 py-3.5 sm:px-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex gap-3 min-w-0">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-teal-600 to-emerald-700 text-white shadow-lg shadow-teal-600/25">
              <BookOpen className="h-5 w-5" aria-hidden />
            </div>
            <div className="min-w-0">
              <h1 className="text-lg sm:text-xl font-semibold tracking-tight text-slate-900">
                知识库问答
              </h1>
              <p className="mt-0.5 text-xs sm:text-sm text-slate-500 leading-snug max-w-xl">
                基于已索引文档作答；流式输出，引用摘录可核对。
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
                setTurns([]);
                setExpandedChunks(new Set());
                setMobileTab('chat');
                requestAnimationFrame(() => textareaRef.current?.focus());
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
              清空对话
            </Button>
          )}
        </div>
      </header>

      {/* 小屏：Tabs；大屏：并排 */}
      <div className="flex min-h-0 flex-1 flex-col p-3 sm:p-4 lg:min-h-[calc(100dvh-7.5rem)]">
        <div className="lg:hidden flex min-h-0 flex-1 flex-col">
          <Tabs
            value={mobileTab}
            onValueChange={(v) => setMobileTab(v as 'chat' | 'sources')}
            className="flex min-h-0 flex-1 flex-col gap-0"
          >
            <TabsList className="grid w-full grid-cols-2 shrink-0 rounded-xl bg-slate-100/90 p-1 h-11">
              <TabsTrigger value="chat" className="gap-1.5 rounded-lg data-[state=active]:shadow-sm">
                <MessageSquare className="h-3.5 w-3.5" />
                对话
              </TabsTrigger>
              <TabsTrigger value="sources" className="gap-1.5 rounded-lg data-[state=active]:shadow-sm">
                <PanelRight className="h-3.5 w-3.5" />
                资料摘录
                {sourceDocs.length > 0 ? (
                  <Badge variant="secondary" className="ml-0.5 h-5 min-w-5 px-1 text-[10px] tabular-nums">
                    {sourceDocs.length}
                  </Badge>
                ) : null}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="chat" className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden data-[state=inactive]:hidden">
              {chatColumn}
            </TabsContent>
            <TabsContent value="sources" className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden data-[state=inactive]:hidden">
              {sourcesPanel}
            </TabsContent>
          </Tabs>
        </div>

        <div className="hidden min-h-0 flex-1 gap-4 overflow-hidden lg:flex lg:flex-row">
          {chatColumn}
          {sourcesPanel}
        </div>
      </div>
    </div>
  );
}
