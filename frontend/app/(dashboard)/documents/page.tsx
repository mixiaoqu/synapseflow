"use client";

import { useState, useEffect, useCallback } from "react";
import {
  uploadDocument,
  uploadDocumentsBatch,
  listDocuments,
  getDocument,
  getDocumentVersions,
  deleteDocument,
  deleteDocumentsBatch,
  indexDocument,
  reindexAll,
  type DocumentListItem,
  type DocumentDetail,
  type DocumentVersionItem,
} from "@/lib/api/documents";
import { listCollections, createCollection, type CollectionWithCount } from "@/lib/api/collections";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Toaster, toast } from "sonner";

const ACCEPT_FILES = ".txt,.md,.pdf,.docx";
const SUPPORTED_EXTENSIONS = [".txt", ".md", ".pdf", ".docx"];
const MAX_SIZE = 10 * 1024 * 1024; // 10MB
const PAGE_SIZE = 20;

function formatDate(s: string) {
  return new Date(s).toLocaleString("zh-CN");
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
  const [keyword, setKeyword] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [viewingDoc, setViewingDoc] = useState<DocumentDetail | null>(null);
  const [documentVersions, setDocumentVersions] = useState<
    DocumentVersionItem[]
  >([]);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [reindexing, setReindexing] = useState(false);
  const [collections, setCollections] = useState<CollectionWithCount[]>([]);
  const [collectionFilter, setCollectionFilter] = useState<number | null | "uncategorized">(null);
  const [uploadCollectionId, setUploadCollectionId] = useState<number | null>(null);
  const [newCollectionName, setNewCollectionName] = useState("");

  const loadCollections = useCallback(async () => {
    try {
      const list = await listCollections();
      setCollections(list);
    } catch {
      /* ignore */
    }
  }, []);

  const handleCreateCollection = async () => {
    const name = newCollectionName.trim();
    if (!name) return;
    try {
      await createCollection(name);
      setNewCollectionName("");
      loadCollections();
      toast.success("集合已创建");
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || "创建失败");
    }
  };

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const cid = collectionFilter === "uncategorized" ? 0 : collectionFilter ?? undefined;
      const data = await listDocuments({
        page,
        page_size: PAGE_SIZE,
        keyword: keyword || undefined,
        collection_id: cid,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      toast.error("加载文档列表失败");
    } finally {
      setLoading(false);
    }
  }, [page, keyword, collectionFilter]);

  useEffect(() => {
    loadCollections();
  }, [loadCollections]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const handleSearch = () => {
    setKeyword(searchInput.trim());
    setPage(1);
  };

  const handleFile = async (file: File) => {
    const ext = "." + (file.name.split(".").pop()?.toLowerCase() || "");
    if (!SUPPORTED_EXTENSIONS.includes(ext)) {
      toast.error(`不支持格式 ${ext}，请上传 txt/md/pdf/docx`);
      return;
    }
    if (file.size > MAX_SIZE) {
      toast.error("文件超过 10MB 限制");
      return;
    }
    setUploading(true);
    try {
      const cid = uploadCollectionId && uploadCollectionId > 0 ? uploadCollectionId : undefined;
      await uploadDocument(file, cid);
      toast.success("上传成功");
      setUploadModalOpen(false);
      loadList();
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const handleBatchUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const validFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const ext = "." + (f.name.split(".").pop()?.toLowerCase() || "");
      if (SUPPORTED_EXTENSIONS.includes(ext) && f.size <= MAX_SIZE) {
        validFiles.push(f);
      }
    }
    if (validFiles.length === 0) {
      toast.error("没有符合条件的文件");
      return;
    }
    setUploading(true);
    try {
      const cid = uploadCollectionId && uploadCollectionId > 0 ? uploadCollectionId : undefined;
      const created = await uploadDocumentsBatch(validFiles, cid);
      toast.success(`成功上传 ${created.length} 个文档`);
      setUploadModalOpen(false);
      loadList();
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || "批量上传失败");
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
    e.target.value = "";
  };

  const handleView = async (id: number) => {
    try {
      const [doc, versionsRes] = await Promise.all([
        getDocument(id),
        getDocumentVersions(id).catch(() => []),
      ]);
      setViewingDoc(doc);
      setDocumentVersions(versionsRes);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "加载文档失败";
      toast.error(msg);
      if (msg.includes("不存在")) loadList(); // 404 时刷新列表
    }
  };

  const handleSwitchVersion = async (versionId: number) => {
    if (versionId === viewingDoc?.id) return;
    try {
      const doc = await getDocument(versionId);
      setViewingDoc(doc);
    } catch (e) {
      toast.error("加载版本失败");
    }
  };

  const handleDelete = async (id: number, title: string) => {
    if (!confirm(`确定删除「${title}」？`)) return;
    try {
      await deleteDocument(id);
      toast.success("删除成功");
      if (viewingDoc?.id === id) setViewingDoc(null);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      loadList();
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || "删除失败");
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
      toast.success(res.message || "向量索引重建完成");
      loadList();
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || "重建索引失败");
    } finally {
      setReindexing(false);
    }
  };

  const handleIndexOne = async (id: number) => {
    try {
      const res = await indexDocument(id);
      toast.success(res.message || "已建立向量索引");
      loadList();
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || "建立索引失败");
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) {
      toast.error("请先选择要删除的文档");
      return;
    }
    if (!confirm(`确定删除选中的 ${selectedIds.size} 篇文档？`)) return;
    try {
      const result = await deleteDocumentsBatch([...selectedIds]);
      toast.success(result.message || "批量删除成功");
      if (viewingDoc && selectedIds.has(viewingDoc.id)) setViewingDoc(null);
      setSelectedIds(new Set());
      loadList();
    } catch (e: unknown) {
      const err = e as { message?: string };
      toast.error(err.message || "批量删除失败");
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
            {reindexing ? "重建中..." : "🔄 全量重建索引"}
          </Button>
          <Button onClick={() => setUploadModalOpen(true)}>📤 批量上传</Button>
        </div>
      </div>

      <div className="flex-1 flex flex-col gap-6 p-6 min-h-0">
        <div className="flex-1 flex flex-col gap-6 min-h-0">
          {/* 搜索与文档列表 */}
          <Card className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <CardHeader className="space-y-4 pb-2">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <CardTitle className="text-lg">文档列表</CardTitle>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex items-center gap-2">
                  <select
                    value={collectionFilter === null ? "all" : collectionFilter === "uncategorized" ? "0" : String(collectionFilter)}
                    onChange={(e) => {
                      const v = e.target.value;
                      setCollectionFilter(v === "all" ? null : v === "0" ? "uncategorized" : Number(v));
                      setPage(1);
                    }}
                    className="h-9 border rounded px-2 text-sm min-w-[100px]"
                  >
                    <option value="all">全部集合</option>
                    <option value="0">未分类</option>
                    {collections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.document_count})
                      </option>
                    ))}
                  </select>
                  <div className="flex items-center gap-1">
                    <Input
                      placeholder="新建集合名"
                      value={newCollectionName}
                      onChange={(e) => setNewCollectionName(e.target.value)}
                      className="h-9 w-28 text-sm"
                      onKeyDown={(e) => e.key === "Enter" && handleCreateCollection()}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCreateCollection}
                      disabled={!newCollectionName.trim()}
                      className="h-9 shrink-0"
                    >
                      新建
                    </Button>
                  </div>
                  </div>
                  <div className="flex flex-1 sm:flex-initial min-w-[200px] sm:min-w-[280px]">
                    <Input
                      placeholder="按标题搜索..."
                      value={searchInput}
                      onChange={(e) => setSearchInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                      className="h-9"
                    />
                  </div>
                  <Button
                    onClick={handleSearch}
                    variant="secondary"
                    size="sm"
                    className="shrink-0"
                  >
                    搜索
                  </Button>
                  {selectedIds.size > 0 && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={handleBatchDelete}
                      className="shrink-0"
                    >
                      批量删除 ({selectedIds.size})
                    </Button>
                  )}
                </div>
              </div>
              <p className="text-sm text-gray-500">共 {total} 篇文档</p>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto px-6 pb-6 pt-0">
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
                            checked={
                              items.length > 0 &&
                              selectedIds.size === items.length
                            }
                            onChange={toggleSelectAll}
                            className="rounded"
                          />
                        </th>
                        <th className="py-3 pl-3 pr-4 text-left min-w-[180px]">
                          标题
                        </th>
                        <th className="py-3 px-4 w-24 text-right">大小</th>
                        <th className="py-3 px-3 w-16 text-center">版本</th>
                        <th className="py-3 px-3 w-16 text-center">索引</th>
                        <th className="py-3 px-3 w-24 text-left">集合</th>
                        <th className="py-3 px-4 w-40 text-left">生成时间</th>
                        <th className="py-3 pl-4 pr-6 min-w-[280px] text-right">
                          操作
                        </th>
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
                              <Badge
                                variant="secondary"
                                className="text-xs mt-0.5"
                              >
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
                          <td className="py-2.5 px-4 text-center">
                            {d.indexed ? (
                              <Badge
                                variant="secondary"
                                className="bg-emerald-50 text-emerald-700 border-0 font-normal hover:bg-emerald-50"
                              >
                                已索引
                              </Badge>
                            ) : (
                              <Badge
                                variant="outline"
                                className="border-amber-200 bg-amber-50 text-amber-700 font-normal hover:bg-amber-50 hover:border-amber-200"
                              >
                                未索引
                              </Badge>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-gray-500 text-xs">
                            {d.collection_name ?? "未分类"}
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
              {total > PAGE_SIZE && !loading && (
                <div className="flex items-center justify-between border-t pt-4 mt-4">
                  <span className="text-sm text-gray-500">
                    共 {total} 篇，第 {page} /{" "}
                    {Math.max(1, Math.ceil(total / PAGE_SIZE))} 页
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      上一页
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= Math.ceil(total / PAGE_SIZE)}
                      onClick={() =>
                        setPage((p) =>
                          Math.min(Math.ceil(total / PAGE_SIZE), p + 1),
                        )
                      }
                    >
                      下一页
                    </Button>
                  </div>
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
            <div className="mb-3 flex items-center gap-2">
              <label className="text-sm text-gray-600">上传到集合：</label>
              <select
                value={uploadCollectionId ?? ""}
                onChange={(e) => setUploadCollectionId(e.target.value ? Number(e.target.value) : null)}
                className="h-9 border rounded px-2 text-sm flex-1"
              >
                <option value="">未分类</option>
                {collections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <p className="text-xs text-gray-500 mb-3">
              txt / md / pdf / docx，最大 10MB，支持多选
            </p>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              className={`
                border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
                ${dragOver ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-gray-400"}
                ${uploading ? "opacity-60 pointer-events-none" : ""}
              `}
              onClick={() => document.getElementById("doc-file-input")?.click()}
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
                  <p className="text-sm text-gray-600">
                    拖拽多个文件到此处，或点击选择（支持多选）
                  </p>
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
          onClick={() => {
            setViewingDoc(null);
            setDocumentVersions([]);
          }}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 py-4 border-b flex items-center justify-between shrink-0">
              <div>
                <h3 className="font-semibold">{viewingDoc.title}</h3>
                <p className="text-xs text-gray-500 mt-1">
                  {viewingDoc.document_type} ·{" "}
                  {formatSize(viewingDoc.size ?? 0)} · v
                  {viewingDoc.version ?? 1} ·{" "}
                  {formatDate(viewingDoc.created_at)}
                </p>
                {documentVersions && documentVersions.length > 1 && (
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs text-gray-500">版本：</span>
                    <select
                      value={viewingDoc.id}
                      onChange={(e) =>
                        handleSwitchVersion(Number(e.target.value))
                      }
                      className="h-7 text-xs border rounded px-2 py-1 bg-white min-w-[120px]"
                    >
                      {documentVersions.map((v) => (
                        <option key={v.id} value={v.id}>
                          v{v.version}
                          {v.is_latest ? " (最新)" : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setViewingDoc(null);
                  setDocumentVersions([]);
                }}
              >
                关闭
              </Button>
            </div>
            <div className="flex-1 overflow-auto p-6 min-h-0">
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
