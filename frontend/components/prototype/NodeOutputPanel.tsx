/**
 * 节点输出详情面板
 * 展示每个节点处理的详细结果
 */
'use client';

import { motion, AnimatePresence } from 'framer-motion';

export interface AgentNode {
  id: string;
  name: string;
  model: string;
  status: 'pending' | 'running' | 'completed' | 'error' | string;
  duration?: number;
  output?: unknown;
  startTime?: number;
  detailedOutput?: unknown;
}

interface Props {
  nodes: (AgentNode | { id: string; name: string; model: string; status: string; detailedOutput?: unknown })[];
}

export function NodeOutputPanel({ nodes }: Props) {
  // 只显示有输出的节点
  const nodesWithOutput = nodes.filter(node => node.detailedOutput);

  if (nodesWithOutput.length === 0) {
    return (
      <div className="bg-white rounded-lg border p-8">
        <div className="text-center text-gray-400">
          <div className="text-4xl mb-2">📊</div>
          <div className="text-sm">节点输出结果将显示在这里</div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b">
        <h3 className="font-semibold text-gray-900">节点处理结果</h3>
        <p className="text-xs text-gray-500 mt-1">每个节点的详细输出数据</p>
      </div>

      <div className="max-h-[600px] overflow-y-auto">
        <AnimatePresence>
          {nodesWithOutput.map((node, idx) => (
            <motion.div
              key={node.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="border-b last:border-b-0"
            >
              <details className="group">
                <summary className="px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">
                        {node.status === 'completed' ? '✅' : '⏳'}
                      </span>
                      <div>
                        <div className="font-medium text-gray-900">{node.name}</div>
                        <div className="text-xs text-gray-500">{node.model}</div>
                      </div>
                    </div>
                    <div className="text-xs text-gray-400 group-open:rotate-180 transition-transform">
                      ▼
                    </div>
                  </div>
                </summary>

                <div className="px-4 py-4 bg-gray-50">
                  {renderNodeOutput(node)}
                </div>
              </details>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

function renderNodeOutput(node: AgentNode | { id: string; detailedOutput?: any }) {
  const output = node.detailedOutput;

  if (!output) return null;

  switch (node.id) {
    case 'prepare_requirement_chunks': {
      const ch = (output as { requirements_chunks?: unknown[] }).requirements_chunks;
      const n = Array.isArray(ch) ? ch.length : 0;
      return (
        <div className="text-sm text-gray-700 space-y-1">
          <p>已切分 <span className="font-semibold text-blue-700">{n}</span> 个章节块</p>
        </div>
      );
    }

    case 'product_design': {
      const sm = (output as { site_map?: { title?: string; route?: string }[] }).site_map;
      const mode = (output as { generation_mode?: string }).generation_mode;
      const list = Array.isArray(sm) ? sm : [];
      return (
        <div className="text-sm text-gray-700 space-y-2">
          <p>
            <span className="font-semibold text-blue-700">{list.length}</span> 页
            {mode ? (
              <span className="text-gray-500 ml-2">({mode})</span>
            ) : null}
          </p>
          <ul className="list-disc pl-4 text-xs text-gray-600 space-y-0.5">
            {list.slice(0, 12).map((p, i) => (
              <li key={i}>
                {p.title || p.route || '—'}
                {p.route ? <span className="text-gray-400 ml-1">{p.route}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      );
    }

    case 'chunk_understanding': {
      const cs = (output as { chunk_summaries?: unknown[] }).chunk_summaries;
      const n = Array.isArray(cs) ? cs.length : 0;
      return (
        <div className="text-sm text-gray-700">
          <p>
            分块语义摘要 <span className="font-semibold text-blue-700">{n}</span> 条
          </p>
        </div>
      );
    }

    case 'structure_extraction': {
      const sp = (output as { structured_spec?: { features?: unknown[] } }).structured_spec;
      const nf = sp?.features?.length ?? 0;
      return (
        <div className="text-sm text-gray-700">
          <p>
            结构化功能点 <span className="font-semibold text-blue-700">{nf}</span> 个
          </p>
        </div>
      );
    }

    case 'normalize_spec': {
      const ns = (output as { normalized_spec?: { features?: unknown[] } }).normalized_spec;
      const nf = ns?.features?.length ?? 0;
      return (
        <div className="text-sm text-gray-700">
          <p>
            归一化功能 <span className="font-semibold text-blue-700">{nf}</span> 个
          </p>
        </div>
      );
    }

    case 'interaction_design': {
      const ix = (output as { interactions?: unknown[] }).interactions;
      const n = Array.isArray(ix) ? ix.length : 0;
      return (
        <div className="text-sm text-gray-700">
          <p>
            交互条目 <span className="font-semibold text-blue-700">{n}</span> 条
          </p>
        </div>
      );
    }

    case 'generate_prototype_from_spec':
      return <CodeOutput output={output} language="HTML" />;

    case 'parse_suggestions':
      return <ParseSuggestionsOutput output={output} />;
    
    case 'analyze_document':
      return <AnalyzeDocumentOutput output={output} />;
    
    case 'locate_edits':
      return <LocateEditsOutput output={output} />;
    
    case 'revise':
      return <ReviseOutput output={output} />;
    
    default:
      return <pre className="text-xs text-gray-600 overflow-x-auto">{JSON.stringify(output, null, 2)}</pre>;
  }
}

function ParseSuggestionsOutput({ output }: { output: any }) {
  const tasks = output.parsed_tasks || [];
  return (
    <div className="space-y-2">
      <h4 className="font-semibold text-sm text-gray-700">解析任务 ({tasks.length} 条)</h4>
      {tasks.map((t: any, i: number) => (
        <div key={i} className="p-2 bg-gray-50 rounded border-l-4 border-blue-500 text-sm">
          <span className="font-medium text-blue-700">{t.action}</span> @ {t.target}: {t.content_requirement}
        </div>
      ))}
    </div>
  );
}

function AnalyzeDocumentOutput({ output }: { output: any }) {
  const chunks = output.chunks_meta || [];
  const structure = output.doc_structure || [];
  return (
    <div className="space-y-2">
      <div className="text-sm"><span className="text-gray-500">章节:</span> {structure.length} 个顶层</div>
      <div className="text-sm"><span className="text-gray-500">分块:</span> {chunks.length} 块</div>
    </div>
  );
}

function LocateEditsOutput({ output }: { output: any }) {
  const indices = output.affected_chunk_indices || [];
  const hints = output.section_hints || {};
  return (
    <div className="space-y-2">
      <div className="text-sm"><span className="text-gray-500">受影响块:</span> {indices.join(', ')}</div>
      {Object.keys(hints).length > 0 && (
        <div className="text-xs text-gray-600">{Object.keys(hints).length} 个块有修订提示</div>
      )}
    </div>
  );
}

function ReviseOutput({ output }: { output: any }) {
  const doc = output.revised_document || '';
  return (
    <div className="space-y-2">
      <div className="text-sm text-green-700 font-medium">✓ 修订完成</div>
      {doc && <pre className="text-xs text-gray-600 max-h-48 overflow-auto bg-gray-50 p-2 rounded">{doc.slice(0, 500)}{doc.length > 500 ? '...' : ''}</pre>}
    </div>
  );
}

function CodeOutput({ output, language }: { output: any; language: string }) {
  const preview = output[`${language.toLowerCase()}_preview`];
  const totalLines = output.total_lines;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">
          📝 共生成 <span className="text-blue-600">{totalLines}</span> 行代码
        </span>
      </div>

      {preview && (
        <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
          <div className="text-xs text-gray-400 mb-2">代码预览（前50行）</div>
          <pre className="text-sm text-gray-100 font-mono">
            {preview}
          </pre>
          {totalLines > 50 && (
            <div className="text-xs text-gray-500 mt-2">
              ... 还有 {totalLines - 50} 行
            </div>
          )}
        </div>
      )}
    </div>
  );
}

