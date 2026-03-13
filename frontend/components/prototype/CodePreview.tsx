/**
 * 代码预览组件
 * 支持查看和编辑生成的HTML/CSS/JS代码
 */
'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';

// 懒加载Monaco编辑器（避免SSR问题）
const Editor = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => (
    <div className="h-full flex items-center justify-center bg-gray-100">
      <div className="text-gray-500">加载编辑器...</div>
    </div>
  ),
});

interface Props {
  html: string;
  css: string;
  js: string;
  onCodeChange?: (file: 'html' | 'css' | 'js', code: string) => void;
  readonly?: boolean;
}

export function CodePreview({ html, css, js, onCodeChange, readonly = false }: Props) {
  const [activeTab, setActiveTab] = useState<'html' | 'css' | 'js'>('html');

  const tabs = [
    { id: 'html', label: 'HTML', icon: '📄', language: 'html', code: html },
    { id: 'css', label: 'CSS', icon: '🎨', language: 'css', code: css },
    { id: 'js', label: 'JavaScript', icon: '⚡', language: 'javascript', code: js },
  ];

  const activeCode = tabs.find((t) => t.id === activeTab);

  return (
    <div className="h-full flex flex-col bg-white rounded-lg border overflow-hidden">
      {/* Tab导航 */}
      <div className="flex items-center border-b bg-gray-50">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`
              relative px-6 py-3 font-medium transition-colors
              ${activeTab === tab.id
                ? 'text-blue-600 bg-white'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }
            `}
          >
            <div className="flex items-center gap-2">
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </div>
            {activeTab === tab.id && (
              <motion.div
                layoutId="activeTab"
                className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600"
              />
            )}
          </button>
        ))}

        {/* 右侧操作按钮 */}
        <div className="ml-auto px-4 flex items-center gap-2">
          <button
            onClick={() => {
              const code = activeCode?.code || '';
              navigator.clipboard.writeText(code);
            }}
            className="text-xs px-3 py-1 rounded bg-gray-200 hover:bg-gray-300 text-gray-700"
          >
            复制
          </button>
          <button
            onClick={() => {
              const blob = new Blob([html, '\n\n<style>\n', css, '\n</style>\n\n<script>\n', js, '\n</script>'], 
                { type: 'text/html' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'prototype.html';
              a.click();
            }}
            className="text-xs px-3 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white"
          >
            下载全部
          </button>
        </div>
      </div>

      {/* 代码编辑器 */}
      <div className="flex-1 overflow-hidden">
        {activeCode && (
          <Editor
            height="100%"
            language={activeCode.language}
            value={activeCode.code}
            onChange={(value) => {
              if (!readonly && onCodeChange && value !== undefined) {
                onCodeChange(activeTab, value);
              }
            }}
            theme="vs-dark"
            options={{
              readOnly: readonly,
              minimap: { enabled: true },
              fontSize: 14,
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 2,
            }}
          />
        )}
      </div>
    </div>
  );
}
