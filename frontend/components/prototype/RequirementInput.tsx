/**
 * 需求文档：仅支持上传文件或从文档库载入为文件
 */
'use client';

import { useRef } from 'react';

const SUPPORTED_EXTENSIONS = ['.txt', '.md', '.pdf', '.docx'];
const ACCEPT_FILES = '.txt,.md,.pdf,.docx';

interface Props {
  file: File | null;
  onFileChange: (file: File | null) => void;
  onSubmit: () => void;
  onOpenDocumentLibrary?: () => void;
  isLoading: boolean;
}

export function RequirementInput({
  file,
  onFileChange,
  onSubmit,
  onOpenDocumentLibrary,
  isLoading,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const ext = '.' + (f.name.split('.').pop()?.toLowerCase() || '');
    if (!SUPPORTED_EXTENSIONS.includes(ext)) return;
    onFileChange(f);
    e.target.value = '';
  };

  const clearFile = () => {
    onFileChange(null);
  };

  const canSubmit = Boolean(file) && !isLoading;

  return (
    <div className="h-full flex flex-col bg-white rounded-lg border overflow-hidden min-h-[280px]">
      <div className="px-4 py-3 bg-gray-50 border-b">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <h3 className="font-semibold text-gray-900">需求文档</h3>
          {onOpenDocumentLibrary && (
            <button
              type="button"
              onClick={onOpenDocumentLibrary}
              disabled={isLoading}
              className="text-xs px-3 py-1 rounded border border-gray-300 hover:bg-gray-100 text-gray-700 disabled:opacity-50"
            >
              📁 从文档库选择
            </button>
          )}
        </div>
        <p className="text-xs text-gray-500 mt-1">
          请上传 txt / md / pdf / docx（最大 10MB）
        </p>
      </div>

      <div className="px-4 py-4 border-b bg-gray-50/50 flex-1 flex flex-col justify-center">
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_FILES}
          onChange={handleFileChange}
          className="hidden"
        />
        <div className="flex flex-col items-stretch gap-3">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
            className="text-sm px-4 py-3 rounded-lg border-2 border-dashed border-gray-300 hover:border-blue-400 hover:bg-blue-50/50 text-gray-700 disabled:opacity-50"
          >
            📎 点击选择文件
          </button>
          {file ? (
            <div className="flex items-center justify-between text-sm text-gray-700 bg-white border rounded-lg px-3 py-2">
              <span className="truncate pr-2">{file.name}</span>
              <button
                type="button"
                onClick={clearFile}
                className="text-red-500 hover:text-red-700 shrink-0"
              >
                清除
              </button>
            </div>
          ) : (
            <p className="text-xs text-gray-400 text-center">尚未选择文件</p>
          )}
        </div>
      </div>

      <div className="px-4 py-3 bg-gray-50 border-t flex justify-end">
        <button
          onClick={onSubmit}
          disabled={!canSubmit}
          className="px-6 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" />
              生成中...
            </span>
          ) : (
            '生成原型'
          )}
        </button>
      </div>
    </div>
  );
}
