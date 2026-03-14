/**
 * 原型生成状态管理
 */
import { create } from 'zustand';

export interface AgentNode {
  id: string;
  name: string;
  model: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  duration?: number;
  output?: any;
  startTime?: number;
  detailedOutput?: any;
}

export interface LogMessage {
  timestamp: Date;
  node: string;
  type: 'info' | 'success' | 'error' | 'warning';
  content: string;
}

interface PrototypeState {
  // 输入数据
  requirements: string;
  
  // 执行状态
  isGenerating: boolean;
  currentNode: string | null;
  progress: number;
  
  // 智能体节点状态
  nodes: AgentNode[];
  
  // 实时日志
  logs: LogMessage[];
  
  // 生成结果
  generatedCode: {
    html: string;
    css: string;
    js: string;
  };
  previewUrl: string | null;
  
  // 操作方法
  setRequirements: (req: string) => void;
  startGeneration: () => void;
  updateNodeStatus: (nodeId: string, updates: Partial<AgentNode>) => void;
  addLog: (log: Omit<LogMessage, 'timestamp'>) => void;
  setGeneratedCode: (code: { html: string; css: string; js: string }) => void;
  setPreviewUrl: (url: string) => void;
  completeGeneration: () => void;
  reset: () => void;
}

export const usePrototypeStore = create<PrototypeState>((set) => ({
  // 初始状态
  requirements: '',
  isGenerating: false,
  currentNode: null,
  progress: 0,
  nodes: [
    { id: 'extract_requirements', name: '提取需求', model: 'Kimi-长文本理解', status: 'pending' },
    { id: 'design_components', name: '设计组件', model: 'Deepseek-设计决策', status: 'pending' },
    { id: 'generate_html', name: '生成HTML', model: 'Deepseek-代码生成', status: 'pending' },
    { id: 'validate_preview', name: '代码验证', model: 'Deepseek-代码验证', status: 'pending' },
  ],
  logs: [],
  generatedCode: { html: '', css: '', js: '' },
  previewUrl: null,

  // 方法实现
  setRequirements: (req) => set({ requirements: req }),

  startGeneration: () => set((state) => ({
    isGenerating: true,
    progress: 0,
    logs: [],
    nodes: state.nodes.map((n) => ({ ...n, status: 'pending' as const }))
  })),

  updateNodeStatus: (nodeId, updates) => set((state) => ({
    currentNode: nodeId,
    nodes: state.nodes.map((node) =>
      node.id === nodeId
        ? { ...node, ...updates, startTime: updates.status === 'running' ? Date.now() : node.startTime }
        : node
    ),
    progress: updates.status === 'completed'
      ? ((state.nodes.filter((n) => n.status === 'completed').length + 1) / state.nodes.length) * 100
      : state.progress,
  })),

  addLog: (log) => set((state) => ({
    logs: [...state.logs, { ...log, timestamp: new Date() }],
  })),

  setGeneratedCode: (code) => set({ generatedCode: code }),

  setPreviewUrl: (url) => set({ previewUrl: url }),

  completeGeneration: () => set({
    isGenerating: false,
    currentNode: null,
    progress: 100,
  }),

  reset: () => set({
    isGenerating: false,
    currentNode: null,
    progress: 0,
    logs: [],
    generatedCode: { html: '', css: '', js: '' },
    previewUrl: null,
  }),
}));
