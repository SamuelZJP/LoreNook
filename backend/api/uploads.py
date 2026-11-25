from fastapi import HTTPException, Request


async def read_body(request: Request, limit: int, too_large: str) -> bytes:
    """The raw request body, refused as soon as it passes `limit` bytes."""
    error = HTTPException(status_code=413, detail=too_large)
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise error
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limit:
            raise error
    return bytes(data)
