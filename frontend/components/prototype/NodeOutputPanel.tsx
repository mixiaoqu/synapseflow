/**
 * 节点输出详情面板
 * 展示每个节点处理的详细结果
 */
'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { AgentNode } from '@/stores/prototypeStore';

interface Props {
  nodes: AgentNode[];
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

function renderNodeOutput(node: AgentNode) {
  const output = node.detailedOutput;

  if (!output) return null;

  switch (node.id) {
    case 'extract_requirements':
      return <ExtractRequirementsOutput output={output} />;
    
    case 'design_components':
      return <DesignComponentsOutput output={output} />;
    
    case 'generate_html':
      return <CodeOutput output={output} language="HTML" />;
    
    case 'generate_css':
      return <CodeOutput output={output} language="CSS" />;
    
    case 'generate_js':
      return <CodeOutput output={output} language="JavaScript" />;
    
    case 'validate_preview':
      return <ValidateOutput output={output} />;
    
    default:
      return <pre className="text-xs text-gray-600 overflow-x-auto">{JSON.stringify(output, null, 2)}</pre>;
  }
}

function ExtractRequirementsOutput({ output }: { output: any }) {
  return (
    <div className="space-y-4">
      {/* 页面信息 */}
      {output.page_info && (
        <div className="bg-white rounded-lg p-4 border">
          <h4 className="font-semibold text-sm text-gray-700 mb-2">📄 页面信息</h4>
          <div className="space-y-1 text-sm">
            <div><span className="text-gray-500">标题:</span> {output.page_info.title}</div>
            <div><span className="text-gray-500">类型:</span> <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">{output.page_info.type}</span></div>
            <div><span className="text-gray-500">描述:</span> {output.page_info.description}</div>
          </div>
        </div>
      )}

      {/* 功能模块 */}
      {output.functional_modules && output.functional_modules.length > 0 && (
        <div className="bg-white rounded-lg p-4 border">
          <h4 className="font-semibold text-sm text-gray-700 mb-2">🧩 功能模块 ({output.functional_modules.length})</h4>
          <div className="space-y-2">
            {output.functional_modules.map((module: any, idx: number) => (
              <div key={idx} className="p-3 bg-gray-50 rounded border-l-4 border-blue-500">
                <div className="font-medium text-sm text-gray-900">{module.name}</div>
                <div className="text-xs text-gray-500 mt-1">{module.description}</div>
                {module.components && module.components.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {module.components.map((comp: string, i: number) => (
                      <span key={i} className="px-2 py-1 bg-white rounded text-xs border">
                        {comp}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 交互行为 */}
      {output.interactions && output.interactions.length > 0 && (
        <div className="bg-white rounded-lg p-4 border">
          <h4 className="font-semibold text-sm text-gray-700 mb-2">⚡ 交互行为 ({output.interactions.length})</h4>
          <div className="space-y-2">
            {output.interactions.map((inter: any, idx: number) => (
              <div key={idx} className="text-sm p-2 bg-purple-50 rounded">
                <span className="text-purple-700 font-medium">{inter.trigger}</span>
                <span className="text-gray-500 mx-2">→</span>
                <span className="text-gray-900">{inter.action}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 数据模型 */}
      {output.data_model && output.data_model.length > 0 && (
        <div className="bg-white rounded-lg p-4 border">
          <h4 className="font-semibold text-sm text-gray-700 mb-2">💾 数据模型 ({output.data_model.length})</h4>
          <div className="space-y-3">
            {output.data_model.map((model: any, idx: number) => (
              <div key={idx} className="border rounded-lg overflow-hidden">
                <div className="bg-gray-100 px-3 py-2 font-medium text-sm">
                  {model.entity}
                </div>
                <div className="p-3 space-y-1">
                  {model.fields && model.fields.map((field: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className="font-mono text-blue-600">{field.name}</span>
                      <span className="text-gray-400">:</span>
                      <span className="text-gray-600">{field.type}</span>
                      {field.required && <span className="text-red-500">*</span>}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 视觉风格 */}
      {output.visual_style && (
        <div className="bg-white rounded-lg p-4 border">
          <h4 className="font-semibold text-sm text-gray-700 mb-2">🎨 视觉风格</h4>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="text-gray-500">主题:</span> {output.visual_style.theme}</div>
            <div><span className="text-gray-500">配色:</span> {output.visual_style.color_scheme}</div>
            <div><span className="text-gray-500">主色:</span> 
              <span className="ml-2 inline-block w-4 h-4 rounded border" 
                    style={{ backgroundColor: output.visual_style.primary_color }}></span>
              <span className="ml-1 font-mono text-xs">{output.visual_style.primary_color}</span>
            </div>
            <div><span className="text-gray-500">布局:</span> {output.visual_style.layout}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function DesignComponentsOutput({ output }: { output: any }) {
  return (
    <div className="space-y-4">
      {/* 组件列表 */}
      {output.components && output.components.length > 0 && (
        <div className="bg-white rounded-lg p-4 border">
          <h4 className="font-semibold text-sm text-gray-700 mb-2">
            🎨 UI组件 ({output.components.length})
          </h4>
          <pre className="text-xs text-gray-600 overflow-x-auto bg-gray-50 p-3 rounded">
            {JSON.stringify(output.components, null, 2)}
          </pre>
        </div>
      )}

      {/* 设计系统 */}
      {output.design_system && (
        <div className="bg-white rounded-lg p-4 border">
          <h4 className="font-semibold text-sm text-gray-700 mb-2">🎨 设计系统</h4>
          <div className="space-y-3">
            {output.design_system.colors && (
              <div>
                <div className="text-xs font-medium text-gray-500 mb-1">颜色</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(output.design_system.colors).map(([key, value]: [string, any]) => (
                    <div key={key} className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded border">
                      <div className="w-6 h-6 rounded border" style={{ backgroundColor: value }}></div>
                      <div>
                        <div className="text-xs font-medium">{key}</div>
                        <div className="text-xs text-gray-500 font-mono">{value}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {output.design_system.typography && (
              <div>
                <div className="text-xs font-medium text-gray-500 mb-1">字体</div>
                <pre className="text-xs text-gray-600 bg-gray-50 p-2 rounded">
                  {JSON.stringify(output.design_system.typography, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
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

function ValidateOutput({ output }: { output: any }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {output.is_valid ? (
          <>
            <span className="text-2xl">✅</span>
            <span className="text-sm font-medium text-green-700">验证通过</span>
          </>
        ) : (
          <>
            <span className="text-2xl">⚠️</span>
            <span className="text-sm font-medium text-orange-700">发现问题</span>
          </>
        )}
      </div>

      {output.preview_url && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">预览地址</div>
          <a
            href={output.preview_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:underline font-mono"
          >
            {output.preview_url}
          </a>
        </div>
      )}

      {output.validation_errors && output.validation_errors.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <div className="text-sm font-medium text-red-700 mb-2">
            验证错误 ({output.validation_errors.length})
          </div>
          <ul className="space-y-1">
            {output.validation_errors.map((error: string, idx: number) => (
              <li key={idx} className="text-xs text-red-600">
                • {error}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
