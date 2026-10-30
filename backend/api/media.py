from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from backend.modules.media import MAX_BYTES, media_type_of, sniff_image
from backend.schemas.common import Contract

router = APIRouter(prefix="/api/media", tags=["media"])


class MediaRead(Contract):
    name: str
    url: str


@router.post("", response_model=MediaRead, status_code=201)
async def upload(request: Request):
    """The request body is the image itself."""
    too_large = HTTPException(status_code=413, detail=f"图片不能超过 {MAX_BYTES // (1024 * 1024)} MB")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BYTES:
        raise too_large
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise too_large
    media_type = sniff_image(bytes(data))
    if media_type is None:
        raise HTTPException(status_code=415, detail="只支持 PNG、JPEG、WebP 图片")
    name = await run_in_threadpool(request.app.state.media.save, bytes(data), media_type)
    return MediaRead(name=name, url=f"/api/media/{name}")


@router.get("/{name}")
def read(name: str, request: Request):
    # The name is the content hash, so the bytes behind a URL never change.
    return FileResponse(request.app.state.media.path(name), media_type=media_type_of(name),
                        headers={"cache-control": "private, max-age=31536000, immutable",
                                 "x-content-type-options": "nosniff"})
