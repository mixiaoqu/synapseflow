import { useCallback, useEffect, useRef } from "react";
import { toast } from "sonner";

import { API_V1 } from "@/lib/api/config";
import { consumeSseStream, type SseEnvelope } from "@/lib/stream/sse";
import { usePrototypeStore } from "@/stores/prototypeStore";

type PrototypeStreamData = Record<string, unknown>;

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
    (env: SseEnvelope<PrototypeStreamData>) => {
      const data = env.data;

      switch (env.type) {
        case "start":
          appendProgressLog({
            node: env.node_name || "System",
            nodeId: env.node_id || "system",
            type: "info",
            content: String(data.message ?? "Starting generation"),
          });
          break;

        case "progress": {
          const step = Number(data.step);
          const totalSteps = Number(data.total_steps) || 7;
          const percent = Number(data.percent);

          setPipelineProgress({
            percent: Number.isFinite(percent) ? percent : 0,
            step: Number.isFinite(step) ? step : 0,
            totalSteps,
            currentNodeLabel: env.node_name || "",
          });
          break;
        }

        case "log":
          appendProgressLog({
            node: env.node_name || "System",
            nodeId: env.node_id || "system",
            type: String(data.level ?? "info"),
            content: String(data.content ?? ""),
          });
          break;

        case "complete": {
          const totalSteps = Number(data.total_steps);
          const total =
            Number.isFinite(totalSteps) && totalSteps > 0 ? totalSteps : 7;

          setPipelineProgress({
            percent: 100,
            step: total,
            totalSteps: total,
            currentNodeLabel: "Completed",
          });
          setGeneratedCode({
            html: String(data.html ?? ""),
            css: String(data.css ?? ""),
            js: String(data.js ?? ""),
          });
          setPreviewUrl(data.preview_url ? String(data.preview_url) : null);
          completeGeneration();
          toast.success(
            `Prototype generated in ${data.total_duration != null ? String(data.total_duration) : "?"}s`,
          );
          break;
        }

        case "error": {
          const message = String(data.message ?? "Unknown error");
          appendProgressLog({
            node: env.node_name || "System",
            nodeId: env.node_id || "system",
            type: "error",
            content: message,
          });
          toast.error(`Generation failed: ${message}`);
          completeGeneration();
          break;
        }

        default:
          break;
      }
    },
    [
      appendProgressLog,
      completeGeneration,
      setGeneratedCode,
      setPipelineProgress,
      setPreviewUrl,
    ],
  );

  const startStreaming = useCallback(
    async (file: File) => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();
      startGeneration();

      try {
        const url = `${API_V1}/prototype/generate/stream/file`;
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(url, {
          method: "POST",
          body: formData,
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        if (!response.body) {
          throw new Error("Unable to read response stream");
        }

        await consumeSseStream(response.body, handleStreamEnvelope);
      } catch (error: unknown) {
        const err = error as { name?: string; message?: string };
        if (err.name !== "AbortError") {
          toast.error(err.message || "Generation failed, please try again");
          completeGeneration();
        }
      }
    },
    [completeGeneration, handleStreamEnvelope, startGeneration],
  );

  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      completeGeneration();
    }
  }, [completeGeneration]);

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
