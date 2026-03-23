/**
 * 原型生成流式 Hook（仅上传文件 → /prototype/generate/stream/file）
 */
import { useEffect, useRef } from 'react';
import { usePrototypeStore } from '@/stores/prototypeStore';
import { toast } from 'sonner';
import { API_V1 } from '@/lib/api/config';

export function usePrototypeStream() {
  const abortControllerRef = useRef<AbortController | null>(null);
  const {
    startGeneration,
    setGeneratedCode,
    setPreviewUrl,
    completeGeneration,
  } = usePrototypeStore();

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

          const eventType = eventMatch[1];
          const eventData = JSON.parse(eventMatch[2]);
          handleSSEEvent(eventType, eventData);
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

  const handleSSEEvent = (eventType: string, data: Record<string, unknown>) => {
    switch (eventType) {
      case 'complete':
        setGeneratedCode({
          html: String(data.html ?? ''),
          css: String(data.css ?? ''),
          js: String(data.js ?? ''),
        });
        setPreviewUrl(data.preview_url ? String(data.preview_url) : null);
        completeGeneration();
        toast.success(`原型生成完成！耗时 ${data.total_duration}s`);
        break;

      case 'error':
        toast.error(`生成失败: ${data.message}`);
        completeGeneration();
        break;

      default:
        break;
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
