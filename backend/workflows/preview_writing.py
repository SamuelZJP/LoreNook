"""Collect one database snapshot, then transform outside its transaction."""

from backend.modules.presets.runtime import PresetRuntime
from backend.repository.database import Database
from backend.repository.queries import Repository
from backend.schemas.memory import MemoryLayout
from backend.schemas.presets import WritingPreview
from backend.workflows.writing_materials import collect_writing_snapshot, resolve_writing_materials


def preview_writing(database: Database, chat_id: str, user_input: str, instruction: str = "",
                    layout: MemoryLayout | None = None) -> WritingPreview:
    with database.read() as session:
        snapshot = collect_writing_snapshot(Repository(session), chat_id, layout)
    materials = resolve_writing_materials(snapshot, user_input, instruction)
    request = PresetRuntime().build(snapshot.source, materials)
    return WritingPreview(chat_id=chat_id, preset_id=snapshot.preset_id,
                          state_snapshot_id=snapshot.state_snapshot_id, request=request)
