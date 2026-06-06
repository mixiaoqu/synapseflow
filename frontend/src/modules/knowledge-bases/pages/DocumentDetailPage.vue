<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { Document, Folder, RefreshRight, Search } from "@element-plus/icons-vue";

import { getDocument, getDocumentChunks } from "@/shared/api/documents";
import AppEmpty from "@/shared/components/feedback/AppEmpty.vue";
import AppError from "@/shared/components/feedback/AppError.vue";
import AppLoading from "@/shared/components/feedback/AppLoading.vue";
import StatusTag from "@/shared/components/page/StatusTag.vue";
import { useAdminBreadcrumbStore } from "@/stores/admin-breadcrumb";
import type {
  DocumentChunkSummary,
  DocumentDetail,
  DocumentLifecycleStatus,
} from "@/shared/types/document";

const route = useRoute();
const adminBreadcrumbStore = useAdminBreadcrumbStore();

const documentDetail = ref<DocumentDetail | null>(null);
const documentChunks = ref<DocumentChunkSummary[]>([]);
const loading = ref(false);
const loadError = ref<unknown>(null);
const activeChunkId = ref<number | null>(null);
const searchKeyword = ref("");
const previewBodyRef = ref<HTMLElement | null>(null);

const knowledgeBaseId = computed(() => getRouteId(route.params.knowledgeBaseId));
const documentId = computed(() => getRouteId(route.params.documentId));

const indexStatusMeta = {
  queued: { label: "排队中", type: "warning" as const },
  processing: { label: "索引中", type: "primary" as const },
  indexed: { label: "已索引", type: "success" as const },
  failed: { label: "索引失败", type: "danger" as const },
};

const lifecycleStatusMeta: Record<DocumentLifecycleStatus, { label: string; type: "info" | "warning" | "success" | "danger" }> = {
  draft: { label: "草稿", type: "info" },
  pending_review: { label: "待审核", type: "warning" },
  published: { label: "已发布", type: "success" },
  archived: { label: "已归档", type: "info" },
};

const activeChunk = computed(() => documentChunks.value.find((item) => item.id === activeChunkId.value) ?? null);

const filteredChunks = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return documentChunks.value;
  }

  return documentChunks.value.filter((item) => {
    const haystack = [item.section_path, item.search_text, item.content, String(item.chunk_index + 1)]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(keyword);
  });
});

const chunkStats = computed(() => [
  { label: "分块总数", value: String(documentChunks.value.length) },
  { label: "当前分块", value: activeChunk.value ? `#${activeChunk.value.chunk_index + 1}` : "未选择" },
  { label: "文档版本", value: documentDetail.value ? `V${documentDetail.value.version}` : "-" },
  { label: "文档大小", value: documentDetail.value ? formatFileSize(documentDetail.value.size) : "-" },
]);

const documentContentHtml = computed(() => {
  const content = documentDetail.value?.content ?? "";
  if (!content) {
    return "";
  }

  const chunk = activeChunk.value;
  if (!chunk) {
    return escapeHtmlWithBreaks(content);
  }

  const { start, end } = resolveChunkHighlightRange(content, chunk);
  if (end <= start) {
    return escapeHtmlWithBreaks(content);
  }

  return [
    escapeHtmlWithBreaks(content.slice(0, start)),
    '<mark id="active-highlight" class="doc-preview__highlight">',
    escapeHtmlWithBreaks(content.slice(start, end)),
    "</mark>",
    escapeHtmlWithBreaks(content.slice(end)),
  ].join("");
});

