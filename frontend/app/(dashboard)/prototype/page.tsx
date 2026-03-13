/**
 * 场景3：文档转原型
 * 完整的多智能体协作可视化页面
 */
'use client';

import { useState, useEffect } from 'react';
import { usePrototypeStore } from '@/stores/prototypeStore';
import { usePrototypeStream } from '@/hooks/usePrototypeStream';
import { AgentFlowGraph } from '@/components/agent/AgentFlowGraph';
import { StreamingLog } from '@/components/agent/StreamingLog';
import { CodePreview } from '@/components/prototype/CodePreview';
import { PrototypePreview } from '@/components/prototype/PrototypePreview';
import { RequirementInput } from '@/components/prototype/RequirementInput';
import { NodeOutputPanel } from '@/components/prototype/NodeOutputPanel';
import { Toaster, toast } from 'sonner';
import { listDocuments, getDocument } from '@/lib/api/documents';
import type { DocumentListItem } from '@/lib/api/documents';

export default function PrototypePage() {
  const {
    requirements,
    isGenerating,
    currentNode,
    progress,
    nodes,
    logs,
    generatedCode,
    previewUrl,
    setRequirements,
    startGeneration,
    updateNodeStatus,
    addLog,
    setGeneratedCode,
    setPreviewUrl,
    completeGeneration,
  } = usePrototypeStore();

  const [viewMode, setViewMode] = useState<'preview' | 'code' | 'split'>('preview');
  const [showDocPicker, setShowDocPicker] = useState(false);
  const [docList, setDocList] = useState<DocumentListItem[]>([]);
  const [docListLoading, setDocListLoading] = useState(false);

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
      setRequirements(doc.content);
      setShowDocPicker(false);
      toast.success(`已加载「${doc.title}」`);
    } catch {
      toast.error('加载文档失败');
    }
  };

  // 使用流式Hook连接后端SSE
  const { startStreaming, stopStreaming } = usePrototypeStream();

  const handleGenerate = () => {
    if (!requirements.trim()) {
      toast.error('请输入需求文档');
      return;
    }
    startStreaming(requirements);
  };

  const handleGenerateFromFile = (file: File) => {
    startStreaming('', file);
  };

  const handleStop = () => {
    stopStreaming();
    toast.warning('已停止生成');
  };

  return (
    <div className="min-h-full flex flex-col bg-gray-50">
      <Toaster position="top-right" />

      {/* 顶部标题栏 */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">文档转原型</h1>
            <p className="text-sm text-gray-500 mt-1">
              AI自动将需求文档转换为可交互的HTML原型
            </p>
          </div>

          {/* 进度条和停止按钮 */}
          {isGenerating && (
            <div className="flex items-center gap-4">
              <div className="w-64">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-gray-700">
                    生成中...
                  </span>
                  <span className="text-sm text-gray-500">{Math.round(progress)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
              <button
                onClick={handleStop}
                className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm"
              >
                停止
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 主内容区（四栏布局） */}
      <div className="flex-1 grid grid-cols-12 gap-4 p-4 min-h-0">
        {/* 左侧：输入区 */}
        <div className="col-span-3 flex flex-col gap-4">
          <RequirementInput
            value={requirements}
            onChange={setRequirements}
            onSubmit={handleGenerate}
            onSubmitWithFile={handleGenerateFromFile}
            onOpenDocumentLibrary={() => setShowDocPicker(true)}
            isLoading={isGenerating}
          />

          {showDocPicker && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowDocPicker(false)}>
              <div className="bg-white rounded-lg shadow-xl max-w-md w-full max-h-[70vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
                <div className="px-4 py-3 border-b flex items-center justify-between">
                  <h3 className="font-semibold">从文档库选择</h3>
                  <button className="text-gray-400 hover:text-gray-600" onClick={() => setShowDocPicker(false)}>✕</button>
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
                          onClick={() => handleSelectFromLibrary(d.id)}
                          className="w-full text-left px-4 py-3 rounded-lg border hover:bg-gray-50 flex justify-between items-center"
                        >
                          <span className="text-sm font-medium truncate">{d.title}</span>
                          {d.document_type && (
                            <span className="text-xs text-gray-500 shrink-0 ml-2">{d.document_type}</span>
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

        {/* 中间左：智能体流程 + 节点输出 */}
        <div className="col-span-3 flex flex-col gap-4">
          {/* 智能体流程图 */}
          <div className="h-[400px]">
            <div className="h-full flex flex-col">
              <div className="px-4 py-2 bg-white border rounded-t-lg">
                <h3 className="font-semibold text-gray-900">智能体执行流程</h3>
                <p className="text-xs text-gray-500 mt-1">
                  实时显示各节点状态
                </p>
              </div>
              <div className="flex-1 min-h-0">
                <AgentFlowGraph nodes={nodes} />
              </div>
            </div>
          </div>

          {/* 节点输出详情 */}
          <div className="flex-1 min-h-0 overflow-auto">
            <NodeOutputPanel nodes={nodes} />
          </div>
        </div>

        {/* 中间右：实时日志 */}
        <div className="col-span-2 flex flex-col">
          <StreamingLog logs={logs} maxHeight="100%" />
        </div>

        {/* 右侧：预览/代码 */}
        <div className="col-span-4 flex flex-col">
          {/* 视图切换 */}
          <div className="mb-4 flex items-center gap-2">
            {[
              { id: 'preview', label: '预览', icon: '👁️' },
              { id: 'code', label: '代码', icon: '💻' },
              { id: 'split', label: '分栏', icon: '⚡' },
            ].map((mode) => (
              <button
                key={mode.id}
                onClick={() => setViewMode(mode.id as any)}
                className={`
                  px-4 py-2 rounded-lg font-medium transition-colors
                  ${viewMode === mode.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-100'
                  }
                `}
              >
                {mode.icon} {mode.label}
              </button>
            ))}
          </div>

          {/* 内容区 */}
          <div className="flex-1 min-h-0">
            {viewMode === 'preview' && (
              <PrototypePreview
                html={generatedCode.html}
                css={generatedCode.css}
                js={generatedCode.js}
                previewUrl={previewUrl}
              />
            )}

            {viewMode === 'code' && (
              <CodePreview
                html={generatedCode.html}
                css={generatedCode.css}
                js={generatedCode.js}
                readonly={false}
                onCodeChange={(file, code) => {
                  setGeneratedCode({ ...generatedCode, [file]: code });
                }}
              />
            )}

            {viewMode === 'split' && (
              <div className="grid grid-cols-2 gap-4 h-full">
                <PrototypePreview
                  html={generatedCode.html}
                  css={generatedCode.css}
                  js={generatedCode.js}
                  previewUrl={previewUrl}
                />
                <CodePreview
                  html={generatedCode.html}
                  css={generatedCode.css}
                  js={generatedCode.js}
                  readonly={true}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
