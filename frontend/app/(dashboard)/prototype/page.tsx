/**
 * 场景：文档转原型 — 上传文档 + 预览
 */
'use client';

import { useState, useEffect } from 'react';
import { usePrototypeStore } from '@/stores/prototypeStore';
import { usePrototypeStream } from '@/hooks/usePrototypeStream';
import { PrototypePreview } from '@/components/prototype/PrototypePreview';
import { PrototypeGenerationProgress } from '@/components/prototype/PrototypeGenerationProgress';
import { RequirementInput } from '@/components/prototype/RequirementInput';
import { Toaster, toast } from 'sonner';
import { listDocuments, getDocument } from '@/lib/api/documents';
import type { DocumentListItem } from '@/lib/api/documents';

function slugFilename(title: string) {
  const s = title.replace(/[/\\?%*:|"<>]/g, '-').trim() || 'document';
  return s.endsWith('.md') ? s : `${s}.md`;
}

export default function PrototypePage() {
  const { isGenerating, generatedCode, previewUrl } = usePrototypeStore();

  const [docFile, setDocFile] = useState<File | null>(null);
  const [showDocPicker, setShowDocPicker] = useState(false);
  const [docList, setDocList] = useState<DocumentListItem[]>([]);
  const [docListLoading, setDocListLoading] = useState(false);

  const { startStreaming, stopStreaming } = usePrototypeStream();

  useEffect(() => {
    if (showDocPicker) {
      setDocListLoading(true);
      listDocuments({ page: 1, page_size: 50 })
        .then((d) => setDocList(d.items))
        .catch(() => toast.error('加载文档列表失败'))
        .finally(() => setDocListLoading(false));
    }
  }, [showDocPicker]);

  const handleSelectFromLibrary = async (id: number) => {
    try {
      const doc = await getDocument(id);
      const name = slugFilename(doc.title);
      const blob = new Blob([doc.content], { type: 'text/markdown;charset=utf-8' });
      const f = new File([blob], name, { type: 'text/markdown' });
      setDocFile(f);
      setShowDocPicker(false);
      toast.success(`已载入「${doc.title}」`);
    } catch {
      toast.error('加载文档失败');
    }
  };

  const handleGenerate = () => {
    if (!docFile) {
      toast.error('请先上传或选择需求文档');
      return;
    }
    startStreaming(docFile);
  };

  const handleStop = () => {
    stopStreaming();
    toast.warning('已停止生成');
  };

  return (
    <div className="min-h-full flex flex-col bg-gray-50">
      <Toaster position="top-right" />

      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">文档转原型</h1>
            <p className="text-sm text-gray-500 mt-1">
              上传需求文档，自动生成可预览的 HTML 原型
            </p>
          </div>

          {isGenerating && (
            <div className="flex items-center gap-3 shrink-0">
              <span className="text-sm font-medium text-gray-700">生成中…</span>
              <button
                type="button"
                onClick={handleStop}
                className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm"
              >
                停止
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 grid grid-cols-12 gap-4 p-4 min-h-0">
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-4 min-h-0">
          <RequirementInput
            file={docFile}
            onFileChange={setDocFile}
            onSubmit={handleGenerate}
            onOpenDocumentLibrary={() => setShowDocPicker(true)}
            isLoading={isGenerating}
          />

          <PrototypeGenerationProgress />

          <div className="bg-white rounded-lg border p-4 flex flex-col gap-2 shrink-0">
            <h3 className="font-semibold text-gray-900 text-sm">迭代修改建议</h3>
            <p className="text-xs text-gray-500 leading-relaxed">
              后续将支持在此提交修改意见，基于当前原型继续迭代优化（功能预留）。
            </p>
            <textarea
              disabled
              placeholder="例如：把主按钮改成绿色、增加页脚版权信息…"
              className="w-full min-h-[100px] text-sm p-3 rounded-lg border border-dashed border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed resize-y"
            />
          </div>
        </div>

        <div className="col-span-12 lg:col-span-8 flex flex-col min-h-0">
          <div className="flex-1 min-h-[480px] rounded-lg border bg-white overflow-hidden">
            <PrototypePreview
              html={generatedCode.html}
              css={generatedCode.css}
              js={generatedCode.js}
              previewUrl={previewUrl}
            />
          </div>
        </div>
      </div>

      {showDocPicker && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setShowDocPicker(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-md w-full max-h-[70vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-4 py-3 border-b flex items-center justify-between">
              <h3 className="font-semibold">从文档库选择</h3>
              <button
                type="button"
                className="text-gray-400 hover:text-gray-600"
                onClick={() => setShowDocPicker(false)}
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {docListLoading ? (
                <p className="text-sm text-gray-500">加载中...</p>
              ) : docList.length === 0 ? (
                <p className="text-sm text-gray-500">暂无文档，请先在文档库上传</p>
              ) : (
                <div className="space-y-2">
                  {docList.map((d) => (
                    <button
                      key={d.id}
                      type="button"
                      onClick={() => handleSelectFromLibrary(d.id)}
                      className="w-full text-left px-4 py-3 rounded-lg border hover:bg-gray-50 flex justify-between items-center"
                    >
                      <span className="text-sm font-medium truncate">{d.title}</span>
                      {d.document_type && (
                        <span className="text-xs text-gray-500 shrink-0 ml-2">
                          {d.document_type}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
