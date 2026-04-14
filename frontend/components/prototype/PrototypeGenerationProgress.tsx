/**
 * 原型生成：实时进度条 + 流式日志
 */
'use client';

import { useEffect, useRef } from 'react';
import { usePrototypeStore } from '@/stores/prototypeStore';

function logTypeClass(type: string): string {
  if (type === 'error') return 'text-red-700 bg-red-50 border-red-100';
  if (type === 'success') return 'text-slate-800 bg-slate-50 border-slate-100';
  return 'text-slate-600 bg-white border-slate-100';
}

export function PrototypeGenerationProgress() {
  const {
    isGenerating,
    progressPercent,
    progressStep,
    progressTotalSteps,
    currentNodeLabel,
    progressLogs,
  } = usePrototypeStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isGenerating || progressLogs.length === 0) return;
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [progressLogs.length, isGenerating]);

  if (!isGenerating && progressLogs.length === 0) {
    return null;
  }

  const showBar = isGenerating || progressPercent > 0;
  const pct = Math.min(100, Math.max(0, progressPercent));

  return (
    <div className="bg-white rounded-lg border flex flex-col min-h-0 shrink-0 overflow-hidden">
      <div className="px-4 py-3 border-b bg-slate-50">
        <div className="flex items-center justify-between gap-2 mb-2">
          <h3 className="font-semibold text-gray-900 text-sm">生成进度</h3>
          {showBar ? (
            <span className="text-xs text-slate-500 tabular-nums">
              {progressStep > 0
                ? `步骤 ${progressStep} / ${progressTotalSteps}`
                : '准备中'}
              {currentNodeLabel ? ` · ${currentNodeLabel}` : ''}
            </span>
          ) : null}
        </div>
        {showBar ? (
          <div className="w-full h-2 rounded-full bg-slate-200 overflow-hidden">
            <div
              className="h-full rounded-full bg-blue-600 transition-[width] duration-300 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
        ) : null}
        {showBar ? (
          <p className="text-xs text-slate-500 mt-1.5 tabular-nums">{pct}%</p>
        ) : null}
      </div>

      {progressLogs.length > 0 ? (
        <div className="max-h-[220px] overflow-y-auto px-3 py-2 space-y-1.5 text-xs font-mono">
          {progressLogs.map((row) => (
            <div
              key={row.id}
              className={`rounded border px-2 py-1.5 leading-relaxed ${logTypeClass(row.type)}`}
            >
              <span className="text-slate-400 shrink-0 mr-2">
                {new Date(row.at).toLocaleTimeString('zh-CN', {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </span>
              <span className="font-medium text-slate-600">[{row.node}]</span>{' '}
              <span className="break-words">{row.content}</span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      ) : isGenerating ? (
        <div className="px-4 py-6 text-center text-sm text-slate-400">等待服务端推送…</div>
      ) : null}
    </div>
  );
}
