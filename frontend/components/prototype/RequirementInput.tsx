/**
 * 需求文档输入组件
 */
'use client';

import { useState, useRef } from 'react';

const SUPPORTED_EXTENSIONS = ['.txt', '.md', '.pdf', '.docx'];
const ACCEPT_FILES = '.txt,.md,.pdf,.docx';

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onSubmitWithFile?: (file: File) => void;
  onOpenDocumentLibrary?: () => void;
  isLoading: boolean;
}

const exampleRequirements = `# 产品落地页需求

## 页面结构
1. 顶部导航栏
   - Logo（左侧）
   - 菜单：首页、产品、定价、关于
   - "立即开始"按钮（右侧）

2. Hero区域
   - 主标题："让AI赋能你的团队"
   - 副标题："下一代智能协作平台"
   - 两个CTA按钮：免费试用、观看演示

3. 产品特性（三栏）
   - 特性1：智能协作
   - 特性2：实时同步
   - 特性3：安全可靠

4. 底部联系表单
   - 姓名、邮箱、消息输入框
   - 提交按钮

## 设计风格
- 现代简约风格
- 蓝色系主题（#3B82F6）
- 使用Tailwind CSS
- 响应式布局`;

export function RequirementInput({
  value,
  onChange,
  onSubmit,
  onSubmitWithFile,
  onOpenDocumentLibrary,
  isLoading,
}: Props) {
  const [charCount, setCharCount] = useState(value.length);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    onChange(newValue);
    setCharCount(newValue.length);
  };

  const handleUseExample = () => {
    onChange(exampleRequirements);
    setCharCount(exampleRequirements.length);
    setSelectedFile(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const ext = '.' + (f.name.split('.').pop()?.toLowerCase() || '');
    if (!SUPPORTED_EXTENSIONS.includes(ext)) return;
    setSelectedFile(f);
    e.target.value = '';
  };

  const clearFile = () => {
    setSelectedFile(null);
    fileInputRef.current?.focus();
  };

  const handleSubmit = () => {
    if (selectedFile && onSubmitWithFile) {
      onSubmitWithFile(selectedFile);
    } else {
      onSubmit();
    }
  };

  const canSubmit = (value.trim() || selectedFile) && !isLoading && (selectedFile || charCount <= 20000);

  return (
    <div className="h-full flex flex-col bg-white rounded-lg border overflow-hidden">
      {/* 标题栏 */}
      <div className="px-4 py-3 bg-gray-50 border-b">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <h3 className="font-semibold text-gray-900">需求文档</h3>
          <div className="flex gap-2">
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
            <button
              onClick={handleUseExample}
              disabled={isLoading}
              className="text-xs px-3 py-1 rounded bg-gray-200 hover:bg-gray-300 text-gray-700 disabled:opacity-50"
            >
              使用示例
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          粘贴输入或上传文件（txt/md/pdf/docx，最大10MB）
        </p>
      </div>

      {/* 文件上传区 */}
      <div className="px-4 py-2 border-b bg-gray-50/50">
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_FILES}
          onChange={handleFileChange}
          className="hidden"
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
            className="text-xs px-3 py-1.5 rounded border border-gray-300 hover:bg-gray-100 text-gray-700 disabled:opacity-50"
          >
            📎 上传文件
          </button>
          {selectedFile ? (
            <span className="text-xs text-gray-600 flex items-center gap-2">
              {selectedFile.name}
              <button
                type="button"
                onClick={clearFile}
                className="text-red-500 hover:text-red-700"
              >
                ✕
              </button>
            </span>
          ) : null}
        </div>
      </div>

      {/* 输入区 */}
      <div className="flex-1 p-4 overflow-hidden">
        <textarea
          value={value}
          onChange={handleChange}
          disabled={isLoading}
          placeholder="粘贴或输入需求文档...

示例格式：
- 页面包含导航栏、Hero区域、特性展示
- 使用蓝色系配色
- 需要响应式布局
- 风格现代简约"
          className="w-full h-full p-4 border-2 rounded-lg resize-none focus:outline-none focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
          style={{ fontFamily: 'monospace' }}
        />
      </div>

      {/* 底部操作栏 */}
      <div className="px-4 py-3 bg-gray-50 border-t flex items-center justify-between">
        <div className="text-sm text-gray-500">
          {selectedFile ? (
            <span className="text-green-600">已选: {selectedFile.name}</span>
          ) : (
            <>
              {charCount} 字符
              {charCount > 10000 && (
                <span className="text-orange-600 ml-2">
                  ⚠️ 建议控制在10000字符以内
                </span>
              )}
            </>
          )}
        </div>

        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="px-6 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
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
