"""原型流式生成 API。"""

from fastapi import APIRouter, File, UploadFile

from app.application import prototype_stream_service

router = APIRouter()


@router.post("/generate/stream/file")
async def generate_prototype_from_file(
    file: UploadFile = File(..., description="需求文档文件"),
):
    """
    通过上传文件流式生成原型（SSE）。
    支持格式：`.txt`、`.md`、`.pdf`、`.docx`，最大 10MB。
    """
    return await prototype_stream_service.stream_file(file)