function getRouteId(raw: string | string[] | undefined) {
  const value = Number(Array.isArray(raw) ? raw[0] : raw);
  return Number.isInteger(value) && value > 0 ? value : null;
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "暂无";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatFileSize(size: number) {
  if (!Number.isFinite(size) || size <= 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];
  let value = size;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function clampOffset(value: number, length: number) {
  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.max(0, Math.min(Math.trunc(value), length));
}

function resolveChunkHighlightRange(content: string, chunk: DocumentChunkSummary) {
  const offsetStart = clampOffset(chunk.start_offset, content.length);
  const offsetEnd = clampOffset(chunk.end_offset, content.length);
  const chunkContent = chunk.content.trim();

  if (!chunkContent) {
    return { start: offsetStart, end: offsetEnd };
  }

  const offsetText = content.slice(offsetStart, offsetEnd).trim();
  if (offsetText === chunkContent) {
    return { start: offsetStart, end: offsetEnd };
  }

  const nearbyStart = Math.max(0, offsetStart - 500);
  const nearbyEnd = Math.min(content.length, offsetEnd + 500);
  const nearbyIndex = content.slice(nearbyStart, nearbyEnd).indexOf(chunkContent);
  if (nearbyIndex >= 0) {
    const start = nearbyStart + nearbyIndex;
    return { start, end: start + chunkContent.length };
  }

  const globalIndex = content.indexOf(chunkContent);
  if (globalIndex >= 0) {
    return { start: globalIndex, end: globalIndex + chunkContent.length };
  }

  return { start: offsetStart, end: offsetEnd };
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeHtmlWithBreaks(value: string) {
  return escapeHtml(value).replaceAll("\n", "<br />");
}

watch(activeChunkId, async (value) => {
  if (!value) {
    return;
  }

  await nextTick();
  const highlight = previewBodyRef.value?.querySelector<HTMLElement>("#active-highlight");
  highlight?.scrollIntoView({ behavior: "smooth", block: "center" });
});

watch(
  () => documentDetail.value,
  (detail) => {
    adminBreadcrumbStore.setDynamicTitle("knowledge-base-detail", detail?.knowledge_base_name);
    adminBreadcrumbStore.setDynamicTitle("knowledge-base-document-detail", detail?.title);
  },
  { immediate: true },
);

async function loadPage() {
  if (!knowledgeBaseId.value || !documentId.value) {
    loadError.value = new Error("文档地址无效。");
    return;
  }

  loading.value = true;
  loadError.value = null;
  documentDetail.value = null;
  documentChunks.value = [];
  try {
    const [detail, chunks] = await Promise.all([
      getDocument(documentId.value),
      getDocumentChunks(documentId.value),
    ]);
    documentDetail.value = detail;
    documentChunks.value = chunks.items;
    activeChunkId.value = chunks.items.find((item) => item.id === activeChunkId.value)?.id ?? chunks.items[0]?.id ?? null;
    if (!activeChunkId.value) {
      searchKeyword.value = "";
    }
  } catch (error) {
    loadError.value = error;
  } finally {
    loading.value = false;
  }
}

function handleSelectChunk(chunkId: number) {
  activeChunkId.value = chunkId;
}

onMounted(() => {
  void loadPage();
});

watch(
  () => [route.params.knowledgeBaseId, route.params.documentId],
  () => {
    activeChunkId.value = null;
    searchKeyword.value = "";
    void loadPage();
  },
);
</script>

<template>
  <section class="document-detail-page">
    <AppLoading
      v-if="loading && !documentDetail"
      title="文档详情加载中"
      description="正在加载正文与分块信息，请稍候。"
      :blocks="4"
    />

    <AppError
      v-else-if="loadError"
      title="文档详情加载失败"
      description="暂时无法获取该文档详情，请稍后重试。"
      :error="loadError"
      @retry="loadPage"
    />

    <template v-else-if="documentDetail">
      <section class="document-detail-page__content">
        <section class="document-detail-page__layout">
          <article class="doc-preview">
            <div class="doc-preview__header">
              <div>
                <div class="doc-preview__document-info">
                  <div class="doc-preview__document-title-row">
                    <h1 class="doc-preview__document-title">
                      <el-icon><Document /></el-icon>
                      <span>{{ documentDetail.title }}</span>
                    </h1>
                    <StatusTag
                      :label="indexStatusMeta[documentDetail.index_status].label"
                      :type="indexStatusMeta[documentDetail.index_status].type"
                    />
                    <StatusTag
                      :label="lifecycleStatusMeta[documentDetail.status].label"
                      :type="lifecycleStatusMeta[documentDetail.status].type"
                    />
                  </div>
                  <div class="doc-preview__document-meta">
                    <span>分类：{{ documentDetail.category_name || "未分配分类" }}</span>
                    <span>{{ formatFileSize(documentDetail.size) }}</span>
                    <span>{{ documentChunks.length }} 个分块</span>
                    <span>更新于 {{ formatDateTime(documentDetail.updated_at) }}</span>
                  </div>
                </div>
              </div>
              <div class="doc-preview__header-actions">
                <StatusTag
                  v-if="activeChunk"
                  :label="`当前分块 #${activeChunk.chunk_index + 1}`"
                  type="info"
                />
                <el-button
                  :icon="RefreshRight"
                  :loading="loading"
                  size="small"
                  @click="loadPage"
                >
                  刷新
                </el-button>
              </div>
            </div>

            <div ref="previewBodyRef" class="doc-preview__body">
              <div
                v-if="documentContentHtml"
                class="doc-preview__content"
                v-html="documentContentHtml"
              />
              <AppEmpty
                v-else
                title="暂无正文内容"
                description="该文档没有可展示的正文文本。"
              />
            </div>
          </article>

          <aside class="chunk-panel">
            <div class="chunk-panel__header">
              <div>
                <p class="chunk-panel__title">
                  <el-icon><Folder /></el-icon>
                  分块查看
                </p>
                <p class="chunk-panel__hint">
                  共 {{ documentChunks.length }} 个真实解析分块
                </p>
              </div>

              <el-input
                v-model="searchKeyword"
                class="chunk-panel__search"
                size="small"
                clearable
                placeholder="搜索分块内容"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </div>

            <div class="chunk-panel__list">
              <button
                v-for="chunk in filteredChunks"
                :key="chunk.id"
                type="button"
                class="chunk-card"
                :class="{ 'is-active': activeChunkId === chunk.id }"
                @click="handleSelectChunk(chunk.id)"
              >
                <div class="chunk-card__header">
                  <span class="chunk-card__index">#{{ chunk.chunk_index + 1 }}</span>
                  <span class="chunk-card__kind">{{ chunk.chunk_kind }}</span>
                </div>

                <p class="chunk-card__path">
                  {{ chunk.section_path || "未命名分块" }}
                </p>
                <p class="chunk-card__content">
                  {{ chunk.content }}
                </p>

                <div class="chunk-card__footer">
                  <span>{{ chunk.start_offset }} - {{ chunk.end_offset }}</span>
                  <span v-if="chunk.block_types.length > 0">
                    {{ chunk.block_types.join(" / ") }}
                  </span>
                </div>
              </button>

              <AppEmpty
                v-if="filteredChunks.length === 0"
                title="未找到匹配分块"
                description="请调整搜索条件后再查看。"
              />
            </div>
          </aside>
        </section>
      </section>
    </template>
  </section>
</template>

<style scoped>
.document-detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.document-detail-page__content {
  min-height: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow: hidden;
}

.document-detail-page__layout {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(360px, 0.95fr);
  gap: 20px;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}

.doc-preview,
.chunk-panel {
  min-width: 0;
  border: 1px solid #dbe2ea;
  border-radius: 24px;
  background: #fff;
  overflow: hidden;
}

.doc-preview {
  display: flex;
  flex-direction: column;
  min-height: 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
  overflow: hidden;
}

.doc-preview__header,
.chunk-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 18px 20px;
}

.chunk-panel__title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
}

.chunk-panel__hint {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 12px;
}

.doc-preview__document-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.doc-preview__document-title-row,
.doc-preview__header-actions,
.doc-preview__document-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.doc-preview__document-title-row,
.doc-preview__document-meta {
  flex-wrap: wrap;
}

.doc-preview__document-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  max-width: min(620px, 100%);
  overflow: hidden;
  color: #0f172a;
  font-size: 17px;
  font-weight: 700;
  white-space: nowrap;
}

