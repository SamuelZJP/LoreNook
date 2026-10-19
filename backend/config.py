"""Runtime configuration; relative SQLite paths resolve from the project root."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv(
        "LORENOOK_DATABASE_URL", "sqlite:///data/lorenook.db"
    ))
    sqlite_busy_timeout_ms: int = 5000
    llm_timeout_seconds: float = 120.0
    llm_max_response_bytes: int = 8 * 1024 * 1024
    llm_recording_directory: str | None = field(default_factory=lambda: os.getenv("LORENOOK_LLM_RECORDING_DIRECTORY"))
    state_recent_summaries: int = 3
    round_summary_recent_summaries: int = 3

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
