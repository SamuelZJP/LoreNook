"""Runtime configuration; relative SQLite paths resolve from the project root."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv(
        "LORENOOK_DATABASE_URL", "sqlite:///data/lorenook.db"
    ))
    sqlite_busy_timeout_ms: int = 5000
    llm_max_response_bytes: int = 8 * 1024 * 1024
    llm_recording_directory: str | None = field(default_factory=lambda: os.getenv("LORENOOK_LLM_RECORDING_DIRECTORY"))
    state_recent_summaries: int = 3
    round_summary_recent_summaries: int = 3
    media_directory: str = field(default_factory=lambda: os.getenv("LORENOOK_MEDIA_DIRECTORY", "data/media"))
    image_directory: str = field(default_factory=lambda: os.getenv("LORENOOK_IMAGE_DIRECTORY", "data/images"))
    comfyui_timeout_seconds: float = 600.0
    comfyui_poll_seconds: float = 1.0
    # Session cookies only travel over HTTPS; browsers accept them on http://localhost too.
    cookie_secure: bool = field(default_factory=lambda: _flag("LORENOOK_COOKIE_SECURE", "1"))
    # /docs and /openapi.json; off in production.
    api_docs: bool = field(default_factory=lambda: _flag("LORENOOK_API_DOCS", "0"))
    # ICP filing number shown in the home page footer.
    icp_number: str = field(default_factory=lambda: os.getenv("LORENOOK_ICP_NUMBER", ""))

    @staticmethod
    def _resolved(directory: str) -> Path:
        path = Path(directory)
        return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()

    def resolved_media_directory(self) -> Path:
        return self._resolved(self.media_directory)

    def resolved_image_directory(self) -> Path:
        return self._resolved(self.image_directory)

    def resolved_database_url(self) -> str:
        url = make_url(self.database_url)
        if url.drivername != "sqlite":
            raise ValueError("LoreNook currently supports sqlite URLs only")
        if url.database and url.database != ":memory:":
            path = Path(url.database)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            url = url.set(database=str(path.resolve()))
        return url.render_as_string(hide_password=False)
