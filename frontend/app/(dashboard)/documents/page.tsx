'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  uploadDocument,
  uploadDocumentsBatch,
  listDocuments,
  getDocument,
  deleteDocument,
  deleteDocumentsBatch,
  indexDocument,
  reindexAll,
  type DocumentListItem,
  type DocumentDetail,
} from '@/lib/api/documents';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Toaster, toast } from 'sonner';

const ACCEPT_FILES = '.txt,.md,.pdf,.docx';
const SUPPORTED_EXTENSIONS = ['.txt', '.md', '.pdf', '.docx'];
const MAX_SIZE = 10 * 1024 * 1024; // 10MB

function formatDate(s: string) {
  return new Date(s).toLocaleString('zh-CN');
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function DocumentsPage() {
  const [items, setItems] = useState<DocumentListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [viewingDoc, setViewingDoc] = useState<DocumentDetail | null>(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [reindexing, setReindexing] = useState(false);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listDocuments({
        page,
        page_size: 20,
        keyword: keyword || undefined,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      toast.error('加载文档列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, keyword]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const handleSearch = () => {
    setKeyword(searchInput.trim());
    setPage(1);
  };

  const handleFile = async (file: File) => {
    const ext = '.' + (file.name.split('.').pop()?.toLowerCase() || '');
    if (!SUPPORTED_EXTENSIONS.includes(ext)) {
      toast.error(`不支持格式 ${ext}，请上传 txt/md/pdf/docx`);
      return;
    }
    if (file.size > MAX_SIZE) {
      toast.error('文件超过 10MB 限制');
      return;
    }
    setUploading(true);
    try {
      await uploadDocument(file);
      toast.success('上传成功');
      setUploadModalOpen(false);
      loadList();
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || '上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleBatchUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const validFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const ext = '.' + (f.name.split('.').pop()?.toLowerCase() || '');
      if (SUPPORTED_EXTENSIONS.includes(ext) && f.size <= MAX_SIZE) {
        validFiles.push(f);
      }
    }
    if (validFiles.length === 0) {
      toast.error('没有符合条件的文件');
      return;
    }
    setUploading(true);
    try {
      const created = await uploadDocumentsBatch(validFiles);
      toast.success(`成功上传 ${created.length} 个文档`);
      setUploadModalOpen(false);
      loadList();
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || '批量上传失败');
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const fileList = e.dataTransfer.files;
    if (fileList.length > 1) {
      handleBatchUpload(fileList);
    } else if (fileList.length === 1) {
      handleFile(fileList[0]);
    }
  };

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (fileList && fileList.length > 0) {
      if (fileList.length > 1) {
        handleBatchUpload(fileList);
      } else {
        handleFile(fileList[0]);
      }
    }
    e.target.value = '';
  };

  const handleView = async (id: number) => {
    try {
      const doc = await getDocument(id);
      setViewingDoc(doc);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '加载文档失败';
      toast.error(msg);
      if (msg.includes('不存在')) loadList(); // 404 时刷新列表
    }
  };

  const handleDelete = async (id: number, title: string) => {
    if (!confirm(`确定删除「${title}」？`)) return;
    try {
      await deleteDocument(id);
      toast.success('删除成功');
      if (viewingDoc?.id === id) setViewingDoc(null);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      loadList();
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || '删除失败');
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map((d) => d.id)));
    }
  };

  const handleReindexAll = async () => {
    setReindexing(true);
    try {
      const res = await reindexAll();
      toast.success(res.message || '向量索引重建完成');
      loadList();
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || '重建索引失败');
    } finally {
      setReindexing(false);
    }
  };

  const handleIndexOne = async (id: number) => {
    try {
      const res = await indexDocument(id);
      toast.success(res.message || '已建立向量索引');
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || '建立索引失败');
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) {
      toast.error('请先选择要删除的文档');
      return;
    }
    if (!confirm(`确定删除选中的 ${selectedIds.size} 篇文档？`)) return;
    try {
      const result = await deleteDocumentsBatch([...selectedIds]);
      toast.success(result.message || '批量删除成功');
      if (viewingDoc && selectedIds.has(viewingDoc.id)) setViewingDoc(null);
      setSelectedIds(new Set());
      loadList();
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || '批量删除失败');
    }
  };

  return (
    <div className="min-h-full flex flex-col bg-gray-50">
      <Toaster position="top-right" />

      {/* 顶部 */}
      <div className="bg-white border-b px-6 py-4 shrink-0 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">文档库</h1>
          <p className="text-sm text-gray-500 mt-1">
            上传的文档会自动写入向量数据库，供 QA 知识库检索使用
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button
            variant="outline"
            onClick={handleReindexAll}
            disabled={reindexing || total === 0}
          >
            {reindexing ? '重建中...' : '🔄 全量重建索引'}
          </Button>
          <Button onClick={() => setUploadModalOpen(true)}>
            📤 批量上传
          </Button>
        </div>
      </div>

      <div className="flex-1 flex flex-col gap-4 p-4 min-h-0">
        {/* 文档列表为主视图 */}
        <div className="flex-1 flex flex-col gap-4 min-h-0">
          {/* 搜索 */}
          <Card>
            <CardContent className="pt-4">
              <div className="flex gap-2">
                <Input
                  placeholder="搜索文档标题或内容..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  className="flex-1"
                />
                <Button onClick={handleSearch} variant="secondary">
                  搜索
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* 文档列表 */}
          <Card className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">文档列表</CardTitle>
                  <p className="text-xs text-gray-500 mt-1">共 {total} 篇</p>
                </div>
                {selectedIds.size > 0 && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleBatchDelete}
                  >
                    🗑️ 批量删除 ({selectedIds.size})
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto p-0 pl-4 pr-6 pb-4">
              {loading ? (
                <p className="text-sm text-gray-500 py-4">加载中...</p>
              ) : items.length === 0 ? (
                <p className="text-sm text-gray-500 py-4">暂无文档</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-sm min-w-[800px]">
                    <thead>
                      <tr className="border-b border-gray-200 text-xs font-medium text-gray-500">
                        <th className="w-10 py-3 pl-4 pr-2 text-left">
                          <input
                            type="checkbox"
                            checked={items.length > 0 && selectedIds.size === items.length}
                            onChange={toggleSelectAll}
                            className="rounded"
                          />
                        </th>
                        <th className="py-3 pl-3 pr-4 text-left min-w-[180px]">标题</th>
                        <th className="py-3 px-4 w-24 text-right">大小</th>
                        <th className="py-3 px-3 w-16 text-center">版本</th>
                        <th className="py-3 px-4 w-40 text-left">生成时间</th>
                        <th className="py-3 pl-4 pr-6 min-w-[280px] text-right">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((d) => (
                        <tr
                          key={d.id}
                          className="border-b border-gray-100 hover:bg-gray-50 last:border-b-0"
                        >
                          <td className="py-2.5 pl-4 pr-2">
                            <input
                              type="checkbox"
                              checked={selectedIds.has(d.id)}
                              onChange={() => toggleSelect(d.id)}
                              className="rounded"
                            />
                          </td>
                          <td className="py-2.5 pl-3 pr-4 min-w-0">
                            <p className="font-medium truncate">{d.title}</p>
                            {d.document_type && (
                              <Badge variant="secondary" className="text-xs mt-0.5">
                                {d.document_type}
                              </Badge>
                            )}
                          </td>
                          <td className="py-2.5 px-4 text-right text-gray-500 tabular-nums">
                            {formatSize(d.size ?? 0)}
                          </td>
                          <td className="py-2.5 px-3 text-center text-gray-500">
                            v{d.version ?? 1}
                          </td>
                          <td className="py-2.5 px-4 text-gray-400 tabular-nums whitespace-nowrap">
                            {formatDate(d.created_at)}
                          </td>
                          <td className="py-2.5 pl-4 pr-6 text-right">
                            <div className="flex gap-2.5 justify-end flex-nowrap">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleView(d.id)}
                              >
                                查看
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleIndexOne(d.id)}
                              >
                                重建索引
                              </Button>
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => handleDelete(d.id, d.title)}
                              >
                                删除
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 上传文档弹窗 */}
      {uploadModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => !uploading && setUploadModalOpen(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-md w-full p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">批量上传文档</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => !uploading && setUploadModalOpen(false)}
              >
                关闭
              </Button>
            </div>
            <p className="text-xs text-gray-500 mb-3">txt / md / pdf / docx，最大 10MB，支持多选</p>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              className={`
                border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
                ${dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
                ${uploading ? 'opacity-60 pointer-events-none' : ''}
              `}
              onClick={() => document.getElementById('doc-file-input')?.click()}
            >
              <input
                id="doc-file-input"
                type="file"
                accept={ACCEPT_FILES}
                multiple
                onChange={onFileSelect}
                className="hidden"
              />
              {uploading ? (
                <span className="text-gray-600">上传中...</span>
              ) : (
                <>
                  <div className="text-3xl mb-2">📄</div>
                  <p className="text-sm text-gray-600">拖拽多个文件到此处，或点击选择（支持多选）</p>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 点击查看后弹出文档预览 */}
      {viewingDoc && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setViewingDoc(null)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-4 py-3 border-b flex items-center justify-between shrink-0">
              <div>
                <h3 className="font-semibold">{viewingDoc.title}</h3>
                <p className="text-xs text-gray-500 mt-1">
                  {viewingDoc.document_type} · {formatSize(viewingDoc.size ?? 0)} · v{viewingDoc.version ?? 1} · {formatDate(viewingDoc.created_at)}
                </p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setViewingDoc(null)}>
                关闭
              </Button>
            </div>
            <div className="flex-1 overflow-auto p-4 min-h-0">
              <pre className="text-sm whitespace-pre-wrap font-mono bg-gray-50 p-4 rounded-lg">
                {viewingDoc.content}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
