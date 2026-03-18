'use client';

import { useState, useRef } from 'react';
import dynamic from 'next/dynamic';
import { Toaster, toast } from 'sonner';
import {
  listDocuments,
  getDocument,
  uploadDocument,
  replaceDocumentContent,
  createDocumentVersion,
  createDocumentFromContent,
  type DocumentListItem,
  type DocumentDetail,
} from '@/lib/api/documents';
import { suggestRevision } from '@/lib/api/revision';

const DiffEditor = dynamic(
  () =>
    import('@monaco-editor/react').then((mod) => ({ default: mod.DiffEditor })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[400px] flex items-center justify-center bg-gray-100 rounded-lg">
        <span className="text-gray-500">加载 Diff 编辑器...</span>
      </div>
    ),
  }
);

export default function RevisionPage() {
  const [originalDoc, setOriginalDoc] = useState('');
  const [currentDoc, setCurrentDoc] = useState('');
  const [suggestions, setSuggestions] = useState('');
  const [docId, setDocId] = useState<number | null>(null);
  const [docTitle, setDocTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [round, setRound] = useState(0);
  const [confirmed, setConfirmed] = useState(false);
  const [saveMode, setSaveMode] = useState<'replace' | 'newversion'>('replace');
  const [saving, setSaving] = useState(false);
  const [showDocPicker, setShowDocPicker] = useState(false);
  const [showPasteModal, setShowPasteModal] = useState(false);
  const [pasteTitle, setPasteTitle] = useState('');
  const [pasteContent, setPasteContent] = useState('');
  const [newDocTitle, setNewDocTitle] = useState('');
  const [docList, setDocList] = useState<DocumentListItem[]>([]);
  const [docListLoading, setDocListLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocList = async () => {
    setDocListLoading(true);
    try {
      const res = await listDocuments({ page: 1, page_size: 50 });
      setDocList(res.items);
    } catch {
      toast.error('加载文档列表失败');
    } finally {
      setDocListLoading(false);
    }
  };

  const handleSelectFromLibrary = async (id: number) => {
    try {
      const doc = await getDocument(id);
      setOriginalDoc(doc.content);
      setCurrentDoc(doc.content);
      setDocId(doc.id);
      setDocTitle(doc.title);
      setRound(0);
      setConfirmed(false);
      setShowDocPicker(false);
      toast.success(`已加载「${doc.title}」`);
    } catch {
      toast.error('加载文档失败');
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const doc = await uploadDocument(file);
      setOriginalDoc(doc.content);
      setCurrentDoc(doc.content);
      setDocId(doc.id);
      setDocTitle(doc.title);
      setRound(0);
      setConfirmed(false);
      toast.success(`已上传「${doc.title}」`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '上传失败');
    }
    e.target.value = '';
  };

  const handleStartRevision = async () => {
    if (!currentDoc.trim()) {
      toast.error('请先选择或上传文档');
      return;
    }
    if (!suggestions.trim()) {
      toast.error('请输入修订建议');
      return;
    }
    setLoading(true);
    try {
      const res = await suggestRevision({
        document: currentDoc,
        suggestions,
        doc_id: docId ?? undefined,
      });
      setCurrentDoc(res.revised_document);
      setRound((r) => r + 1);
      toast.success('修订完成');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '修订失败');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = () => {
    setConfirmed(true);
  };

  const handlePasteConfirm = () => {
    if (!pasteContent.trim()) {
      toast.error('请粘贴文档内容');
      return;
    }
    const title = (pasteTitle || '').trim() || '未命名文档';
    setOriginalDoc(pasteContent);
    setCurrentDoc(pasteContent);
    setDocId(null);
    setDocTitle(title);
    setNewDocTitle(title);
    setRound(0);
    setConfirmed(false);
    setShowPasteModal(false);
    setPasteTitle('');
    setPasteContent('');
    toast.success('已加载粘贴内容');
  };

  const handleSaveAsNewDocument = async () => {
    const title = (newDocTitle || docTitle || '').trim() || '未命名文档';
    if (!currentDoc.trim()) return;
    setSaving(true);
    try {
      const doc = await createDocumentFromContent({ title, content: currentDoc });
      setDocId(doc.id);
      setDocTitle(doc.title);
      setNewDocTitle(doc.title);
      toast.success('已保存到知识库');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    if (!docId) return;
    if (!currentDoc.trim()) return;
    setSaving(true);
    try {
      if (saveMode === 'replace') {
        await replaceDocumentContent(docId, currentDoc);
        toast.success('已替换原文档');
      } else {
        await createDocumentVersion(docId, currentDoc);
        toast.success('已保存为新版本');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const hasDoc = originalDoc.trim().length > 0;
  const hasRevised = currentDoc !== originalDoc && currentDoc.length > 0;
  const showDiff = hasDoc && (hasRevised || round > 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <Toaster position="top-right" />
      <div className="max-w-7xl mx-auto p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">文档修订</h1>
        <p className="text-sm text-gray-500 mb-6">
          选择或上传文档，输入修订建议，支持多轮修订与差异对比
        </p>

        <div className="flex gap-4 mb-6">
          <button
            type="button"
            onClick={() => {
              setShowDocPicker(true);
              loadDocList();
            }}
            className="px-4 py-2 rounded-lg bg-white border border-gray-300 hover:bg-gray-50 text-gray-700"
          >
            从文档库选择
          </button>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="px-4 py-2 rounded-lg bg-white border border-gray-300 hover:bg-gray-50 text-gray-700"
          >
            上传文档
          </button>
          <button
            type="button"
            onClick={() => {
              setPasteTitle('');
              setPasteContent('');
              setShowPasteModal(true);
            }}
            className="px-4 py-2 rounded-lg bg-white border border-gray-300 hover:bg-gray-50 text-gray-700"
          >
            粘贴文档
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.pdf,.docx"
            className="hidden"
            onChange={handleUpload}
          />
          {docTitle && (
            <span className="px-4 py-2 text-sm text-gray-600 flex items-center">
              当前文档：{docTitle}
            </span>
          )}
        </div>

        {/* 建议输入 */}
        <div className="bg-white rounded-lg border p-4 mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            修订建议（必填）
          </label>
          <textarea
            value={suggestions}
            onChange={(e) => setSuggestions(e.target.value)}
            placeholder="例如：补充第三章的案例分析；将第二段改得更简洁；添加安全相关章节"
            className="w-full p-3 border rounded-lg min-h-[100px] text-sm font-mono"
          />
          <div className="mt-3 flex justify-between items-center">
            <span className="text-xs text-gray-500">
              {round > 0 ? `第 ${round} 轮修订完成` : '输入建议后点击开始修订'}
            </span>
            <button
              type="button"
              onClick={handleStartRevision}
              disabled={loading || !hasDoc || !suggestions.trim()}
              className="px-6 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white"
            >
              {loading ? '修订中...' : round > 0 ? '继续修订' : '开始修订'}
            </button>
          </div>
        </div>

        {/* Diff 对比 */}
        {showDiff && (
          <div className="bg-white rounded-lg border p-4 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">差异对比</h2>
            <div className="h-[500px] rounded-lg overflow-hidden border">
              <DiffEditor
                original={originalDoc}
                modified={currentDoc}
                language="markdown"
                options={{
                  readOnly: true,
                  renderSideBySide: true,
                  minimap: { enabled: false },
                  fontSize: 13,
                }}
              />
            </div>

            {/* 操作区 */}
            <div className="mt-4 flex gap-3">
              {!confirmed ? (
                <button
                  type="button"
                  onClick={handleConfirm}
                  className="px-6 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white"
                >
                  确认无误
                </button>
              ) : (
                <>
                  {docId ? (
                    <div className="flex items-center gap-4">
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          checked={saveMode === 'replace'}
                          onChange={() => setSaveMode('replace')}
                        />
                        <span className="text-sm">替换原文档</span>
                      </label>
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          checked={saveMode === 'newversion'}
                          onChange={() => setSaveMode('newversion')}
                        />
                        <span className="text-sm">作为新版本保存</span>
                      </label>
                      <button
                        type="button"
                        onClick={handleSave}
                        disabled={saving}
                        className="px-6 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white"
                      >
                        {saving ? '保存中...' : '保存到知识库'}
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-4">
                      <label className="text-sm text-gray-700 shrink-0">文档标题：</label>
                      <input
                        type="text"
                        value={newDocTitle || docTitle || '未命名文档'}
                        onChange={(e) => setNewDocTitle(e.target.value)}
                        placeholder="未命名文档"
                        className="px-3 py-1.5 border rounded-lg text-sm w-48"
                      />
                      <button
                        type="button"
                        onClick={handleSaveAsNewDocument}
                        disabled={saving}
                        className="px-6 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white"
                      >
                        {saving ? '保存中...' : '保存到知识库'}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}

        {/* 粘贴文档弹窗 */}
        {showPasteModal && (
          <div
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setShowPasteModal(false)}
          >
            <div
              className="bg-white rounded-xl shadow-xl max-w-xl w-full max-h-[80vh] flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="px-4 py-3 border-b flex items-center justify-between">
                <h3 className="font-semibold">粘贴文档</h3>
                <button
                  type="button"
                  className="text-gray-400 hover:text-gray-600"
                  onClick={() => setShowPasteModal(false)}
                >
                  ✕
                </button>
              </div>
              <div className="flex-1 overflow-auto p-4 space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">标题（可选）</label>
                  <input
                    type="text"
                    value={pasteTitle}
                    onChange={(e) => setPasteTitle(e.target.value)}
                    placeholder="未命名文档"
                    className="w-full px-3 py-2 border rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">文档内容</label>
                  <textarea
                    value={pasteContent}
                    onChange={(e) => setPasteContent(e.target.value)}
                    placeholder="在此粘贴文档内容..."
                    className="w-full px-3 py-2 border rounded-lg text-sm min-h-[200px] font-mono"
                  />
                </div>
                <button
                  type="button"
                  onClick={handlePasteConfirm}
                  className="w-full px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white"
                >
                  确定
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 文档选择弹窗 */}
        {showDocPicker && (
          <div
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setShowDocPicker(false)}
          >
            <div
              className="bg-white rounded-xl shadow-xl max-w-md w-full max-h-[70vh] flex flex-col"
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
                  <p className="text-sm text-gray-500">暂无文档，请先上传</p>
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
    </div>
  );
}
