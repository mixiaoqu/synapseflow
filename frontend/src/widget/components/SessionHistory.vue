<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ChatLineRound, Clock, Delete, Loading, Plus, Search } from "@element-plus/icons-vue";

import type { WidgetSessionSummary } from "../client/agent-chat-api";

const props = defineProps<{
  currentSessionId: string | null;
  sessions: WidgetSessionSummary[];
  loading: boolean;
}>();
const emit = defineEmits<{
  load: [];
  select: [sessionId: string];
  create: [];
  delete: [sessionId: string];
}>();
const isOpen = ref(false);
const keyword = ref("");
const filtered = computed(() => {
  const value = keyword.value.trim().toLowerCase();
  if (!value) return props.sessions;
  return props.sessions.filter((item) =>
    `${item.title} ${item.preview || ""}`.toLowerCase().includes(value),
  );
});

watch(isOpen, (open) => { if (open) emit("load"); else keyword.value = ""; });
function select(sessionId: string) { emit("select", sessionId); isOpen.value = false; }
function create() { emit("create"); isOpen.value = false; }
</script>

<template>
  <div class="widget-history">
    <button
      type="button"
      class="widget-history__trigger"
      title="历史对话"
      :aria-expanded="isOpen"
      @click="isOpen = !isOpen"
    >
      <el-icon><Clock /></el-icon>
    </button>

    <section
      v-if="isOpen"
      class="widget-history__panel"
      aria-label="历史对话"
    >
      <header><strong>历史对话</strong><span>{{ sessions.length }}</span></header>
      <label class="widget-history__search">
        <el-icon><Search /></el-icon>
        <input
          v-model="keyword"
          type="search"
          placeholder="搜索历史对话"
          aria-label="搜索历史对话"
        >
      </label>
      <div class="widget-history__body">
        <div
          v-if="loading"
          class="widget-history__empty"
        >
          <el-icon class="is-loading">
            <Loading />
          </el-icon>加载中...
        </div>
        <div
          v-else-if="!filtered.length"
          class="widget-history__empty"
        >
          <el-icon><ChatLineRound /></el-icon>暂无历史对话
        </div>
        <div
          v-else
          class="widget-history__list"
        >
          <div
            v-for="session in filtered"
            :key="session.session_id"
            class="widget-history__item"
            :class="{ 'is-active': session.session_id === currentSessionId }"
          >
            <button
              type="button"
              class="widget-history__main"
              @click="select(session.session_id)"
            >
              <strong>{{ session.title || "新对话" }}</strong>
              <span>{{ session.preview || "暂无预览" }}</span>
            </button>
            <button
              type="button"
              class="widget-history__delete"
              title="删除对话"
              @click.stop="emit('delete', session.session_id)"
            >
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </div>
      </div>
      <footer>
        <button
          type="button"
          @click="create"
        >
          <el-icon><Plus /></el-icon>新建对话
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.widget-history { position: relative; }
.widget-history__trigger { display: grid; width: 40px; height: 40px; padding: 0; place-items: center; border: 1px solid #dbe5ea; border-radius: 8px; background: #fff; color: #475569; cursor: pointer; }
.widget-history__trigger:hover { background: #f0f9fa; color: #0891b2; }
.widget-history button:focus-visible, .widget-history input:focus-visible { outline: 3px solid rgba(8, 145, 178, 0.28); outline-offset: 1px; }
.widget-history__panel { position: absolute; z-index: 8; top: 46px; right: 0; display: flex; width: min(350px, calc(100vw - 40px)); max-height: 440px; flex-direction: column; overflow: hidden; border: 1px solid #dbe5ea; border-radius: 8px; background: #fff; box-shadow: 0 18px 44px rgba(15, 23, 42, 0.18); }
.widget-history__panel > header { display: flex; min-height: 46px; padding: 0 13px; align-items: center; justify-content: space-between; border-bottom: 1px solid #edf2f5; }
.widget-history__panel > header strong { color: #164e63; font-size: 14px; }
.widget-history__panel > header span { min-width: 22px; padding: 2px 6px; border-radius: 8px; background: #e6f7fa; color: #0e7490; font-size: 11px; text-align: center; }
.widget-history__search { display: flex; margin: 10px 10px 4px; padding: 0 10px; align-items: center; gap: 7px; border: 1px solid #dbe5ea; border-radius: 7px; color: #94a3b8; }
.widget-history__search input { min-width: 0; height: 36px; flex: 1; border: 0; outline: 0; background: transparent; font: inherit; font-size: 12px; }
.widget-history__body { min-height: 120px; overflow-y: auto; padding: 6px; }
.widget-history__empty { display: flex; min-height: 130px; align-items: center; justify-content: center; gap: 7px; color: #78909c; font-size: 12px; }
.widget-history__list { display: flex; flex-direction: column; gap: 2px; }
.widget-history__item { display: flex; min-width: 0; align-items: center; border-radius: 6px; }
.widget-history__item:hover, .widget-history__item.is-active { background: #ecfeff; }
.widget-history__main { display: flex; min-width: 0; flex: 1; padding: 8px 9px; flex-direction: column; gap: 3px; border: 0; background: transparent; cursor: pointer; text-align: left; }
.widget-history__main strong, .widget-history__main span { width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.widget-history__main strong { color: #334155; font-size: 12px; }
.widget-history__main span { color: #78909c; font-size: 11px; }
.widget-history__delete { display: grid; width: 34px; height: 34px; flex: 0 0 34px; padding: 0; place-items: center; border: 0; border-radius: 6px; background: transparent; color: #94a3b8; cursor: pointer; }
.widget-history__delete:hover { background: #fef2f2; color: #dc2626; }
.widget-history__panel > footer { padding: 8px 10px; border-top: 1px solid #edf2f5; }
.widget-history__panel > footer button { display: flex; width: 100%; height: 38px; align-items: center; justify-content: center; gap: 6px; border: 1px solid #bae6ef; border-radius: 7px; background: #ecfeff; color: #0e7490; cursor: pointer; font: inherit; font-size: 12px; font-weight: 600; }
@media (max-width: 480px) { .widget-history__panel { position: fixed; top: 70px; right: 12px; left: 12px; width: auto; } }
</style>
