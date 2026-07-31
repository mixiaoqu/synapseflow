<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  ArrowDown,
  ArrowUp,
  ChatDotRound,
  CircleCheck,
  CircleClose,
  Clock,
  Connection,
  Document,
  Search,
} from "@element-plus/icons-vue";

import type {
  QaLogDetail,
  QaLogDiagnosticDoc,
  QaLogTracePayload,
} from "@/modules/qa-logs/types";

const props = defineProps<{
  modelValue: boolean;
  detail: QaLogDetail | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
}>();

type QueryStat = { query: string; chunk_count: number };
type SourceKind = "vector" | "lexical" | "graph";
type SubtaskTraceResult = NonNullable<QaLogTracePayload["subtask_results"]>[number];

const emptyReasonMeta: Record<string, { title: string; advice: string }> = {
  disabled: {
    title: "检索能力未启用",
    advice: "请检查检索配置、当前范围绑定和相关服务状态。",
  },
  empty_knowledge_base: {
    title: "知识库为空",
    advice: "当前范围内还没有可用于回答的知识内容，请先补充文档。",
  },
  empty_collection: {
    title: "集合为空",
    advice: "知识已上传但索引内容不可用，请检查索引任务和向量库状态。",
  },
  no_hits: {
    title: "没有命中相关片段",
    advice: "当前问题没有检索到足够相关的片段，请检查知识内容、查询改写和召回阈值。",
  },
  threshold_filtered: {
    title: "命中结果被阈值过滤",
    advice: "系统召回了候选片段，但相关性不够高，建议检查阈值配置或补充更贴近问题的文档。",
  },
  context_truncated: {
    title: "上下文预算截断",
    advice: "候选内容过多或单条过长，最终只有部分片段进入上下文。",
  },
};

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit("update:modelValue", value),
});

const diagnosisExpanded = ref(false);
const expandedSource = ref<SourceKind | null>(null);
const showAllSourceDocs = ref<Record<string, boolean>>({});
const expandedFinalDocs = ref<Record<string, boolean>>({});

function asString(value: unknown) {
  return typeof value === "string" ? value : "";
}

