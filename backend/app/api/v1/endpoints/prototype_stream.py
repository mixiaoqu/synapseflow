"""
原型生成流式 API（SSE）
仅推送文本日志与完成结果，供前端展示进度与预览（无节点/流程图专用事件）
"""
import json
import time
import asyncio
from typing import AsyncGenerator, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from loguru import logger

from app.agents.graphs import create_doc_to_prototype_graph
from app.utils.file_parser import extract_text_from_file

router = APIRouter()


async def prototype_event_generator(
    requirements: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    生成 SSE 事件流

    事件类型：
    - start: 流程开始
    - log: 日志消息
    - complete: 整个流程完成
    - error: 错误消息
    """
    stream_start = time.time()
    node_names = {
        "extract_requirements": "提取需求",
        "design_components": "设计组件",
        "generate_html": "生成HTML",
        "validate_preview": "代码验证",
    }
    node_models = {
        "extract_requirements": "Kimi-长文本理解",
        "design_components": "Deepseek-设计决策",
        "generate_html": "Deepseek-代码生成",
        "validate_preview": "Deepseek-代码验证",
    }
    node_start_times: Dict[str, float] = {}
    last_node_state: Dict[str, Any] = {}

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
            "metadata": {},
        }

        yield {
            "event": "start",
            "data": {
                "message": "开始生成原型",
                "timestamp": time.time(),
            },
        }

        async for chunk in graph.astream(initial_state):
            for node_id, node_state in chunk.items():
                node_name = node_names.get(node_id, node_id)
                node_model = node_models.get(node_id, "Unknown")
                last_node_state = node_state

                if node_id not in node_start_times:
                    node_start_times[node_id] = time.time()
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "info",
                            "content": "开始执行 (模型: %s)" % node_model,
                        },
                    }

                if node_id == "extract_requirements" and node_state.get(
                    "extracted_requirements"
                ):
                    req_data = node_state["extracted_requirements"]
                    page_info = req_data.get("page_info", {})
                    modules = req_data.get("functional_modules", [])
                    interactions = req_data.get("interactions", [])
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "success",
                            "content": "📄 页面类型: %s - %s"
                            % (
                                page_info.get("type", "unknown"),
                                page_info.get("title", ""),
                            ),
                        },
                    }
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "success",
                            "content": "🧩 功能模块: %s 个 - %s"
                            % (
                                len(modules),
                                ", ".join([m.get("name", "") for m in modules[:3]]),
                            ),
                        },
                    }
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "success",
                            "content": "⚡ 交互行为: %s 个" % len(interactions),
                        },
                    }

                elif node_id == "design_components" and node_state.get("ui_components"):
                    components = node_state["ui_components"]
                    design_system = node_state.get("design_system", {})
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "success",
                            "content": "🎨 设计了 %s 个UI组件" % len(components),
                        },
                    }
                    colors = design_system.get("colors", {})
                    if colors:
                        yield {
                            "event": "log",
                            "data": {
                                "node": node_name,
                                "type": "info",
                                "content": "🎨 主色: %s"
                                % colors.get("primary", "N/A"),
                            },
                        }

                elif node_id == "generate_html" and node_state.get("generated_html"):
                    html_code = node_state["generated_html"]
                    html_lines = len(html_code.split("\n"))
                    yield {
                        "event": "log",
                        "data": {
                            "node": node_name,
                            "type": "success",
                            "content": "📝 生成了 %s 行HTML代码" % html_lines,
                        },
                    }

                elif node_id == "validate_preview" and node_state.get("preview_url"):
                    if node_state.get("is_valid"):
                        yield {
                            "event": "log",
                            "data": {
                                "node": node_name,
                                "type": "success",
                                "content": "✅ 验证通过，预览地址: %s"
                                % node_state.get("preview_url"),
                            },
                        }
                    else:
                        errors = node_state.get("validation_errors", [])
                        yield {
                            "event": "log",
                            "data": {
                                "node": node_name,
                                "type": "warning",
                                "content": "⚠️ 发现 %s 个验证问题" % len(errors),
                            },
                        }

                duration = time.time() - node_start_times[node_id]
                yield {
                    "event": "log",
                    "data": {
                        "node": node_name,
                        "type": "success",
                        "content": "执行完成 (耗时: %.2fs)" % duration,
                    },
                }

        total_duration = round(time.time() - stream_start, 2)
        raw_preview_url = last_node_state.get("preview_url", "")
        full_preview_url = (
            "http://localhost:8000%s" % raw_preview_url if raw_preview_url else ""
        )
        logger.info(
            "[原型流式] 生成完成，总耗时 %.1fs，预览 %s",
            total_duration,
            raw_preview_url or "(无)",
        )

        yield {
            "event": "complete",
            "data": {
                "preview_url": full_preview_url,
                "html": last_node_state.get("generated_html", ""),
                "css": "",
                "js": "",
                "is_valid": last_node_state.get("is_valid", False),
                "validation_errors": last_node_state.get("validation_errors", []),
                "total_duration": total_duration,
            },
        }

        yield {
            "event": "log",
            "data": {
                "node": "System",
                "type": "success",
                "content": "🎉 原型生成完成！",
            },
        }

    except Exception as e:
        logger.exception("[原型流式] 生成失败: %s", e)
        yield {
            "event": "error",
            "data": {
                "message": str(e),
                "timestamp": time.time(),
            },
        }
        yield {
            "event": "log",
            "data": {
                "node": "System",
                "type": "error",
                "content": "生成失败: %s" % str(e),
            },
        }


@router.post("/generate/stream/file")
async def generate_prototype_from_file(
    file: UploadFile = File(..., description="需求文档文件"),
):
    """
    通过上传文件流式生成原型（SSE）
    支持格式：.txt, .md, .pdf, .docx，最大 10MB
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
            sse_message = (
                "event: %s\ndata: %s\n\n"
                % (event_type, json.dumps(data, ensure_ascii=False))
            )
            yield sse_message
            await asyncio.sleep(0)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
