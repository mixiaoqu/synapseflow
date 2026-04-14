/**
 * 原型预览组件
 * 使用iframe实时预览生成的HTML
 */
'use client';

import { useEffect, useState } from 'react';

interface Props {
  html: string;
  css: string;
  js: string;
  previewUrl?: string | null;
}

export function PrototypePreview({ html, css, js, previewUrl }: Props) {
  const [iframeContent, setIframeContent] = useState('');

  useEffect(() => {
    // 若html已是完整文档（含<!DOCTYPE或<html），直接使用；否则组装
    const isFullDocument = html.trim().startsWith('<!DOCTYPE') || html.trim().toLowerCase().startsWith('<html');
    const fullHtml = isFullDocument
      ? html
      : `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>原型预览</title>
  <style>
    ${css}
  </style>
</head>
<body>
  ${html}
  <script>
    ${js}
  </script>
</body>
</html>
    `;
    setIframeContent(fullHtml);
  }, [html, css, js]);

  if (!html && !previewUrl) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50 rounded-lg border-2 border-dashed">
        <div className="text-center text-gray-400">
          <div className="text-6xl mb-4">🎨</div>
          <div className="text-lg">原型预览将显示在这里</div>
          <div className="text-sm mt-2">提交需求文档后自动生成</div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white rounded-lg border overflow-hidden">
      {/* 预览工具栏 */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b">
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <div className="w-3 h-3 rounded-full bg-green-500" />
          </div>
          <span className="text-sm text-gray-600 ml-2">原型预览</span>
        </div>
        
        {previewUrl && (
          <a
            href={previewUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm px-3 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white"
          >
            在新窗口打开 ↗
          </a>
        )}
      </div>

      {/* iframe预览 */}
      <div className="flex-1 overflow-hidden">
        {previewUrl ? (
          <iframe
            src={previewUrl}
            className="w-full h-full border-0"
            title="原型预览"
            sandbox="allow-scripts allow-same-origin"
          />
        ) : (
          <iframe
            srcDoc={iframeContent}
            className="w-full h-full border-0"
            title="原型预览"
            sandbox="allow-scripts"
          />
        )}
      </div>
    </div>
  );
}
