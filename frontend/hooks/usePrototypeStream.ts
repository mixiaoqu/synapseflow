/**
 * 原型生成流式Hook
 * 使用fetch + ReadableStream接收SSE（支持POST请求）
 */
import { useEffect, useRef } from 'react';
import { usePrototypeStore } from '@/stores/prototypeStore';
import { toast } from 'sonner';

export function usePrototypeStream() {
  const abortControllerRef = useRef<AbortController | null>(null);
  const {
    startGeneration,
    updateNodeStatus,
    addLog,
    setGeneratedCode,
    setPreviewUrl,
    completeGeneration,
  } = usePrototypeStore();

  const startStreaming = async (requirements: string, file?: File) => {
    const mode = file ? 'file' : 'text';
    console.log('[startStreaming] 开始流式生成，模式:', mode);
    
    // 取消旧请求
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // 创建新的AbortController
    abortControllerRef.current = new AbortController();

    // 重置状态
    startGeneration();
    addLog({ node: 'System', type: 'info', content: '正在连接服务器...' });

    try {
      const url = file
        ? 'http://localhost:8000/api/v1/prototype/generate/stream/file'
        : 'http://localhost:8000/api/v1/prototype/generate/stream';
      
      const init: RequestInit = {
        method: 'POST',
        signal: abortControllerRef.current.signal,
      };
      
      if (file) {
        const formData = new FormData();
        formData.append('file', file);
        init.body = formData;
      } else {
        init.headers = { 'Content-Type': 'application/json' };
        init.body = JSON.stringify({ requirements });
      }
      
      const response = await fetch(url, init);
      
      console.log('[startStreaming] fetch返回，状态:', response.status, response.statusText);

      if (!response.ok) {
        console.error('[startStreaming] 响应失败:', response.status);
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      console.log('[startStreaming] 响应OK，开始处理流');
      addLog({ node: 'System', type: 'success', content: '✓ 已连接到服务器' });

      // 读取流式响应
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (!reader) {
        throw new Error('无法获取响应流');
      }

      while (true) {
        const { done, value } = await reader.read();
        console.log('[Stream] 收到数据块，done:', done, 'value长度:', value?.length);

        if (done) {
          console.log('[Stream] 流结束');
          break;
        }

        // 解码数据
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        console.log('[Stream] 解码后的chunk:', chunk.substring(0, 200));
        console.log('[Stream] 当前buffer长度:', buffer.length);

        // 处理完整的SSE消息
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || ''; // 保留不完整的消息
        console.log('[Stream] 分割后的消息数:', lines.length, '剩余buffer长度:', buffer.length);

        for (const line of lines) {
          if (!line.trim()) continue;
          
          console.log('[Stream] 处理消息行:', line.substring(0, 100));

          // 解析SSE格式: event: xxx\ndata: xxx
          const eventMatch = line.match(/event:\s*(\w+)\ndata:\s*(.+)/s);
          if (!eventMatch) {
            console.warn('[Stream] 无法解析SSE消息:', line.substring(0, 100));
            continue;
          }

          const eventType = eventMatch[1];
          const eventData = JSON.parse(eventMatch[2]);
          console.log('[Stream] 解析成功，事件类型:', eventType);

          // 处理不同事件类型
          handleSSEEvent(eventType, eventData);
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        addLog({ node: 'System', type: 'warning', content: '生成已取消' });
      } else {
        console.error('流式请求错误:', error);
        addLog({
          node: 'System',
          type: 'error',
          content: `连接失败: ${error.message}`,
        });
        toast.error('生成失败，请重试');
        completeGeneration();
      }
    }
  };

  const handleSSEEvent = (eventType: string, data: any) => {
    console.log('[SSE事件]', eventType, data);
    
    switch (eventType) {
      case 'start':
        addLog({ node: 'System', type: 'info', content: data.message });
        break;

      case 'node_start':
        updateNodeStatus(data.node_id, {
          status: 'running',
          model: data.model,
        });
        break;

      case 'node_output':
        console.log('[node_output事件]', {
          node_id: data.node_id,
          node_name: data.node_name,
          output_keys: Object.keys(data.output || {})
        });
        
        updateNodeStatus(data.node_id, {
          detailedOutput: data.output,
        });
        
        // 根据节点类型生成友好的日志消息
        let outputSummary = '';
        if (data.node_id === 'extract_requirements') {
          const modules = data.output.functional_modules?.length || 0;
          const interactions = data.output.interactions?.length || 0;
          const models = data.output.data_model?.length || 0;
          outputSummary = `提取到: ${modules}个模块, ${interactions}个交互, ${models}个数据模型`;
        } else if (data.node_id === 'design_components') {
          const compCount = data.output.components?.length || 0;
          outputSummary = `设计了${compCount}个组件及设计系统`;
        } else if (data.node_id.includes('generate_')) {
          const lines = data.output.total_lines || 0;
          outputSummary = `生成 ${lines} 行代码`;
        } else if (data.node_id === 'validate_preview') {
          outputSummary = data.output.is_valid ? '验证通过' : `${data.output.validation_errors?.length || 0}个问题`;
        } else {
          outputSummary = JSON.stringify(data.output).substring(0, 80);
        }
        
        addLog({
          node: data.node_name,
          type: 'info',
          content: `📊 ${outputSummary}`,
        });
        break;

      case 'log':
        addLog({
          node: data.node,
          type: data.type,
          content: data.content,
        });
        break;

      case 'node_complete':
        updateNodeStatus(data.node_id, {
          status: 'completed',
          duration: data.duration,
        });
        break;

      case 'complete':
        setGeneratedCode({
          html: data.html,
          css: data.css,
          js: data.js,
        });
        setPreviewUrl(data.preview_url);
        completeGeneration();
        
        addLog({
          node: 'System',
          type: 'success',
          content: `✓ 原型生成完成！总耗时: ${data.total_duration}s`,
        });
        
        toast.success(`原型生成完成！耗时 ${data.total_duration}s`);
        break;

      case 'error':
        addLog({
          node: 'System',
          type: 'error',
          content: `错误: ${data.message}`,
        });
        toast.error(`生成失败: ${data.message}`);
        completeGeneration();
        break;
    }
  };

  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      addLog({ node: 'System', type: 'warning', content: '已手动停止生成' });
    }
  };

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    startStreaming,
    stopStreaming,
  };
}
