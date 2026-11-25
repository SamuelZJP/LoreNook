"""The zip container. Nothing is extracted to disk; entries are read into memory within fixed limits."""

from dataclasses import dataclass, field
import io
import re
import zipfile

from backend.modules.media import MAX_BYTES
from backend.shared.errors import CharacterCardError

CARD_FILE = "card.json"
MEDIA_DIRECTORY = "media/"
MEDIA_PATH = re.compile(r"media/[A-Za-z0-9_-][A-Za-z0-9._-]*")
MAX_CARD_BYTES = 16 * 1024 * 1024
MAX_PACKAGE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 256


@dataclass
class Package:
    card: bytes
    media: dict[str, bytes] = field(default_factory=dict)


def write_package(package: Package) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(CARD_FILE, package.card, compress_type=zipfile.ZIP_DEFLATED)
        for path, data in sorted(package.media.items()):
            # Images are already compressed.
            archive.writestr(path, data, compress_type=zipfile.ZIP_STORED)
    return buffer.getvalue()


def _read(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int) -> bytes:
    if info.file_size > limit:
        raise CharacterCardError(f"角色卡中的 {info.filename} 过大")
    try:
        with archive.open(info) as entry:
            data = entry.read(limit + 1)
    except (RuntimeError, zipfile.BadZipFile, NotImplementedError, OSError) as error:
        raise CharacterCardError(f"无法读取角色卡中的 {info.filename}") from error
    if len(data) > limit:
        raise CharacterCardError(f"角色卡中的 {info.filename} 过大")
    return data


def read_package(data: bytes) -> Package:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise CharacterCardError("不是有效的角色卡文件") from error
    with archive:
        entries = [info for info in archive.infolist() if not info.is_dir()]
        if len(entries) > MAX_ENTRIES:
            raise CharacterCardError("角色卡中的文件过多")
        card, media, total = None, {}, 0
        for info in entries:
            if info.filename == CARD_FILE:
                card = _read(archive, info, MAX_CARD_BYTES)
                total += len(card)
            elif info.filename.startswith(MEDIA_DIRECTORY):
                if not MEDIA_PATH.fullmatch(info.filename):
                    raise CharacterCardError(f"角色卡中的路径无效：{info.filename[:200]}")
                media[info.filename] = _read(archive, info, MAX_BYTES)
                total += len(media[info.filename])
            # Anything else is not part of the format and is ignored.
            if total > MAX_TOTAL_BYTES:
                raise CharacterCardError("角色卡内容过大")
    if card is None:
        raise CharacterCardError("角色卡中缺少 card.json")
    return Package(card=card, media=media)
