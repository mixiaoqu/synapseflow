/**
 * 原型生成状态管理
 */
import { create } from 'zustand';

const MAX_PROGRESS_LOGS = 200;

export interface ProgressLogEntry {
  id: string;
  at: number;
  node: string;
  nodeId?: string;
  type: string;
  content: string;
}

interface PrototypeState {
  isGenerating: boolean;
  progressPercent: number;
  progressStep: number;
  progressTotalSteps: number;
  currentNodeLabel: string;
  progressLogs: ProgressLogEntry[];
  generatedCode: {
    html: string;
    css: string;
    js: string;
  };
  previewUrl: string | null;

  startGeneration: () => void;
  appendProgressLog: (entry: Omit<ProgressLogEntry, 'id' | 'at'>) => void;
  setPipelineProgress: (p: {
    percent: number;
    step: number;
    totalSteps: number;
    currentNodeLabel: string;
  }) => void;
  setGeneratedCode: (code: { html: string; css: string; js: string }) => void;
  setPreviewUrl: (url: string | null) => void;
  completeGeneration: () => void;
  reset: () => void;
}

let logSeq = 0;

export const usePrototypeStore = create<PrototypeState>((set) => ({
  isGenerating: false,
  progressPercent: 0,
  progressStep: 0,
  progressTotalSteps: 7,
  currentNodeLabel: '',
  progressLogs: [],
  generatedCode: { html: '', css: '', js: '' },
  previewUrl: null,

  startGeneration: () =>
    set({
      isGenerating: true,
      progressPercent: 0,
      progressStep: 0,
      progressTotalSteps: 7,
      currentNodeLabel: '',
      progressLogs: [],
    }),

  appendProgressLog: (entry) =>
    set((state) => {
      logSeq += 1;
      const id = `${Date.now()}-${logSeq}`;
      const next: ProgressLogEntry = { ...entry, id, at: Date.now() };
      const logs = [...state.progressLogs, next];
      return {
        progressLogs:
          logs.length > MAX_PROGRESS_LOGS ? logs.slice(-MAX_PROGRESS_LOGS) : logs,
      };
    }),

  setPipelineProgress: (p) =>
    set({
      progressPercent: p.percent,
      progressStep: p.step,
      progressTotalSteps: p.totalSteps || 7,
      currentNodeLabel: p.currentNodeLabel,
    }),

  setGeneratedCode: (code) => set({ generatedCode: code }),

  setPreviewUrl: (url) => set({ previewUrl: url }),

  completeGeneration: () =>
    set({
      isGenerating: false,
    }),

  reset: () =>
    set({
      isGenerating: false,
      progressPercent: 0,
      progressStep: 0,
      progressTotalSteps: 7,
      currentNodeLabel: '',
      progressLogs: [],
      generatedCode: { html: '', css: '', js: '' },
      previewUrl: null,
    }),
}));
