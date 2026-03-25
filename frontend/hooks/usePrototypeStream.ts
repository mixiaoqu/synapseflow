/**
 * 原型生成流式 Hook（上传文件 → /prototype/generate/stream/file）
 * SSE 固定 event: message，业务类型见 JSON 信封 type 字段。
 */
import { useEffect, useRef, useCallback } from 'react';
import { usePrototypeStore } from '@/stores/prototypeStore';
import { toast } from 'sonner';
import { API_V1 } from '@/lib/api/config';

/** 与后端 prototype_stream._stream_envelope 对齐 */
interface StreamEnvelope {
  type: string;
  node_id: string;
  node_name: string;
  timestamp: number;
  data: Record<string, unknown>;
}

function isStreamEnvelope(raw: unknown): raw is StreamEnvelope {
  if (!raw || typeof raw !== 'object') return false;
  const o = raw as Record<string, unknown>;
  return (
    typeof o.type === 'string' &&
    o.data !== null &&
    typeof o.data === 'object' &&
    !Array.isArray(o.data)
  );
}

export function usePrototypeStream() {
  const abortControllerRef = useRef<AbortController | null>(null);
  const {
    startGeneration,
    appendProgressLog,
    setPipelineProgress,
    setGeneratedCode,
    setPreviewUrl,
    completeGeneration,
  } = usePrototypeStore();

  const handleStreamEnvelope = useCallback(
    (env: StreamEnvelope) => {
      const d = env.data;
      switch (env.type) {
        case 'start':
          appendProgressLog({
            node: env.node_name || 'System',
            nodeId: env.node_id || 'system',
            type: 'info',
            content: String(d.message ?? '开始'),
          });
          break;

        case 'progress': {
          const step = Number(d.step);
          const totalSteps = Number(d.total_steps) || 7;
          const percent = Number(d.percent);
          setPipelineProgress({
            percent: Number.isFinite(percent) ? percent : 0,
            step: Number.isFinite(step) ? step : 0,
            totalSteps,
            currentNodeLabel: env.node_name || '',
          });
          break;
        }

        case 'log':
          appendProgressLog({
            node: env.node_name || '',
            nodeId: env.node_id || undefined,
            type: String(d.level ?? 'info'),
            content: String(d.content ?? ''),
          });
          break;

        case 'complete': {
          const totalSteps = Number(d.total_steps);
          const total =
            Number.isFinite(totalSteps) && totalSteps > 0 ? totalSteps : 7;
          setPipelineProgress({
            percent: 100,
            step: total,
            totalSteps: total,
            currentNodeLabel: '已完成',
          });
          setGeneratedCode({
            html: String(d.html ?? ''),
            css: String(d.css ?? ''),
            js: String(d.js ?? ''),
          });
          setPreviewUrl(d.preview_url ? String(d.preview_url) : null);
          completeGeneration();
          toast.success(
            `原型生成完成！耗时 ${d.total_duration != null ? String(d.total_duration) : '?'}s`,
          );
          break;
        }

        case 'error': {
          const msg = String(d.message ?? '未知错误');
          appendProgressLog({
            node: env.node_name || 'System',
            nodeId: env.node_id || 'system',
            type: 'error',
            content: msg,
          });
          toast.error(`生成失败: ${msg}`);
          completeGeneration();
          break;
        }

        default:
          break;
      }
    },
    [
      appendProgressLog,
      setPipelineProgress,
      setGeneratedCode,
      setPreviewUrl,
      completeGeneration,
    ],
  );

  const startStreaming = async (file: File) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();

    startGeneration();

    try {
      const url = `${API_V1}/prototype/generate/stream/file`;
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(url, {
        method: 'POST',
        body: formData,
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (!reader) {
        throw new Error('无法获取响应流');
      }

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;

          const eventMatch = line.match(/event:\s*(\w+)\ndata:\s*(.+)/s);
          if (!eventMatch) continue;

          let rawData = eventMatch[2].trim();
          if (rawData.endsWith('\n')) {
            rawData = rawData.replace(/\n+$/, '');
          }
          let parsed: unknown;
          try {
            parsed = JSON.parse(rawData);
          } catch {
            continue;
          }
          if (!isStreamEnvelope(parsed)) continue;
          handleStreamEnvelope(parsed);
        }
      }
    } catch (error: unknown) {
      const err = error as { name?: string; message?: string };
      if (err.name !== 'AbortError') {
        toast.error('生成失败，请重试');
        completeGeneration();
      }
    }
  };

  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      completeGeneration();
    }
  };

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    startStreaming,
    stopStreaming,
  };
}
