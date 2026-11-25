from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from backend.api.dependencies import DatabaseDependency
from backend.api.uploads import read_body
from backend.modules.media import MAX_BYTES, media_type_of, media_url, sniff_image
from backend.repository.queries import Repository
from backend.shared.errors import NotFoundError
from backend.schemas.common import Contract

router = APIRouter(prefix="/api/media", tags=["media"])


class MediaRead(Contract):
    name: str
    url: str


@router.post("", response_model=MediaRead, status_code=201)
async def upload(request: Request, database: DatabaseDependency):
    """The request body is the image itself."""
    data = await read_body(request, MAX_BYTES, f"图片不能超过 {MAX_BYTES // (1024 * 1024)} MB")
    media_type = sniff_image(data)
    if media_type is None:
        raise HTTPException(status_code=415, detail="只支持 PNG、JPEG、WebP 图片")
    name = await run_in_threadpool(request.app.state.media.save, data, media_type)

    def register():
        with database.transaction() as session:
            Repository(session).own_media(name)
    await run_in_threadpool(register)
    return MediaRead(name=name, url=media_url(name))


@router.get("/{name}")
def read(name: str, request: Request, database: DatabaseDependency):
    with database.read() as session:
        if not Repository(session).owns_media(name):
            raise NotFoundError("图片不存在")
    # The name is the content hash, so the bytes behind a URL never change.
    return FileResponse(request.app.state.media.path(name), media_type=media_type_of(name),
                        headers={"cache-control": "private, max-age=31536000, immutable",
                                 "x-content-type-options": "nosniff"})
