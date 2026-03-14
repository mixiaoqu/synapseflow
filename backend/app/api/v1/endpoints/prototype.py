"""原型生成API端点"""
import json
import time
import asyncio
from typing import AsyncGenerator, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.models.schemas.prototype import PrototypeRequest, PrototypeResponse
from app.agents.graphs import create_doc_to_prototype_graph

router = APIRouter()

prototype_agent = create_doc_to_prototype_graph()


@router.post("/generate", response_model=PrototypeResponse)
async def generate_prototype(request: PrototypeRequest):
    """
    同步生成原型
    """
    try:
        initial_state = {
            "requirements_doc": request.requirements,
            "extracted_requirements": {},
            "ui_components": [],
            "design_system": {},
            "generated_html": "",
            "validation_errors": [],
            "preview_url": "",
            "is_valid": False,
            "metadata": {}
        }
        
        result = await prototype_agent.ainvoke(initial_state)
        
        return PrototypeResponse(
            preview_url=result["preview_url"],
            html=result["generated_html"],
            is_valid=result["is_valid"],
            validation_errors=result["validation_errors"],
            metadata=result["metadata"]
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def prototype_event_generator(
    requirements: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    生成SSE事件流
    
    事件类型：
    - start: 流程开始
    - node_start: 节点开始执行
    - node_output: 节点中间输出
    - log: 日志消息
    - node_complete: 节点执行完成
    - complete: 整个流程完成
    - error: 错误消息
    """
    
    try:
        graph = create_doc_to_prototype_graph()
        
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
        yield {
            "event": "start",
            "data": {
                "message": "开始生成原型",
                "timestamp": time.time()
            }
        }
        
        # 节点映射
        node_names = {
            "extract_requirements": "提取需求",
            "design_components": "设计组件",
            "generate_html": "生成HTML",
            "validate_preview": "代码验证"
        }
        
        node_models = {
            "extract_requirements": "Kimi-长文本理解",
            "design_components": "Deepseek-设计决策",
            "generate_html": "Deepseek-代码生成",
            "validate_preview": "Deepseek-代码验证"
        }
        
        node_start_times = {}
        final_state = None
        
        # 流式执行LangGraph
        async for chunk in graph.astream(initial_state):
            for node_id, node_state in chunk.items():
                node_name = node_names.get(node_id, node_id)
                node_model = node_models.get(node_id, "Unknown")
                
                # 节点开始
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
                
                # 节点输出信息
                if node_id == "extract_requirements" and node_state.get("extracted_requirements"):
                    req_data = node_state["extracted_requirements"]
                    
                    # 推送详细的提取结果
                    yield {
                        "event": "node_output",
                        "data": {
                            "node_id": node_id,
                            "node_name": node_name,
                            "output": {
                                "page_info": req_data.get("page_info", {}),
                                "functional_modules": req_data.get("functional_modules", []),
                                "interactions": req_data.get("interactions", []),
                                "data_model": req_data.get("data_model", []),
                                "visual_style": req_data.get("visual_style", {})
                            }
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
                
                # 节点完成
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
                
                final_state = node_state
        
        # 最终完成事件
        if final_state:
            yield {
                "event": "complete",
                "data": {
                    "preview_url": final_state.get("preview_url", ""),
                    "html": final_state.get("generated_html", ""),
                    "is_valid": final_state.get("is_valid", False),
                    "validation_errors": final_state.get("validation_errors", []),
                    "total_duration": round(sum(time.time() - t for t in node_start_times.values()), 2)
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


@router.post("/generate/stream")
async def generate_prototype_stream(request: PrototypeRequest):
    """
    流式生成原型（SSE）
    
    前端使用EventSource连接：
    const es = new EventSource('/api/v1/prototype/generate/stream');
    es.addEventListener('node_start', (e) => { ... });
    es.addEventListener('log', (e) => { ... });
    es.addEventListener('complete', (e) => { ... });
    """
    
    async def sse_generator():
        async for event_data in prototype_event_generator(request.requirements):
            event_type = event_data.get("event", "message")
            data = event_data.get("data", {})
            
            # SSE格式
            yield f"event: {event_type}\n"
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            
            await asyncio.sleep(0)
    
    return EventSourceResponse(sse_generator())
