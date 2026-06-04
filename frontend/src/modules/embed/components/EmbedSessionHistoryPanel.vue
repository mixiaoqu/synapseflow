<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ChatDotRound, Clock, Delete, Plus, Search } from "@element-plus/icons-vue";

import type { SessionSummary } from "@/modules/embed/composables/useEmbeddedAssistant";

const props = defineProps<{
  currentSessionId: string | null;
  sessions: SessionSummary[];
  loading: boolean;
  error: string | null;
  deletingSessionId: string | null;
}>();

const emit = defineEmits<{
  select: [sessionId: string];
  create: [];
  delete: [sessionId: string];
  refresh: [];
}>();

const visible = ref(false);
const keyword = ref("");

const filteredSessions = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase();
  if (!normalizedKeyword) {
    return props.sessions;
  }

  return props.sessions.filter((session) => {
    return (
      session.title.toLowerCase().includes(normalizedKeyword) ||
      (session.preview ?? "").toLowerCase().includes(normalizedKeyword)
    );
  });
});

watch(visible, (value) => {
  if (value) {
    emit("refresh");
  } else {
    keyword.value = "";
  }
});

function handleSelect(sessionId: string) {
  emit("select", sessionId);
  visible.value = false;
}

function handleCreate() {
  emit("create");
  visible.value = false;
}

function formatSessionTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  if (diffMs >= 0 && diffMs < 60 * 1000) {
    return "刚刚";
  }
  if (diffMs >= 0 && diffMs < 60 * 60 * 1000) {
    return `${Math.max(1, Math.floor(diffMs / 60000))} 分钟前`;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
</script>

<template>
  <el-popover
    v-model:visible="visible"
    trigger="click"
    placement="bottom-end"
    :width="360"
    popper-class="embed-history-popover"
  >
    <template #reference>
      <button
        type="button"
        class="embed-history-panel__trigger"
        title="历史对话"
        aria-label="历史对话"
      >
        <el-icon><Clock /></el-icon>
      </button>
    </template>

    <section class="embed-history-panel">
      <header class="embed-history-panel__header">
        <div class="embed-history-panel__header-main">
          <div class="embed-history-panel__icon">
            <el-icon><Clock /></el-icon>
          </div>
          <div class="embed-history-panel__title-wrap">
            <strong class="embed-history-panel__title">历史对话</strong>
            <span v-if="sessions.length > 0" class="embed-history-panel__count">{{ sessions.length }}</span>
          </div>
        </div>
      </header>

      <label class="embed-history-panel__search">
        <el-icon><Search /></el-icon>
        <input v-model="keyword" type="text" placeholder="搜索历史对话..." />
      </label>

      <div class="embed-history-panel__body">
        <div v-if="error" class="embed-history-panel__error">
          {{ error }}
        </div>

        <div v-if="loading" class="embed-history-panel__empty">
          <el-icon class="is-loading"><Clock /></el-icon>
          <span>正在加载历史对话...</span>
        </div>

        <div v-else-if="filteredSessions.length === 0" class="embed-history-panel__empty">
          <el-icon><ChatDotRound /></el-icon>
          <span>{{ sessions.length === 0 ? "暂无历史对话" : "没有匹配的会话" }}</span>
        </div>

        <div v-else class="embed-history-panel__list">
          <div
            v-for="session in filteredSessions"
            :key="session.id"
            class="embed-history-panel__item"
            :class="{ 'is-active': currentSessionId === session.id }"
          >
            <button
              type="button"
              class="embed-history-panel__item-main-button"
              @click="handleSelect(session.id)"
            >
            <div class="embed-history-panel__item-icon">
              <el-icon><ChatDotRound /></el-icon>
            </div>
            <div class="embed-history-panel__item-main">
              <div class="embed-history-panel__item-title">{{ session.title }}</div>
              <div v-if="session.preview" class="embed-history-panel__item-preview">
                {{ session.preview }}
              </div>
              <div class="embed-history-panel__item-time">{{ formatSessionTime(session.createdAt) }}</div>
            </div>
            </button>
            <button
              type="button"
              class="embed-history-panel__delete"
              :disabled="deletingSessionId === session.id"
              title="删除会话"
              @click.stop="emit('delete', session.id)"
            >
              <el-icon v-if="deletingSessionId === session.id" class="is-loading"><Clock /></el-icon>
              <el-icon v-else><Delete /></el-icon>
            </button>
          </div>
        </div>
      </div>

      <footer class="embed-history-panel__footer">
        <button type="button" class="embed-history-panel__create" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          <span>新建对话</span>
        </button>
      </footer>
    </section>
  </el-popover>
</template>

<style scoped>
.embed-history-panel {
  display: flex;
  flex-direction: column;
  max-height: min(70vh, 560px);
}

.embed-history-panel__header {
  padding-bottom: 12px;
}

.embed-history-panel__header-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.embed-history-panel__icon {
  display: inline-flex;
  width: 30px;
  height: 30px;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
  color: #ffffff;
}

.embed-history-panel__title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.embed-history-panel__title {
  font-size: 14px;
  color: #0f172a;
}

.embed-history-panel__count {
  padding: 2px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  font-size: 11px;
  color: #64748b;
}

.embed-history-panel__search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 0 12px;
  height: 40px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
  color: #94a3b8;
}

.embed-history-panel__search input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: #334155;
}

.embed-history-panel__body {
  min-height: 180px;
  max-height: 360px;
  overflow-y: auto;
}

.embed-history-panel__error {
  margin-bottom: 10px;
  padding: 10px 12px;
  border: 1px solid #fecaca;
  border-radius: 12px;
  background: #fef2f2;
  font-size: 12px;
  color: #dc2626;
}

.embed-history-panel__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 180px;
  color: #94a3b8;
  font-size: 12px;
}

.embed-history-panel__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.embed-history-panel__item {
  display: flex;
  width: 100%;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 14px;
  background: transparent;
  transition: all 0.2s ease;
}

.embed-history-panel__item:hover {
  border-color: #e2e8f0;
  background: #f8fafc;
}

.embed-history-panel__item.is-active {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.embed-history-panel__item-main-button {
  display: flex;
  flex: 1;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.embed-history-panel__item-icon {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #e2e8f0;
  color: #475569;
  flex-shrink: 0;
}

.embed-history-panel__item.is-active .embed-history-panel__item-icon {
  background: #dbeafe;
  color: #2563eb;
}

.embed-history-panel__item-main {
  flex: 1;
  min-width: 0;
}

.embed-history-panel__item-title {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
  color: #334155;
}

.embed-history-panel__item-preview {
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: #94a3b8;
}

.embed-history-panel__item-time {
  margin-top: 6px;
  font-size: 10px;
  color: #94a3b8;
}

.embed-history-panel__delete {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #cbd5e1;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.embed-history-panel__delete:hover:not(:disabled) {
  background: #fef2f2;
  color: #ef4444;
}

.embed-history-panel__delete:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.embed-history-panel__footer {
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
  margin-top: 12px;
}

.embed-history-panel__create {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 42px;
  border: 1px dashed #93c5fd;
  border-radius: 14px;
  background: rgba(239, 246, 255, 0.7);
  color: #2563eb;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.embed-history-panel__create:hover {
  background: rgba(219, 234, 254, 0.85);
  border-color: #60a5fa;
}

.embed-history-panel__trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}

.embed-history-panel__trigger:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #0f172a;
}
</style>
