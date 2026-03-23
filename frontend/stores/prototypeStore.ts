/**
 * 原型生成状态管理
 */
import { create } from 'zustand';

interface PrototypeState {
  isGenerating: boolean;
  progressIndeterminate: boolean;
  generatedCode: {
    html: string;
    css: string;
    js: string;
  };
  previewUrl: string | null;

  startGeneration: () => void;
  setGeneratedCode: (code: { html: string; css: string; js: string }) => void;
  setPreviewUrl: (url: string) => void;
  completeGeneration: () => void;
  reset: () => void;
}

export const usePrototypeStore = create<PrototypeState>((set) => ({
  isGenerating: false,
  progressIndeterminate: false,
  generatedCode: { html: '', css: '', js: '' },
  previewUrl: null,

  startGeneration: () =>
    set({
      isGenerating: true,
      progressIndeterminate: true,
    }),

  setGeneratedCode: (code) => set({ generatedCode: code }),

  setPreviewUrl: (url) => set({ previewUrl: url }),

  completeGeneration: () =>
    set({
      isGenerating: false,
      progressIndeterminate: false,
    }),

  reset: () =>
    set({
      isGenerating: false,
      progressIndeterminate: false,
      generatedCode: { html: '', css: '', js: '' },
      previewUrl: null,
    }),
}));