function formatDateTime(value: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatLatency(value: number | null) {
  if (value === null) return "-";
  if (value >= 1000) return `${(value / 1000).toFixed(1)}s`;
  return `${value}ms`;
}

function detailLabel(value: string) {
  if (value === "ok") return "已命中";
  if (value === "no_hits") return "无命中";
  if (value === "empty_knowledge_base") return "知识库为空";
  if (value === "empty_collection") return "集合为空";
  return value;
}

function sourceLabel(doc: QaLogDiagnosticDoc) {
  return doc.source_label || "Context";
}

function sourceTagType(doc: QaLogDiagnosticDoc) {
  const source = asString(doc.source_type);
  if (source === "vector") return "primary";
  if (source === "lexical") return "warning";
  if (source === "graph") return "success";
  if (source === "hybrid") return "info";
  return "info";
}

const tracePayload = computed<QaLogTracePayload | null>(() => props.detail?.tracePayload ?? null);
const knowledgePlan = computed(() => tracePayload.value?.knowledge_plan ?? null);
const retrievalSubtasks = computed(() => knowledgePlan.value?.subtasks || []);
const subtaskResults = computed(() => tracePayload.value?.subtask_results || []);
const subtaskResultById = computed(() => {
  return new Map(
    subtaskResults.value
      .filter((item) => item.id)
      .map((item): [string, SubtaskTraceResult] => [item.id as string, item]),
  );
});
const queryClues = computed(() => tracePayload.value?.query_clues ?? null);
const sourceSummary = computed(() => tracePayload.value?.source_summary ?? null);
const funnel = computed(() => tracePayload.value?.funnel ?? null);
const branchSummaries = computed(() => tracePayload.value?.branch_summaries ?? null);
const semanticQueries = computed(() => queryClues.value?.semantic_queries || []);
const lexicalTerms = computed(() => queryClues.value?.lexical_terms || []);
const candidateEntities = computed(() => queryClues.value?.candidate_entities || []);

const semanticQueryStats = computed<QueryStat[]>(() => {
  return branchSummaries.value?.vector || [];
});

const lexicalQueryStats = computed<QueryStat[]>(() => {
  return branchSummaries.value?.lexical || [];
});

const rankedDocs = computed(() => tracePayload.value?.ranked_candidates || []);
const finalContextDocs = computed(() => tracePayload.value?.final_context_docs || []);
const supportingEvidenceDocs = computed(() => tracePayload.value?.supporting_evidence_docs || []);
const metadataEvidenceDocs = computed(() => tracePayload.value?.metadata_evidence_docs || []);

const sourceDocs = computed<Record<SourceKind, QaLogDiagnosticDoc[]>>(() => {
  const grouped: Record<SourceKind, QaLogDiagnosticDoc[]> = {
    vector: [],
    lexical: [],
    graph: [],
  };
  const allDocs = [
    ...rankedDocs.value,
    ...supportingEvidenceDocs.value,
    ...metadataEvidenceDocs.value,
  ];
  const seen = new Set<string>();
  for (const doc of allDocs) {
    const source = asString(doc.source_type);
    const key = doc.identity || `${doc.rank}-${doc.title || ""}-${doc.content}`;
    if (seen.has(key)) continue;
    seen.add(key);
    if (source === "vector") grouped.vector.push(doc);
    else if (source === "lexical") grouped.lexical.push(doc);
    else if (source === "graph" || source === "hybrid") grouped.graph.push(doc);
  }
  return grouped;
});

const overview = computed(() => {
  const detail = props.detail;
  return {
    status: detail?.retrievalStatus || "未记录",
    totalRecall: funnel.value?.recall_total || 0,
    mergedCandidates: funnel.value?.merged_count || 0,
    duplicatesFolded: funnel.value?.duplicates_folded || 0,
    rerankedCandidates: funnel.value?.rerank_count || 0,
    finalCitations: funnel.value?.final_context_count || 0,
    latencyMs: detail?.latencyMs ?? null,
  };
});

const emptyReason = computed(() => {
  const detail = props.detail;
  if (!detail) return null;
  return detail.emptyReason || detail.retrievalStatus || null;
});

const emptyReasonState = computed(() => {
  if (!emptyReason.value || emptyReason.value === "ok") return null;
  return emptyReasonMeta[emptyReason.value] || {
    title: detailLabel(emptyReason.value),
    advice: props.detail?.retrievalStatusReason || "请结合查询改写和索引状态继续排查。",
  };
});

const sourceSummaryCards = computed(() => {
  return [
    {
      key: "vector" as const,
      title: "向量召回",
      status: sourceSummary.value?.vector?.status || "skipped",
      recallCount: sourceSummary.value?.vector?.recall_count || 0,
      candidateCount: sourceSummary.value?.vector?.candidate_count || 0,
      subtitle: `${sourceSummary.value?.vector?.query_count || 0} 条语义查询`,
    },
    {
      key: "lexical" as const,
      title: "关键词召回",
      status: sourceSummary.value?.lexical?.status || "skipped",
      recallCount: sourceSummary.value?.lexical?.recall_count || 0,
      candidateCount: sourceSummary.value?.lexical?.candidate_count || 0,
      subtitle: `${sourceSummary.value?.lexical?.query_count || 0} 个关键词`,
    },
    {
      key: "graph" as const,
      title: "图谱召回",
      status: sourceSummary.value?.graph?.status || "skipped",
      recallCount: sourceSummary.value?.graph?.recall_count || 0,
      candidateCount: sourceSummary.value?.graph?.candidate_count || 0,
      subtitle: `${sourceSummary.value?.graph?.query_count || 0} 个图谱线索`,
    },
  ];
});

function branchStatsForSource(kind: SourceKind) {
  if (kind === "vector") return semanticQueryStats.value;
  if (kind === "lexical") return lexicalQueryStats.value;
  return branchSummaries.value?.graph || [];
}

function docsForSource(kind: SourceKind) {
  return sourceDocs.value[kind] || [];
}

function toggleSource(kind: SourceKind) {
  expandedSource.value = expandedSource.value === kind ? null : kind;
}

function shouldShowAll(kind: SourceKind) {
  return Boolean(showAllSourceDocs.value[kind]);
}

function expandAllSourceDocs(kind: SourceKind) {
  showAllSourceDocs.value = {
    ...showAllSourceDocs.value,
    [kind]: true,
  };
}

function finalDocKey(doc: QaLogDiagnosticDoc, index: number) {
  return doc.identity || `${index}-${doc.rank}-${doc.title || ""}-${doc.content}`;
}

function isFinalDocExpanded(doc: QaLogDiagnosticDoc, index: number) {
  return Boolean(expandedFinalDocs.value[finalDocKey(doc, index)]);
}

function toggleFinalDoc(doc: QaLogDiagnosticDoc, index: number) {
  const key = finalDocKey(doc, index);
  expandedFinalDocs.value = {
    ...expandedFinalDocs.value,
    [key]: !expandedFinalDocs.value[key],
  };
}

watch(
  () => props.detail?.id,
  () => {
    expandedFinalDocs.value = {};
  },
);
</script>

<template>
  <el-drawer
    v-model="visible"
    size="980px"
    class="qa-log-trace-drawer"
  >
    <template #header>
      <div class="qa-log-trace-drawer__drawer-header">
        <div class="qa-log-trace-drawer__header-icon">
          <el-icon><Connection /></el-icon>
        </div>
        <div class="qa-log-trace-drawer__header-main">
          <h2>统一-检索 Trace</h2>
          <div class="qa-log-trace-drawer__header-meta">
            <span>会话: {{ detail?.sessionId || "-" }}</span>
            <span>用户: {{ detail?.externalUserName || detail?.externalUserId || detail?.userId || "-" }}</span>
            <span>{{ formatDateTime(detail?.createdAt || null) }}</span>
          </div>
        </div>
      </div>
    </template>

    <div class="qa-log-trace-drawer__body">
      <el-skeleton
        v-if="loading"
        animated
        :rows="14"
      />

      <el-empty
        v-else-if="!detail"
        description="未找到问答日志详情"
      />

      <template v-else>
        <section class="qa-log-trace-drawer__overview">
          <article class="qa-log-trace-drawer__metric qa-log-trace-drawer__metric--status">
            <span class="qa-log-trace-drawer__metric-label">检索状态</span>
            <strong>
              <el-icon><Connection /></el-icon>
              {{ detailLabel(overview.status) }}
            </strong>
          </article>
          <article class="qa-log-trace-drawer__metric qa-log-trace-drawer__metric--recall">
            <span class="qa-log-trace-drawer__metric-label">总召回数</span>
            <strong>{{ overview.totalRecall }}</strong>
          </article>
          <article class="qa-log-trace-drawer__metric qa-log-trace-drawer__metric--merged">
            <span class="qa-log-trace-drawer__metric-label">合并后候选数</span>
            <strong>{{ overview.mergedCandidates }}</strong>
          </article>
          <article class="qa-log-trace-drawer__metric qa-log-trace-drawer__metric--rerank">
            <span class="qa-log-trace-drawer__metric-label">重排后候选数</span>
            <strong>{{ overview.rerankedCandidates }}</strong>
          </article>
          <article class="qa-log-trace-drawer__metric qa-log-trace-drawer__metric--final">
            <span class="qa-log-trace-drawer__metric-label">最终引用数</span>
            <strong>{{ overview.finalCitations }}</strong>
          </article>
          <article class="qa-log-trace-drawer__metric qa-log-trace-drawer__metric--latency">
            <span class="qa-log-trace-drawer__metric-label">耗时</span>
            <strong>
              <el-icon><Clock /></el-icon>
              {{ formatLatency(overview.latencyMs) }}
            </strong>
          </article>
        </section>

        <section
          v-if="emptyReasonState"
          class="qa-log-trace-drawer__alert"
        >
          <el-icon><Connection /></el-icon>
          <div>
            <h3>{{ emptyReasonState.title }}</h3>
            <p>{{ detail.retrievalStatusReason || emptyReasonState.advice }}</p>
          </div>
        </section>

        <section class="qa-log-trace-drawer__section">
          <header class="qa-log-trace-drawer__section-header">
            <div class="qa-log-trace-drawer__section-title">
              <span class="qa-log-trace-drawer__section-icon">
                <el-icon><Search /></el-icon>
              </span>
              <div>
                <h3>1. 检索线索生成</h3>
                <p>统一理解问题后生成的并行检索线索</p>
              </div>
            </div>
            <span class="qa-log-trace-drawer__section-pill">Query & Clues</span>
          </header>

          <div class="qa-log-trace-drawer__query-hero">
            <p class="qa-log-trace-drawer__query-hero-label">
              User Query
            </p>
            <div class="qa-log-trace-drawer__query-hero-content">
              {{ detail.query }}
            </div>
          </div>

          <div
            v-if="knowledgePlan?.standalone_query"
            class="qa-log-trace-drawer__query-hero"
          >
            <p class="qa-log-trace-drawer__query-hero-label">
              Standalone Query
            </p>
            <div class="qa-log-trace-drawer__query-hero-content">
              {{ knowledgePlan.standalone_query }}
            </div>
          </div>

          <div class="qa-log-trace-drawer__query-arrow">
            <span />
          </div>

          <div class="qa-log-trace-drawer__rewrite-stack">
            <article
              v-if="retrievalSubtasks.length > 0"
              class="qa-log-trace-drawer__panel qa-log-trace-drawer__panel--vector"
            >
              <h4>
                <el-icon><ChatDotRound /></el-icon>
                检索子任务（{{ knowledgePlan?.attempt_count || 1 }} 轮）
              </h4>
              <ul class="qa-log-trace-drawer__query-list">
                <li
                  v-for="(task, index) in retrievalSubtasks"
                  :key="task.id || `${task.goal}-${index}`"
                >
                  <span>{{ index + 1 }}</span>
                  <p>
                    {{ task.goal }}
                    <small v-if="task.evidence_requirement">
                      证据要求：{{ task.evidence_requirement }}
                    </small>
                    <small>
                      覆盖状态：{{
                        subtaskResultById.get(task.id || "")?.coverage_status || "未审计"
                      }}
                    </small>
                    <small
                      v-if="subtaskResultById.get(task.id || '')?.coverage_reason"
                    >
                      审计说明：{{
                        subtaskResultById.get(task.id || "")?.coverage_reason
                      }}
                    </small>
                    <small
                      v-for="claim in subtaskResultById.get(task.id || '')?.supported_claims || []"
                      :key="claim"
                    >
                      已支持：{{ claim }}
                    </small>
                  </p>
                </li>
              </ul>
            </article>

            <article class="qa-log-trace-drawer__panel qa-log-trace-drawer__panel--vector">
              <h4>
                <el-icon><Search /></el-icon>
                语义查询 (Vector)
              </h4>
              <ul
                v-if="semanticQueries.length > 0"
                class="qa-log-trace-drawer__query-list"
              >
                <li
                  v-for="(query, index) in semanticQueries"
                  :key="`${query}-${index}`"
                >
                  <span>{{ index + 1 }}</span>
                  <p>{{ query }}</p>
                </li>
              </ul>
              <p
                v-else
                class="qa-log-trace-drawer__empty-copy"
              >
                当前日志未保存语义查询。
              </p>
            </article>

            <article class="qa-log-trace-drawer__panel qa-log-trace-drawer__panel--lexical">
              <h4>
                <el-icon><Document /></el-icon>
                关键词 (Lexical)
              </h4>
              <div
                v-if="lexicalTerms.length > 0"
                class="qa-log-trace-drawer__term-list"
              >
                <span
                  v-for="term in lexicalTerms"
                  :key="term"
                >
                  {{ term }}
                </span>
              </div>
              <p
                v-else
                class="qa-log-trace-drawer__empty-copy"
              >
                当前日志未保存关键词。
              </p>
            </article>

            <article class="qa-log-trace-drawer__panel qa-log-trace-drawer__panel--graph">
              <h4>
                <el-icon><Connection /></el-icon>
                图谱线索 (Graph)
              </h4>
              <div
                v-if="candidateEntities.length > 0"
                class="qa-log-trace-drawer__term-list"
              >
                <span
                  v-for="entity in candidateEntities"
                  :key="entity"
                >
                  {{ entity }}
                </span>
              </div>
              <p
                v-else
                class="qa-log-trace-drawer__empty-copy"
              >
                当前日志未保存图谱线索。
              </p>
            </article>
          </div>
        </section>

        <section class="qa-log-trace-drawer__section">
          <header class="qa-log-trace-drawer__section-header">
            <div class="qa-log-trace-drawer__section-title">
              <span class="qa-log-trace-drawer__section-icon">
                <el-icon><ChatDotRound /></el-icon>
              </span>
              <div>
                <h3>2. 统一候选排序</h3>
                <p>汇集多路线索，经过重排打分后的最终名次（精简排位视图）。</p>
              </div>
            </div>
            <span class="qa-log-trace-drawer__section-pill">Unified Ranking</span>
          </header>

          <div
            v-if="rankedDocs.length > 0"
            class="qa-log-trace-drawer__ranking-list"
          >
            <article
              v-for="doc in rankedDocs"
              :key="doc.identity || `${doc.rank}-${doc.title || doc.content}`"
              class="qa-log-trace-drawer__ranking-row"
              :class="{ 'qa-log-trace-drawer__ranking-row--muted': !doc.selected }"
            >
              <div class="qa-log-trace-drawer__ranking-main">
                <span class="qa-log-trace-drawer__ranking-rank">{{ doc.rank }}</span>
                <strong>{{ doc.title || `候选片段 #${doc.rank}` }}</strong>
                <span
                  class="qa-log-trace-drawer__ranking-source"
                  :class="`qa-log-trace-drawer__ranking-source--${doc.source_type || 'vector'}`"
                >
                  {{ doc.source_label || sourceLabel(doc) }}
                </span>
              </div>
              <div class="qa-log-trace-drawer__ranking-meta">
                <span class="qa-log-trace-drawer__ranking-chip">
                  原#{{ doc.original_rank || doc.rank }} → 现#{{ doc.rank }}
                </span>
                <span class="qa-log-trace-drawer__ranking-chip">
                  分: {{ doc.score === null || doc.score === undefined ? "-" : doc.score.toFixed(3) }}
                </span>
                <el-icon
                  class="qa-log-trace-drawer__ranking-state"
                  :class="{ 'qa-log-trace-drawer__ranking-state--selected': doc.selected }"
                >
                  <CircleCheck v-if="doc.selected" />
                  <CircleClose v-else />
                </el-icon>
              </div>
            </article>
          </div>
          <p
            v-else
            class="qa-log-trace-drawer__empty-copy"
          >
            当前日志没有保留统一候选排序结果。
          </p>
        </section>

        <section class="qa-log-trace-drawer__section">
          <header class="qa-log-trace-drawer__section-header">
            <div class="qa-log-trace-drawer__section-title">
              <span class="qa-log-trace-drawer__section-icon qa-log-trace-drawer__section-icon--final">
                <el-icon><Document /></el-icon>
              </span>
              <div>
                <h3>3. 最终回答上下文</h3>
                <p>这些片段真正提供给大模型参与最终回答生成，是本次输出最直接的依据。</p>
              </div>
            </div>
            <span class="qa-log-trace-drawer__section-pill qa-log-trace-drawer__section-pill--final">
              Final Context
            </span>
          </header>

          <div
            v-if="finalContextDocs.length > 0"
            class="qa-log-trace-drawer__final-list"
          >
            <article
              v-for="(doc, index) in finalContextDocs"
              :key="`final-${doc.identity || `${doc.rank}-${doc.title || doc.content}`}`"
              class="qa-log-trace-drawer__final-card"
            >
              <button
                class="qa-log-trace-drawer__final-card-top"
                type="button"
                @click="toggleFinalDoc(doc, index)"
              >
                <div class="qa-log-trace-drawer__final-card-title">
                  <span class="qa-log-trace-drawer__final-card-rank">{{ index + 1 }}</span>
                  <div>
                    <h4>{{ doc.title || `证据片段 #${index + 1}` }}</h4>
                    <p>{{ doc.section_path || "未记录路径" }}</p>
                  </div>
                </div>
                <span class="qa-log-trace-drawer__final-card-toggle">
                  {{ isFinalDocExpanded(doc, index) ? "收起" : "展开" }}
                  <el-icon>
                    <ArrowUp v-if="isFinalDocExpanded(doc, index)" />
                    <ArrowDown v-else />
                  </el-icon>
                </span>
              </button>
              <div
                v-if="isFinalDocExpanded(doc, index)"
                class="qa-log-trace-drawer__final-card-body"
              >
                {{ doc.content }}
              </div>
            </article>
          </div>
          <p
            v-else
            class="qa-log-trace-drawer__empty-copy"
          >
            当前日志没有保留最终上下文片段。
          </p>
        </section>

        <section class="qa-log-trace-drawer__section">
          <header class="qa-log-trace-drawer__section-header">
            <div class="qa-log-trace-drawer__section-title">
              <span class="qa-log-trace-drawer__section-icon qa-log-trace-drawer__section-icon--answer">
                <el-icon><ChatDotRound /></el-icon>
              </span>
              <div>
                <h3>4. 最终模型回答</h3>
                <p>这里展示本次问答最终返回给用户的模型回答正文。</p>
              </div>
            </div>
            <span class="qa-log-trace-drawer__section-pill qa-log-trace-drawer__section-pill--answer">
              LLM Response
            </span>
          </header>

          <div class="qa-log-trace-drawer__answer-card">
            <div class="qa-log-trace-drawer__answer-body">
              {{ detail.answerText || "当前日志未记录模型最终回答。" }}
            </div>
          </div>
        </section>

        <section class="qa-log-trace-drawer__section">
          <button
            class="qa-log-trace-drawer__diagnosis-toggle"
            @click="diagnosisExpanded = !diagnosisExpanded"
          >
            <div class="qa-log-trace-drawer__section-title">
              <span class="qa-log-trace-drawer__section-icon qa-log-trace-drawer__section-icon--diagnosis">
                <el-icon><Connection /></el-icon>
              </span>
              <div>
                <h3>5. 召回诊断</h3>
                <p>查看统一候选池的底层来源与过滤情况，展开后可继续查看各来源分路统计和候选片段。</p>
              </div>
            </div>
            <div class="qa-log-trace-drawer__diagnosis-toggle-side">
              <span class="qa-log-trace-drawer__section-pill qa-log-trace-drawer__section-pill--diagnosis">
                Retrieval Diagnosis
              </span>
              <span class="qa-log-trace-drawer__diagnosis-toggle-indicator">
                {{ diagnosisExpanded ? "收起" : "展开" }}
                <el-icon>
                  <ArrowUp v-if="diagnosisExpanded" />
                  <ArrowDown v-else />
                </el-icon>
              </span>
            </div>
          </button>

          <div
            v-if="diagnosisExpanded"
            class="qa-log-trace-drawer__diagnosis-body"
          >
            <div class="qa-log-trace-drawer__merge-summary">
              <article class="qa-log-trace-drawer__merge-card">
                <span>合并前总数</span>
                <strong>{{ overview.totalRecall }}</strong>
              </article>
              <article class="qa-log-trace-drawer__merge-card">
                <span>重复折叠数</span>
                <strong>{{ overview.duplicatesFolded }}</strong>
              </article>
              <article class="qa-log-trace-drawer__merge-card">
                <span>统一候选池</span>
                <strong>{{ overview.mergedCandidates }}</strong>
              </article>
            </div>

            <article
              v-for="card in sourceSummaryCards"
              :key="card.key"
              class="qa-log-trace-drawer__source-card"
            >
              <button
                class="qa-log-trace-drawer__source-header"
                @click="toggleSource(card.key)"
              >
                <div>
                  <div class="qa-log-trace-drawer__source-top">
                    <h4>{{ card.title }}</h4>
                    <span>{{ card.status }}</span>
                  </div>
                  <p>{{ card.subtitle }}</p>
                </div>
                <div class="qa-log-trace-drawer__source-stats">
                  <span>召回 {{ card.recallCount }}</span>
                  <span>候选 {{ card.candidateCount }}</span>
                </div>
              </button>

              <div
                v-if="expandedSource === card.key"
                class="qa-log-trace-drawer__source-body"
              >
                <div class="qa-log-trace-drawer__branch-list">
                  <article
                    v-for="(branch, index) in branchStatsForSource(card.key)"
                    :key="`${card.key}-${branch.query}-${index}`"
                    class="qa-log-trace-drawer__branch-item"
                  >
                    <div class="qa-log-trace-drawer__branch-header">
                      <span>{{ card.key === 'graph' ? '线索' : '分路' }} {{ index + 1 }}</span>
                      <strong>{{ branch.chunk_count }}</strong>
                    </div>
                    <p>{{ branch.query }}</p>
                  </article>
                </div>

                <div class="qa-log-trace-drawer__branch-docs">
                  <header>
                    <h5>来源候选片段</h5>
                    <p>当前日志只保留来源级候选片段，不保留每个 branch 的原始全量明细。</p>
                  </header>
                  <div
                    v-if="docsForSource(card.key).length > 0"
                    class="qa-log-trace-drawer__doc-list"
                  >
                    <article
                      v-for="doc in shouldShowAll(card.key) ? docsForSource(card.key) : docsForSource(card.key).slice(0, 3)"
                      :key="`${card.key}-${doc.identity || `${doc.rank}-${doc.title || doc.content}`}`"
                      class="qa-log-trace-drawer__doc-card qa-log-trace-drawer__doc-card--diagnosis"
                    >
                      <div class="qa-log-trace-drawer__doc-header">
                        <div class="qa-log-trace-drawer__doc-title">
                          <span class="qa-log-trace-drawer__doc-rank">{{ doc.rank }}</span>
                          <div>
                            <h4>{{ doc.title || `来源片段 #${doc.rank}` }}</h4>
                            <p>{{ doc.section_path || "未记录章节路径" }}</p>
                          </div>
                        </div>
                        <el-tag
                          size="small"
                          effect="plain"
                          :type="sourceTagType(doc)"
                        >
                          {{ sourceLabel(doc) }}
                        </el-tag>
                      </div>
                      <p class="qa-log-trace-drawer__doc-content">
                        {{ doc.content }}
                      </p>
                    </article>
                    <button
                      v-if="docsForSource(card.key).length > 3 && !shouldShowAll(card.key)"
                      class="qa-log-trace-drawer__show-more"
                      @click="expandAllSourceDocs(card.key)"
                    >
                      展开剩余 {{ docsForSource(card.key).length - 3 }} 条候选片段
                    </button>
                  </div>
                  <p
                    v-else
                    class="qa-log-trace-drawer__empty-copy"
                  >
                    当前日志没有保留这一来源的候选片段。
                  </p>
                </div>
              </div>
            </article>
          </div>
        </section>
      </template>
    </div>
  </el-drawer>
</template>

<style scoped>
.qa-log-trace-drawer__body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 100%;
  padding-top: 4px;
  background: #f8fafc;
}

