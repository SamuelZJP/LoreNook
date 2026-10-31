"""One generation or regeneration; return an unsaved candidate for confirmation."""

from backend.llm.client import ModelClient
from backend.llm.recording import recorded_workflow
from backend.modules.models.service import ModelService
from backend.modules.presets.runtime import PresetRuntime
from backend.repository.database import Database
from backend.repository.queries import Repository
from backend.schemas.memory import MemoryLayout
from backend.schemas.writing import WritingResult
from backend.shared.errors import ConflictError
from backend.workflows.writing_materials import collect_writing_snapshot, resolve_writing_materials


@recorded_workflow("writing")
def generate_writing(database: Database, client: ModelClient, chat_id: str, user_input: str,
                     instruction: str = "", layout: MemoryLayout | None = None) -> WritingResult:
    with database.read() as session:
        repository = Repository(session)
        snapshot = collect_writing_snapshot(repository, chat_id, layout)
        binding = repository.model_binding(chat_id, "writing")
        if binding is None:
            raise ConflictError("聊天尚未绑定 writing 用途的模型配置")
        model_config_id = binding.model_config_id
        connection = ModelService(repository, chat_id).connection(model_config_id)

    materials = resolve_writing_materials(snapshot, user_input, instruction)
    runtime = PresetRuntime()
    request = runtime.build(snapshot.source, materials)
    response = client.invoke(connection, request)
    # Use the same source snapshot even if the saved preset was edited in flight.
    output = runtime.parse(snapshot.source, response.response)
    return WritingResult(
        chat_id=chat_id, preset_id=snapshot.preset_id, model_config_id=model_config_id,
        state_snapshot_id=snapshot.state_snapshot_id, based_on_round_id=snapshot.based_on_round_id,
        user_input=user_input, ai_output=output.ai_output,
    )
