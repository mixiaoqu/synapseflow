"""
原型生成流式API
使用SSE (Server-Sent Events) 实时推送智能体状态到前端
支持详细的节点输出展示
"""
import json
import time
import asyncio
from typing import AsyncGenerator, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from app.models.schemas.prototype import PrototypeRequest
from app.agents.graphs import create_doc_to_prototype_graph
from app.core.file_parser import extract_text_from_file

router = APIRouter()


async def prototype_event_generator(
    requirements: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    生成SSE事件流
    
    事件类型：
    - node_start: 节点开始执行
    - node_output: 节点输出数据（可能多次）
    - node_complete: 节点执行完成
    - log: 日志消息
    - error: 错误消息
    - complete: 整个流程完成
    """
    
    print("[Generator] prototype_event_generator 开始执行")
    print(f"[Generator] 需求文档长度: {len(requirements)}")
    
    try:
        # 创建LangGraph实例
        print("[Generator] 创建LangGraph实例")
        graph = create_doc_to_prototype_graph()
        print("[Generator] LangGraph实例创建完成")
        
        # 初始状态
        initial_state = {
            "requirements_doc": requirements,
            "extracted_requirements": {},
            "ui_components": [],
            "design_system": {},
            "generated_html": "",
            "validation_errors": [],
            "preview_url": "",
            "is_valid": False,
            "metadata": {}
        }
        
        # 发送开始事件
        print("[Generator] 发送start事件")
        yield {
            "event": "start",
            "data": {
                "message": "开始生成原型",
                "timestamp": time.time()
            }
        }
        print("[Generator] start事件已yield")
        
        # 节点名称映射（更友好的中文名）
        node_names = {
            "extract_requirements": "提取需求",
            "design_components": "设计组件",
            "generate_html": "生成HTML",
            "validate_preview": "代码验证"
        }
        
        # 节点使用的模型映射
        node_models = {
            "extract_requirements": "Kimi-长文本理解",
            "design_components": "Deepseek-设计决策",
            "generate_html": "Deepseek-代码生成",
            "validate_preview": "Deepseek-代码验证"
        }
        
        # 记录每个节点的开始时间
        node_start_times = {}
        
        # 流式执行LangGraph
        print("[Generator] 开始流式执行LangGraph")
        async for chunk in graph.astream(initial_state):
            # chunk格式: {节点名: 状态数据}
            print(f"[Generator] 收到chunk: {list(chunk.keys())}")
            
            for node_id, node_state in chunk.items():
                node_name = node_names.get(node_id, node_id)
                node_model = node_models.get(node_id, "Unknown")
                
                print(f"[DEBUG] 处理节点: {node_id}, 状态键: {list(node_state.keys())}")
                
                # 节点开始执行
                if node_id not in node_start_times:
                    node_start_times[node_id] = time.time()
                    
                    yield {
                        "event": "node_start",
                        "data": {
                            "node_id": node_id,
                            "node_name": node_name,
                            "model": node_model,
                            "timestamp": time.time()
                        }
                    }
                    
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "info",
                            "content": f"开始执行 (模型: {node_model})"
                        }
                    }
                
                # 节点输出数据（中间结果）
                # 根据不同节点发送不同的有用信息
                if node_id == "extract_requirements" and node_state.get("extracted_requirements"):
                    req_data = node_state["extracted_requirements"]
                    
                    # 推送详细的提取结果
                    print(f"[SSE推送] node_output事件 - {node_id}")
                    output_data = {
                        "page_info": req_data.get("page_info", {}),
                        "functional_modules": req_data.get("functional_modules", []),
                        "interactions": req_data.get("interactions", []),
                        "data_model": req_data.get("data_model", []),
                        "visual_style": req_data.get("visual_style", {})
                    }
                    print(f"[SSE推送] 输出数据键: {list(output_data.keys())}")
                    
                    yield {
                        "event": "node_output",
                        "data": {
                            "node_id": node_id,
                            "node_name": node_name,
                            "output": output_data
                        }
                    }
                    
                    # 详细日志
                    page_info = req_data.get("page_info", {})
                    modules = req_data.get("functional_modules", [])
                    interactions = req_data.get("interactions", [])
                    
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "success",
                            "content": f"📄 页面类型: {page_info.get('type', 'unknown')} - {page_info.get('title', '')}"
                        }
                    }
                    
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "success",
                            "content": f"🧩 功能模块: {len(modules)} 个 - {', '.join([m.get('name', '') for m in modules[:3]])}"
                        }
                    }
                    
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "success",
                            "content": f"⚡ 交互行为: {len(interactions)} 个"
                        }
                    }
                
                elif node_id == "design_components" and node_state.get("ui_components"):
                    components = node_state['ui_components']
                    design_system = node_state.get('design_system', {})
                    
                    # 推送设计结果
                    yield {
                        "event": "node_output",
                        "data": {
                            "node_id": node_id,
                            "node_name": node_name,
                            "output": {
                                "components": components,
                                "design_system": design_system
                            }
                        }
                    }
                    
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "success",
                            "content": f"🎨 设计了 {len(components)} 个UI组件"
                        }
                    }
                    
                    colors = design_system.get("colors", {})
                    if colors:
                        yield {
                            "event": "log",
                            "data": {
                                "node": node_name,
                                "type": "info",
                                "content": f"🎨 主色: {colors.get('primary', 'N/A')}"
                            }
                        }
                
                elif node_id == "generate_html" and node_state.get("generated_html"):
                    html_code = node_state["generated_html"]
                    html_lines = len(html_code.split('\n'))
                    
                    # 推送HTML代码片段（前50行预览）
                    html_preview = '\n'.join(html_code.split('\n')[:50])
                    
                    yield {
                        "event": "node_output",
                        "data": {
                            "node_id": node_id,
                            "node_name": node_name,
                            "output": {
                                "html_preview": html_preview,
                                "total_lines": html_lines
                            }
                        }
                    }
                    
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "success",
                            "content": f"📝 生成了 {html_lines} 行HTML代码"
                        }
                    }
                
                elif node_id == "validate_preview" and node_state.get("preview_url"):
                    # 推送验证结果
                    yield {
                        "event": "node_output",
                        "data": {
                            "node_id": node_id,
                            "node_name": node_name,
                            "output": {
                                "preview_url": node_state.get("preview_url"),
                                "is_valid": node_state.get("is_valid"),
                                "validation_errors": node_state.get("validation_errors", [])
                            }
                        }
                    }
                    
                    if node_state.get("is_valid"):
                        yield {
                            "event": "log",
                            "data": {
                                "node": node_name,
                                "type": "success",
                                "content": f"✅ 验证通过，预览地址: {node_state.get('preview_url')}"
                            }
                        }
                    else:
                        errors = node_state.get("validation_errors", [])
                        yield {
                            "event": "log",
                            "data": {
                                "node": node_name,
                                "type": "warning",
                                "content": f"⚠️ 发现 {len(errors)} 个验证问题"
                            }
                        }
                
                # 节点执行完成
                duration = time.time() - node_start_times[node_id]
                
                yield {
                    "event": "node_complete",
                    "data": {
                        "node_id": node_id,
                        "node_name": node_name,
                        "duration": round(duration, 2),
                        "timestamp": time.time()
                    }
                }
                
                yield {
                    "event": "log",
                    "data": {
                        "node": node_name,
                        "type": "success",
                        "content": f"执行完成 (耗时: {duration:.2f}s)"
                    }
                }
        
        # 获取最终结果
        final_state = node_state  # 最后一个chunk的state就是最终状态
        
        # 发送完成事件（包含完整HTML以便前端可靠渲染预览）
        raw_preview_url = final_state.get("preview_url", "")
        full_preview_url = f"http://localhost:8000{raw_preview_url}" if raw_preview_url else ""
        yield {
            "event": "complete",
            "data": {
                "preview_url": full_preview_url,
                "html": final_state.get("generated_html", ""),
                "is_valid": final_state.get("is_valid", False),
                "validation_errors": final_state.get("validation_errors", []),
                "total_duration": round(sum(time.time() - t for t in node_start_times.values()), 2)
            }
        }
        
        yield {
            "event": "log",
            "data": {
                "node": "System",
                "type": "success",
                "content": "🎉 原型生成完成！"
            }
        }
    
    except Exception as e:
        yield {
            "event": "error",
            "data": {
                "message": str(e),
                "timestamp": time.time()
            }
        }
        
        yield {
            "event": "log",
            "data": {
                "node": "System",
                "type": "error",
                "content": f"生成失败: {str(e)}"
            }
        }


@router.post("/generate/stream")
async def generate_prototype_stream(request: PrototypeRequest):
    """
    流式生成原型（SSE）
    
    事件格式：
    event: node_start
    data: {"node_id": "extract", "node_name": "提取需求", "model": "Kimi"}
    
    event: log
    data: {"node": "提取需求", "type": "info", "content": "开始执行..."}
    
    event: node_complete
    data: {"node_id": "extract", "duration": 2.5}
    
    event: complete
    data: {"html": "...", "css": "...", "preview_url": "..."}
    """
    print(f"[Endpoint] generate_prototype_stream 被调用，需求长度: {len(request.requirements)}")
    
    async def sse_generator():
        """SSE格式化生成器"""
        print("[SSE Generator] sse_generator 开始执行")
        async for event_data in prototype_event_generator(request.requirements):
            event_type = event_data.get("event", "message")
            data = event_data.get("data", {})
            print(f"[SSE Generator] 生成SSE事件: {event_type}")
            
            # 手动格式化SSE消息
            sse_message = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            print(f"[SSE Generator] SSE消息前50字符: {sse_message[:50]}")
            yield sse_message
            
            # 确保立即发送
            await asyncio.sleep(0)
        
        print("[SSE Generator] sse_generator 执行完毕")

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/generate/stream/file")
async def generate_prototype_from_file(file: UploadFile = File(..., description="需求文档文件")):
    """
    通过上传文件流式生成原型（SSE）
    支持格式：.txt, .md, .pdf, .docx
    最大 10MB
    """
    content = await file.read()
    text, err = extract_text_from_file(file.filename or "unknown", content)
    if err:
        raise HTTPException(status_code=400, detail=err)
    if not text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    async def sse_generator():
        async for event_data in prototype_event_generator(text):
            event_type = event_data.get("event", "message")
            data = event_data.get("data", {})
            sse_message = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            yield sse_message
            await asyncio.sleep(0)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