.qa-log-trace-drawer__drawer-header {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 2px 0;
}

.qa-log-trace-drawer__header-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #4f46e5;
  color: #fff;
  font-size: 16px;
}

.qa-log-trace-drawer__header-main {
  min-width: 0;
}

.qa-log-trace-drawer__header-main h2 {
  margin: 0;
  color: var(--admin-text, #0f172a);
  font-size: 18px;
  font-weight: 800;
  line-height: 1.3;
}

.qa-log-trace-drawer__header-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.qa-log-trace-drawer__header-meta span + span::before {
  content: "•";
  margin-right: 8px;
  color: #cbd5e1;
}

.qa-log-trace-drawer__hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 24px;
  border: 1px solid var(--admin-border, #e5e7eb);
  border-radius: 16px;
  background:
    radial-gradient(circle at top right, rgba(99, 102, 241, 0.12), transparent 35%),
    linear-gradient(135deg, rgba(15, 23, 42, 0.03), rgba(13, 148, 136, 0.05)),
    #fff;
}

.qa-log-trace-drawer__hero-main {
  min-width: 0;
}

.qa-log-trace-drawer__hero-kicker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
  color: var(--admin-text-subtle, #64748b);
  font-size: 12px;
  font-weight: 600;
}

.qa-log-trace-drawer__hero-title {
  margin: 0;
  color: var(--admin-text, #0f172a);
  font-size: 22px;
  line-height: 1.45;
}

.qa-log-trace-drawer__hero-answer {
  margin: 14px 0 0;
  color: var(--admin-text-muted, #475569);
  line-height: 1.7;
}

.qa-log-trace-drawer__hero-side {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
}

.qa-log-trace-drawer__hero-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--admin-text-subtle, #64748b);
  font-size: 12px;
  text-align: right;
}

.qa-log-trace-drawer__overview {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0;
  overflow: hidden;
  border: 1px solid #dbe3ef;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.qa-log-trace-drawer__metric {
  padding: 18px 24px;
  border: 0;
  border-right: 1px solid #e5e7eb;
  border-radius: 0;
  background: #fff;
}

.qa-log-trace-drawer__metric:last-child {
  border-right: 0;
}

.qa-log-trace-drawer__metric-label {
  display: block;
  margin-bottom: 10px;
  color: var(--admin-text-subtle, #64748b);
  font-size: 12px;
  font-weight: 600;
}

.qa-log-trace-drawer__metric strong {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--admin-text, #0f172a);
  font-size: 18px;
}

.qa-log-trace-drawer__metric strong .el-icon {
  font-size: 14px;
}

.qa-log-trace-drawer__metric--status strong,
.qa-log-trace-drawer__metric--status .el-icon {
  color: #059669;
}

.qa-log-trace-drawer__metric--recall strong,
.qa-log-trace-drawer__metric--recall .el-icon,
.qa-log-trace-drawer__metric--merged strong,
.qa-log-trace-drawer__metric--merged .el-icon {
  color: #2563eb;
}

.qa-log-trace-drawer__metric--rerank strong,
.qa-log-trace-drawer__metric--rerank .el-icon {
  color: #4f46e5;
}

.qa-log-trace-drawer__metric--final strong,
.qa-log-trace-drawer__metric--final .el-icon {
  color: #059669;
}

.qa-log-trace-drawer__metric--latency .el-icon {
  color: #64748b;
}

.qa-log-trace-drawer__alert {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 12px;
  padding: 16px;
  border: 1px solid #fecaca;
  border-radius: 14px;
  background: #fff1f2;
  color: #9f1239;
}

.qa-log-trace-drawer__alert h3 {
  margin: 0 0 6px;
  font-size: 14px;
}

.qa-log-trace-drawer__alert p {
  margin: 0;
  line-height: 1.6;
}

.qa-log-trace-drawer__section {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
  border: 1px solid #dbe3ef;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}

.qa-log-trace-drawer__section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.qa-log-trace-drawer__section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.qa-log-trace-drawer__section-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: #eef2ff;
  color: #4f46e5;
  font-size: 17px;
}

.qa-log-trace-drawer__section-icon--final {
  background: linear-gradient(180deg, #eef2ff 0%, #e0f2fe 100%);
  color: #4f46e5;
}

.qa-log-trace-drawer__section-icon--answer {
  background: linear-gradient(180deg, #eef2ff 0%, #ede9fe 100%);
  color: #6366f1;
}

.qa-log-trace-drawer__section-icon--diagnosis {
  background: linear-gradient(180deg, #eef2ff 0%, #dbeafe 100%);
  color: #2563eb;
}

.qa-log-trace-drawer__section-index {
  margin: 0 0 8px;
  color: #4f46e5;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.4;
}

.qa-log-trace-drawer__section-header h3 {
  margin: 0;
  color: var(--admin-text, #0f172a);
  font-size: 22px;
  font-weight: 800;
  line-height: 1.35;
}

.qa-log-trace-drawer__section-pill {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: 9px;
  background: #eef2f7;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.qa-log-trace-drawer__section-pill--final {
  background: #f3f4f6;
  color: #64748b;
}

.qa-log-trace-drawer__section-pill--answer {
  background: #eef2ff;
  color: #6366f1;
}

.qa-log-trace-drawer__section-pill--diagnosis {
  background: #eff6ff;
  color: #2563eb;
}

.qa-log-trace-drawer__section-header p,
.qa-log-trace-drawer__section-copy {
  margin: 8px 0 0;
  color: var(--admin-text-subtle, #64748b);
  font-size: 15px;
  line-height: 1.75;
}

.qa-log-trace-drawer__query-hero {
  padding: 18px;
  border-radius: 14px;
  background: #0f172a;
  color: #fff;
}

.qa-log-trace-drawer__query-hero-label {
  margin: 0 0 8px;
  color: rgba(255, 255, 255, 0.65);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.qa-log-trace-drawer__query-hero-content {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.6;
}

.qa-log-trace-drawer__query-arrow {
  display: flex;
  justify-content: center;
  margin-top: -6px;
}

.qa-log-trace-drawer__query-arrow span {
  width: 18px;
  height: 18px;
  border-right: 2px solid #cbd5e1;
  border-bottom: 2px solid #cbd5e1;
  transform: rotate(45deg);
  background: #fff;
}

.qa-log-trace-drawer__rewrite-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.qa-log-trace-drawer__panel {
  align-self: stretch;
  width: 100%;
  padding: 16px;
  border: 1px solid var(--admin-border, #e5e7eb);
  border-radius: 14px;
  background: #fff;
}

.qa-log-trace-drawer__panel--vector {
  background: rgba(239, 246, 255, 0.7);
}

.qa-log-trace-drawer__panel--lexical {
  background: rgba(255, 251, 235, 0.7);
}

.qa-log-trace-drawer__panel--graph {
  background: rgba(236, 253, 245, 0.7);
}

.qa-log-trace-drawer__panel h4 {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 12px;
  color: var(--admin-text, #0f172a);
  font-size: 14px;
}

.qa-log-trace-drawer__panel h4 .el-icon {
  font-size: 15px;
}

.qa-log-trace-drawer__clue-divider {
  height: 1px;
  background: rgba(148, 163, 184, 0.28);
}

.qa-log-trace-drawer__query-list,
.qa-log-trace-drawer__support-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.qa-log-trace-drawer__query-list li,
.qa-log-trace-drawer__support-list li {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
}

.qa-log-trace-drawer__query-list span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 12px;
  font-weight: 700;
}

.qa-log-trace-drawer__query-list p,
.qa-log-trace-drawer__support-list p {
  margin: 0;
  color: var(--admin-text-muted, #475569);
  line-height: 1.6;
}

.qa-log-trace-drawer__term-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.qa-log-trace-drawer__term-list span {
  padding: 6px 10px;
  border: 1px solid #d6d3d1;
  border-radius: 999px;
  background: #fff;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}

.qa-log-trace-drawer__doc-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.qa-log-trace-drawer__ranking-list {
  overflow: hidden;
  border: 1px solid #dbe3ef;
  border-radius: 12px;
  background: #fff;
}

.qa-log-trace-drawer__ranking-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 54px;
  padding: 10px 16px;
  border-bottom: 1px solid #edf2f7;
}

.qa-log-trace-drawer__ranking-row:last-child {
  border-bottom: 0;
}

.qa-log-trace-drawer__ranking-row--muted {
  background: #f8fafc;
  color: #94a3b8;
}

.qa-log-trace-drawer__ranking-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.qa-log-trace-drawer__ranking-rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 25px;
  height: 25px;
  border-radius: 7px;
  background: #e0e7ff;
  color: #4f46e5;
  font-size: 13px;
  font-weight: 800;
}

.qa-log-trace-drawer__ranking-row--muted .qa-log-trace-drawer__ranking-rank {
  background: #e5e7eb;
  color: #94a3b8;
}

.qa-log-trace-drawer__ranking-main strong {
  overflow: hidden;
  color: var(--admin-text, #0f172a);
  font-size: 14px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qa-log-trace-drawer__ranking-row--muted .qa-log-trace-drawer__ranking-main strong {
  color: #94a3b8;
}

.qa-log-trace-drawer__ranking-source {
  flex-shrink: 0;
  padding: 4px 8px;
  border: 1px solid #c7d2fe;
  border-radius: 5px;
  background: #f5f3ff;
  color: #6d28d9;
  font-size: 12px;
  font-weight: 800;
}

.qa-log-trace-drawer__ranking-source--lexical {
  border-color: #fcd34d;
  background: #fffbeb;
  color: #b45309;
}

.qa-log-trace-drawer__ranking-source--graph {
  border-color: #a7f3d0;
  background: #ecfdf5;
  color: #047857;
}

.qa-log-trace-drawer__ranking-source--vector {
  border-color: #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
}

.qa-log-trace-drawer__ranking-meta {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 10px;
}

.qa-log-trace-drawer__ranking-chip {
  padding: 6px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.qa-log-trace-drawer__ranking-state {
  color: #cbd5e1;
  font-size: 16px;
}

.qa-log-trace-drawer__ranking-state--selected {
  color: #10b981;
}

.qa-log-trace-drawer__doc-card {
  padding: 16px;
  border: 1px solid var(--admin-border, #e5e7eb);
  border-radius: 14px;
  background: #fff;
}

.qa-log-trace-drawer__doc-card--final {
  border-left: 4px solid #0f766e;
}

.qa-log-trace-drawer__final-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
}

.qa-log-trace-drawer__final-title {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}

.qa-log-trace-drawer__final-title > div {
  min-width: 0;
}

.qa-log-trace-drawer__final-title .qa-log-trace-drawer__section-index {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.4;
}

.qa-log-trace-drawer__final-title h3 {
  margin: 0;
  color: var(--admin-text, #0f172a);
  font-size: 22px;
  font-weight: 800;
  line-height: 1.35;
}

.qa-log-trace-drawer__final-header .qa-log-trace-drawer__section-copy,
.qa-log-trace-drawer__final-header p:not(.qa-log-trace-drawer__section-index) {
  font-size: 15px;
  line-height: 1.75;
}

.qa-log-trace-drawer__final-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(180deg, #eef2ff 0%, #e0f2fe 100%);
  color: #4f46e5;
  font-size: 18px;
}

.qa-log-trace-drawer__final-icon--answer {
  background: linear-gradient(180deg, #eef2ff 0%, #ede9fe 100%);
  color: #6366f1;
}

.qa-log-trace-drawer__final-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.qa-log-trace-drawer__final-card {
  padding: 18px;
  border: 1px solid #dbe3ef;
  border-radius: 16px;
  background:
    linear-gradient(180deg, #f8fbff 0%, #f5f7fb 100%);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}

.qa-log-trace-drawer__final-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  margin-bottom: 14px;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.qa-log-trace-drawer__final-card-title {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.qa-log-trace-drawer__final-card-rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: #1e293b;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  flex-shrink: 0;
}

.qa-log-trace-drawer__final-card-title h4 {
  margin: 0;
  color: var(--admin-text, #0f172a);
  font-size: 16px;
  font-weight: 800;
}

.qa-log-trace-drawer__final-card-title p {
  margin: 6px 0 0;
  color: var(--admin-text-subtle, #94a3b8);
  font-size: 12px;
  line-height: 1.5;
}

.qa-log-trace-drawer__final-card-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.qa-log-trace-drawer__final-card-toggle .el-icon {
  font-size: 14px;
}

.qa-log-trace-drawer__final-card-body {
  padding: 18px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
  color: var(--admin-text-muted, #334155);
  line-height: 1.85;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
  white-space: pre-wrap;
}

.qa-log-trace-drawer__answer-card {
  padding: 18px;
  border: 1px solid #c7d2fe;
  border-radius: 16px;
  background: linear-gradient(180deg, #f8faff 0%, #f5f3ff 100%);
  box-shadow: 0 10px 24px rgba(99, 102, 241, 0.06);
}

.qa-log-trace-drawer__answer-body {
  padding: 20px 18px;
  border: 1px solid #dbe3ef;
  border-radius: 14px;
  background: #fff;
  color: var(--admin-text-muted, #334155);
  line-height: 1.95;
  white-space: pre-wrap;
}

.qa-log-trace-drawer__doc-card--diagnosis {
  background: #fff;
}

.qa-log-trace-drawer__doc-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.qa-log-trace-drawer__doc-title {
  display: flex;
  gap: 10px;
}

.qa-log-trace-drawer__doc-rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  background: #0f172a;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.qa-log-trace-drawer__doc-title h4 {
  margin: 0;
  color: var(--admin-text, #0f172a);
  font-size: 14px;
}

.qa-log-trace-drawer__doc-title p {
  margin: 4px 0 0;
  color: var(--admin-text-subtle, #64748b);
  font-size: 12px;
}

.qa-log-trace-drawer__doc-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.qa-log-trace-drawer__doc-content {
  margin: 0;
  color: var(--admin-text-muted, #475569);
  line-height: 1.7;
}

.qa-log-trace-drawer__doc-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
  color: var(--admin-text-subtle, #64748b);
  font-size: 12px;
}

.qa-log-trace-drawer__diagnosis-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  padding: 0;
  border: 0;
  border-radius: 14px;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.qa-log-trace-drawer__diagnosis-toggle-side {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.qa-log-trace-drawer__diagnosis-toggle-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.qa-log-trace-drawer__diagnosis-toggle-indicator .el-icon {
  font-size: 14px;
}

.qa-log-trace-drawer__diagnosis-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.qa-log-trace-drawer__merge-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.qa-log-trace-drawer__merge-card {
  padding: 18px;
  border: 1px solid #dbe3ef;
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04);
}

.qa-log-trace-drawer__merge-card span {
  display: block;
  margin-bottom: 10px;
  color: var(--admin-text-subtle, #64748b);
  font-size: 12px;
  font-weight: 600;
}

.qa-log-trace-drawer__merge-card strong {
  color: var(--admin-text, #0f172a);
  font-size: 24px;
}

.qa-log-trace-drawer__source-card {
  overflow: hidden;
  border: 1px solid #dbe3ef;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
}

.qa-log-trace-drawer__source-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  padding: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border: 0;
  text-align: left;
  cursor: pointer;
}

.qa-log-trace-drawer__source-top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.qa-log-trace-drawer__source-top h4 {
  margin: 0;
  color: var(--admin-text, #0f172a);
  font-size: 15px;
}

.qa-log-trace-drawer__source-top span {
  padding: 4px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
}

.qa-log-trace-drawer__source-header p {
  margin: 0;
  color: var(--admin-text-subtle, #64748b);
  font-size: 12px;
}

.qa-log-trace-drawer__source-stats {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
  text-align: right;
}

.qa-log-trace-drawer__source-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  border-top: 1px solid #e5e7eb;
  background: linear-gradient(180deg, #f8fbff 0%, #f8fafc 100%);
}

.qa-log-trace-drawer__branch-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.qa-log-trace-drawer__branch-item {
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
}

.qa-log-trace-drawer__branch-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.qa-log-trace-drawer__branch-header span {
  color: var(--admin-text-subtle, #64748b);
  font-size: 11px;
  font-weight: 700;
}

.qa-log-trace-drawer__branch-header strong {
  color: var(--admin-text, #0f172a);
  font-size: 18px;
}

.qa-log-trace-drawer__branch-item p,
.qa-log-trace-drawer__branch-docs header p,
.qa-log-trace-drawer__empty-copy {
  margin: 0;
  color: var(--admin-text-subtle, #64748b);
  line-height: 1.6;
}

.qa-log-trace-drawer__branch-docs {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.qa-log-trace-drawer__branch-docs header h5 {
  margin: 0 0 6px;
  color: var(--admin-text, #0f172a);
  font-size: 14px;
}

.qa-log-trace-drawer__show-more {
  width: 100%;
  padding: 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 12px;
  background: #fff;
  color: #4f46e5;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

@media (max-width: 960px) {
  .qa-log-trace-drawer__overview,
  .qa-log-trace-drawer__merge-summary,
  .qa-log-trace-drawer__branch-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .qa-log-trace-drawer__final-header,
  .qa-log-trace-drawer__final-title,
  .qa-log-trace-drawer__final-card-top {
    flex-direction: column;
  }

  .qa-log-trace-drawer__hero,
  .qa-log-trace-drawer__doc-header,
  .qa-log-trace-drawer__ranking-row,
  .qa-log-trace-drawer__source-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .qa-log-trace-drawer__hero-side,
  .qa-log-trace-drawer__ranking-meta,
  .qa-log-trace-drawer__source-stats {
    align-items: flex-start;
    text-align: left;
  }

  .qa-log-trace-drawer__ranking-main {
    width: 100%;
  }

  .qa-log-trace-drawer__ranking-main strong {
    white-space: normal;
  }

  .qa-log-trace-drawer__overview,
  .qa-log-trace-drawer__merge-summary,
  .qa-log-trace-drawer__branch-list {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
