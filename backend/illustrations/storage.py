"""Image files under one directory, one folder per chat; the database keeps relative names."""

from pathlib import Path
import re
import shutil

from backend.illustrations.comfyui import MEDIA_TYPES, RenderedImage
from backend.illustrations.errors import IllustrationError
from backend.shared.errors import NotFoundError

SAFE_NAME = re.compile(r"[A-Za-z0-9_-]+")


class ImageStorage:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def save(self, chat_id: str, illustration_id: str, image: RenderedImage) -> str:
        if not SAFE_NAME.fullmatch(chat_id) or not SAFE_NAME.fullmatch(illustration_id):
            raise IllustrationError("聊天或插图 ID 不能用作文件名")
        directory = self.root / chat_id
        directory.mkdir(parents=True, exist_ok=True)
        name = f"{illustration_id}{MEDIA_TYPES[image.media_type]}"
        temporary = directory / f".{name}.tmp"
        temporary.write_bytes(image.data)
        temporary.replace(directory / name)
        return f"{chat_id}/{name}"

    def path(self, file_name: str) -> Path:
        path = (self.root / file_name).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise NotFoundError("插图文件不存在")
        return path

    def remove_chat(self, chat_id: str) -> None:
        if SAFE_NAME.fullmatch(chat_id):
            shutil.rmtree(self.root / chat_id, ignore_errors=True)
