/**
 * 实时日志流组件
 * 显示智能体执行过程中的日志
 */
'use client';

import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface LogMessage {
  timestamp: Date;
  node: string;
  type: 'info' | 'success' | 'error' | 'warning';
  content: string;
}

interface Props {
  logs: LogMessage[];
  maxHeight?: string;
}

export function StreamingLog({ logs, maxHeight = '500px' }: Props) {
  const logRef = useRef<HTMLDivElement>(null);

  // 自动滚动到最新消息
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTo({
        top: logRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [logs]);

  const getTypeStyle = (type: LogMessage['type']) => {
    switch (type) {
      case 'success':
        return 'text-green-400';
      case 'error':
        return 'text-red-400';
      case 'warning':
        return 'text-yellow-400';
      default:
        return 'text-blue-400';
    }
  };

  const getTypeIcon = (type: LogMessage['type']) => {
    switch (type) {
      case 'success':
        return '✓';
      case 'error':
        return '✗';
      case 'warning':
        return '⚠';
      default:
        return '➤';
    }
  };

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
      <div className="bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-300">实时日志</span>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-xs text-gray-400">运行中</span>
          </div>
          <span className="text-xs text-gray-500">
            {logs.length} 条消息
          </span>
        </div>
      </div>

      <div
        ref={logRef}
        className="p-4 font-mono text-sm overflow-y-auto"
        style={{ maxHeight }}
      >
        {logs.length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            等待智能体执行...
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {logs.map((log, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3 }}
                className="mb-2 leading-relaxed"
              >
                <span className="text-gray-500">
                  [{log.timestamp.toLocaleTimeString()}]
                </span>
                {' '}
                <span className="text-purple-400 font-semibold">
                  [{log.node}]
                </span>
                {' '}
                <span className={getTypeStyle(log.type)}>
                  {getTypeIcon(log.type)}
                </span>
                {' '}
                <span className="text-gray-300 break-words">
                  {log.content}
                </span>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
