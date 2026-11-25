"""Uploaded images (avatars, reference images), stored by content hash.

A hash name means copies of a character in chats share one file and never need reference counting;
files no record points at any more are simply left in place.
"""

import hashlib
from pathlib import Path
import re

from backend.shared.errors import NotFoundError

MAX_BYTES = 16 * 1024 * 1024
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MEDIA_NAME = re.compile(r"[0-9a-f]{64}\.(png|jpg|webp)")
# Avatars and portraits store this URL; reference images store the bare name.
URL_PREFIX = "/api/media/"


def media_url(name: str) -> str:
    return URL_PREFIX + name


def name_from_url(url: str) -> str | None:
    """The stored name behind an uploaded image's URL; None for anything else, such as an outside URL."""
    name = url.removeprefix(URL_PREFIX)
    return name if url.startswith(URL_PREFIX) and MEDIA_NAME.fullmatch(name) else None


def sniff_image(data: bytes) -> str | None:
    """The real type from the file's first bytes; a client's Content-Type is not trusted."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def media_type_of(name: str) -> str:
    extension = "." + name.rsplit(".", 1)[-1]
    return next(kind for kind, value in EXTENSIONS.items() if value == extension)


class MediaStorage:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def save(self, data: bytes, media_type: str) -> str:
        name = hashlib.sha256(data).hexdigest() + EXTENSIONS[media_type]
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / name
        if not target.exists():
            temporary = self.root / f".{name}.tmp"
            temporary.write_bytes(data)
            temporary.replace(target)
        return name

    def path(self, name: str) -> Path:
        path = self.root / name
        if not MEDIA_NAME.fullmatch(name) or not path.is_file():
            raise NotFoundError("图片不存在")
        return path

    def read(self, name: str) -> bytes:
        return self.path(name).read_bytes()
