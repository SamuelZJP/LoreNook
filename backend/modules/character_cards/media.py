"""Image references between stored media and a package.

Uploaded images become `media/<name>` in the package. Outside URLs in avatar fields are kept as they are.
"""

from collections.abc import Callable

from backend.modules.media import MediaStorage, media_url, name_from_url, sniff_image
from backend.modules.character_cards.package import MEDIA_DIRECTORY
from backend.shared.errors import CharacterCardError, NotFoundError


class MediaWriter:
    """Collects the images a card refers to while it is exported."""

    def __init__(self, storage: MediaStorage, readable: Callable[[str], bool]):
        """`readable` tells whether the exporting user may read a stored image; others are left out."""
        self.storage = storage
        self.readable = readable
        self.files: dict[str, bytes] = {}

    def name(self, name: str | None) -> str | None:
        """A stored image name (reference images). A file that is gone is left out."""
        if name is None:
            return None
        path = MEDIA_DIRECTORY + name
        if path not in self.files:
            if not self.readable(name):
                return None
            try:
                self.files[path] = self.storage.read(name)
            except NotFoundError:
                return None
        return path

    def url(self, url: str | None) -> str | None:
        """An image URL (avatars, portraits): uploaded images are packed, anything else kept."""
        if not url:
            return None
        name = name_from_url(url)
        return url if name is None else self.name(name)


class MediaReader:
    """Stores a package's images as they are referred to while it is imported."""

    def __init__(self, storage: MediaStorage, files: dict[str, bytes]):
        self.storage = storage
        self.files = files
        self.saved: dict[str, str] = {}

    def name(self, path: str | None) -> str | None:
        """A package path to a stored image name. Must be an image in the package."""
        if path is None:
            return None
        if path not in self.saved:
            data = self.files.get(path)
            if data is None:
                raise CharacterCardError(f"角色卡中缺少图片 {path[:200]}")
            media_type = sniff_image(data)
            if media_type is None:
                raise CharacterCardError(f"{path[:200]} 不是 PNG、JPEG 或 WebP 图片")
            self.saved[path] = self.storage.save(data, media_type)
        return self.saved[path]

    def url(self, value: str | None) -> str | None:
        """A package path to an image URL; an outside URL is kept."""
        if not value:
            return None
        return media_url(self.name(value)) if value.startswith(MEDIA_DIRECTORY) else value
