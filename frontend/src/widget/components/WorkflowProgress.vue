<script setup lang="ts">
import { computed, ref } from "vue";
import { ArrowDown, Check, Loading, WarningFilled } from "@element-plus/icons-vue";

import {
  getWorkflowDisplayStages,
  type ChatWorkflowRun,
  type WorkflowDisplayStage,
} from "../../shared/lib/stream/workflowRun";

const props = defineProps<{ run: ChatWorkflowRun | null }>();
const isExpanded = ref(false);
const stages = computed(() =>
  getWorkflowDisplayStages(props.run).filter((stage) => stage.status !== "pending"),
);

const summary = computed(() => {
  if (props.run?.status === "done") return "处理完成";
  if (props.run?.status === "error") return props.run.error?.message || "处理遇到问题";
  const current = stages.value.find((stage) => stage.status === "running");
  return current ? `正在${current.title}…` : props.run?.message || "正在处理你的问题…";
});

function stageDetail(stage: WorkflowDisplayStage) {
  const activity = stage.activities[stage.activities.length - 1];
  return activity?.text && activity.text !== stage.title ? activity.text : "";
}
</script>

<template>
  <section
    v-if="run"
    class="widget-workflow"
    :class="`is-${run.status}`"
    aria-live="polite"
  >
    <div class="widget-workflow__summary">
      <span
        class="widget-workflow__status"
        aria-hidden="true"
      >
        <el-icon v-if="run.status === 'done'"><Check /></el-icon>
        <el-icon v-else-if="run.status === 'error'"><WarningFilled /></el-icon>
        <el-icon
          v-else
          class="is-loading"
        ><Loading /></el-icon>
      </span>
      <span class="widget-workflow__summary-text">{{ summary }}</span>
      <button
        v-if="stages.length"
        type="button"
        class="widget-workflow__toggle"
        :title="isExpanded ? '收起执行过程' : '查看执行过程'"
        :aria-label="isExpanded ? '收起执行过程' : '查看执行过程'"
        :aria-expanded="isExpanded"
        @click="isExpanded = !isExpanded"
      >
        <el-icon
          class="widget-workflow__arrow"
          :class="{ 'is-open': isExpanded }"
        >
          <ArrowDown />
        </el-icon>
      </button>
    </div>

    <div
      v-if="isExpanded && stages.length"
      class="widget-workflow__stages"
    >
      <div
        v-for="stage in stages"
        :key="stage.id"
        class="widget-workflow__stage"
      >
        <span
          class="widget-workflow__stage-mark"
          :class="`is-${stage.status}`"
        >
          <el-icon v-if="stage.status === 'success'"><Check /></el-icon>
          <el-icon v-else-if="stage.status === 'error'"><WarningFilled /></el-icon>
          <el-icon
            v-else
            class="is-loading"
          ><Loading /></el-icon>
        </span>
        <span class="widget-workflow__stage-copy">
          <strong>{{ stage.title }}</strong>
          <small v-if="stageDetail(stage)">{{ stageDetail(stage) }}</small>
        </span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.widget-workflow { width: min(100%, 410px); color: #334155; }
.widget-workflow__summary { display: flex; width: 100%; min-height: 34px; align-items: center; gap: 8px; }
.widget-workflow__status { display: grid; width: 16px; height: 16px; flex: 0 0 16px; place-items: center; color: #0891b2; font-size: 15px; }
.widget-workflow.is-done .widget-workflow__status { color: #059669; }
.widget-workflow.is-error .widget-workflow__status { color: #dc2626; }
.widget-workflow__summary-text { min-width: 0; overflow: hidden; font-size: 13px; font-weight: 500; line-height: 1.45; text-overflow: ellipsis; white-space: nowrap; }
.widget-workflow__toggle { display: grid; width: 30px; height: 30px; margin-left: auto; padding: 0; flex: 0 0 30px; place-items: center; border: 0; border-radius: 50%; background: #eff9fb; color: #475569; cursor: pointer; transition: background 0.18s ease, color 0.18s ease; }
.widget-workflow__toggle:hover { background: #dff4f7; color: #0891b2; }
.widget-workflow__toggle:focus-visible { outline: 3px solid rgba(8, 145, 178, 0.28); outline-offset: 2px; }
.widget-workflow__arrow { font-size: 14px; transition: transform 0.18s ease; }
.widget-workflow__arrow.is-open { transform: rotate(180deg); }
.widget-workflow__stages { position: relative; display: flex; margin-top: 4px; padding: 12px 14px 13px 17px; flex-direction: column; gap: 12px; border-radius: 8px; background: #f8fbfc; }
.widget-workflow__stage { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 9px; align-items: flex-start; }
.widget-workflow__stage-mark { display: grid; width: 18px; height: 18px; place-items: center; border-radius: 50%; background: #e6f7fa; color: #0891b2; }
.widget-workflow__stage-mark.is-success { background: #ecfdf5; color: #059669; }
.widget-workflow__stage-mark.is-error { background: #fef2f2; color: #dc2626; }
.widget-workflow__stage-copy { display: flex; min-width: 0; flex-direction: column; gap: 2px; }
.widget-workflow__stage-copy strong { overflow: hidden; color: #334155; font-size: 12px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.widget-workflow__stage-copy small { overflow: hidden; color: #64748b; font-size: 11px; line-height: 1.45; text-overflow: ellipsis; white-space: nowrap; }
@media (prefers-reduced-motion: reduce) { .widget-workflow__toggle, .widget-workflow__arrow { transition: none; } }
</style>
