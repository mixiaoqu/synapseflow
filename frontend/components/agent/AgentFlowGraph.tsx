/**
 * 智能体流程图组件
 * 使用 ReactFlow 显示节点执行状态
 */
'use client';

import { useCallback, useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  ConnectionLineType,
} from 'reactflow';
import { motion } from 'framer-motion';
import 'reactflow/dist/style.css';

interface AgentNode {
  id: string;
  name: string;
  model: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  duration?: number;
}

interface Props {
  nodes: AgentNode[];
}

// 自定义节点组件
function CustomNode({ data }: any) {
  const statusColors = {
    pending: 'bg-gray-100 border-gray-300 text-gray-600',
    running: 'bg-blue-50 border-blue-500 text-blue-900 shadow-lg',
    completed: 'bg-green-50 border-green-500 text-green-900',
    error: 'bg-red-50 border-red-500 text-red-900',
  };

  const statusIcons = {
    pending: '⏸️',
    running: '⏳',
    completed: '✓',
    error: '✗',
  };

  return (
    <motion.div
      className={`
        px-6 py-4 rounded-lg border-2 min-w-[200px]
        ${statusColors[data.status as keyof typeof statusColors]}
        ${data.status === 'running' ? 'animate-pulse' : ''}
      `}
      animate={
        data.status === 'running'
          ? { scale: [1, 1.05, 1] }
          : { scale: 1 }
      }
      transition={{ repeat: data.status === 'running' ? Infinity : 0, duration: 1 }}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold text-lg">{data.name}</span>
        <span className="text-2xl">{statusIcons[data.status as keyof typeof statusIcons]}</span>
      </div>
      
      <div className="text-xs text-gray-500 mb-1">
        模型: {data.model}
      </div>
      
      {data.duration && (
        <div className="text-xs font-medium">
          耗时: {data.duration.toFixed(2)}s
        </div>
      )}
      
      {data.detailedOutput && data.status === 'completed' && (
        <div className="mt-2 text-xs text-gray-600 bg-white bg-opacity-50 rounded px-2 py-1">
          {getOutputSummary(data)}
        </div>
      )}
      
      {data.status === 'running' && (
        <div className="mt-2">
          <div className="h-1 bg-gray-200 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-blue-500"
              initial={{ width: '0%' }}
              animate={{ width: '100%' }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          </div>
        </div>
      )}
    </motion.div>
  );
}

function getOutputSummary(data: any): string {
  if (!data.detailedOutput) return '';
  
  const output = data.detailedOutput;
  
  // 根据节点ID返回摘要
  if (data.id === 'extract_requirements') {
    const modules = output.functional_modules?.length || 0;
    return `${modules}个模块`;
  } else if (data.id === 'design_components') {
    const comps = output.components?.length || 0;
    return `${comps}个组件`;
  } else if (data.id.includes('generate_')) {
    const lines = output.total_lines || 0;
    return `${lines}行`;
  } else if (data.id === 'validate_preview') {
    return output.is_valid ? '✓ 验证通过' : '⚠ 有问题';
  }
  
  return '已完成';
}

const nodeTypes = {
  custom: CustomNode,
};

export function AgentFlowGraph({ nodes }: Props) {
  // 转换为ReactFlow节点格式
  const flowNodes: Node[] = useMemo(() => {
    return nodes.map((node, index) => ({
      id: node.id,
      type: 'custom',
      position: { x: 250, y: index * 150 },
      data: node,
    }));
  }, [nodes]);

  // 创建边（连接线）
  const flowEdges: Edge[] = useMemo(() => {
    return nodes.slice(0, -1).map((node, index) => ({
      id: `e${index}`,
      source: node.id,
      target: nodes[index + 1].id,
      type: ConnectionLineType.SmoothStep,
      animated: nodes[index].status === 'completed' && nodes[index + 1].status === 'running',
      style: {
        stroke: nodes[index].status === 'completed' ? '#10b981' : '#d1d5db',
        strokeWidth: 2,
      },
    }));
  }, [nodes]);

  return (
    <div className="h-full w-full bg-gray-50 rounded-lg border">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.5}
        maxZoom={1.5}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(node) => {
            const status = node.data.status;
            if (status === 'completed') return '#10b981';
            if (status === 'running') return '#3b82f6';
            if (status === 'error') return '#ef4444';
            return '#d1d5db';
          }}
          className="bg-white"
        />
      </ReactFlow>
    </div>
  );
}