.doc-preview__document-title span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-preview__document-title .el-icon {
  flex-shrink: 0;
  color: #2563eb;
}

.doc-preview__document-meta {
  color: #64748b;
  font-size: 12px;
}

.doc-preview__header-actions {
  flex-shrink: 0;
}

.doc-preview__body {
  min-height: 0;
  flex: 1;
  overflow: auto;
  padding: 20px;
  background: #f8fafc;
}

.doc-preview__content {
  min-height: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.9;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 24px;
  max-width: 820px;
  margin: 0 auto;
}

.doc-preview__highlight {
  border-radius: 6px;
  background: rgba(37, 99, 235, 0.14);
  color: #1d4ed8;
  font-weight: 600;
}

.chunk-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
  overflow: hidden;
}

.chunk-panel__search {
  max-width: 220px;
}

.chunk-panel__list {
  min-height: 0;
  flex: 1;
  overflow: auto;
  background: #f8fafc;
  padding: 16px;
}

.chunk-card {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: #fff;
  cursor: pointer;
  margin-bottom: 12px;
  padding: 14px 16px;
  text-align: left;
  transition: all 0.18s ease;
}

.chunk-card:hover {
  border-color: #93c5fd;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.08);
  transform: translateY(-1px);
}

.chunk-card.is-active {
  border-color: #2563eb;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.18);
}

.chunk-card__header,
.chunk-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #64748b;
  font-size: 12px;
}

.chunk-card__index {
  color: #2563eb;
  font-weight: 700;
}

.chunk-card__kind {
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 2px 8px;
}

.chunk-card__path {
  margin: 10px 0 8px;
  color: #0f172a;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
}

.chunk-card__content {
  display: -webkit-box;
  margin: 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.7;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
}

@media (max-width: 1200px) {
  .document-detail-page__layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .doc-preview__header,
  .chunk-panel__header {
    flex-direction: column;
    align-items: stretch;
  }

  .chunk-panel__search {
    max-width: 100%;
  }

  .doc-preview__document-title {
    max-width: none;
  }

  .doc-preview__header-actions {
    justify-content: space-between;
  }
}
</style>
