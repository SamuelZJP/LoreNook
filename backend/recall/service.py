"""Recall settings, and the two passes that turn the assembled layout into this request's layout."""

from backend.llm.client import ModelClient
from backend.llm.recording import recorded_workflow
from backend.modules.memory.layout import expand_layout
from backend.modules.memory.render import render_round, render_timeline
from backend.modules.memory.service import MemoryService
from backend.modules.memory.sources import MemorySources
from backend.modules.models.service import ModelService
from backend.recall.judge import judge
from backend.recall.models import ChatRecallSettings
from backend.recall.schemas import RecallContext, RecallResult, RecallSettings
from backend.repository.database import Database
from backend.repository.models import Character, Chat, ModelConfig, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.memory import ChatMemory, MemoryLayout
from backend.shared.errors import ConflictError


class RecallSettingsService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def read(self, chat_id: str) -> RecallSettings:
        self.repository.get(Chat, chat_id)
        record = self.repository.session.get(ChatRecallSettings, chat_id)
        if record is None:
            return RecallSettings()
        return RecallSettings(enabled=record.enabled, model_config_id=record.model_config_id, depth=record.depth,
                              episode_limit=record.episode_limit, summary_limit=record.summary_limit)

    def replace(self, chat_id: str, payload: RecallSettings) -> RecallSettings:
        self.repository.get(Chat, chat_id)
        if payload.model_config_id is not None:
            self.repository.get_owned(ModelConfig, payload.model_config_id, chat_id)
        record = self.repository.session.get(ChatRecallSettings, chat_id)
        if record is None:
            record = self.repository.add(ChatRecallSettings(chat_id=chat_id))
        for name, value in payload.model_dump().items():
            setattr(record, name, value)
        self.repository.session.flush()
        return self.read(chat_id)

    def setup(self, chat_id: str, payload: RecallSettings) -> RecallSettings:
        """From library resources, for a new chat: the model config is copied into it."""
        model_id = payload.model_config_id and self._chat_model(chat_id, payload.model_config_id)
        return self.replace(chat_id, payload.model_copy(update={"model_config_id": model_id}))

    def _chat_model(self, chat_id: str, source_id: str) -> str:
        """A chat copy of a library model config, reusing an identical copy it already has."""
        source = self.repository.get_owned(ModelConfig, source_id, None)
        fields = ("name", "api_type", "base_url", "api_key", "model", "default_parameters", "timeout_seconds")
        for record in self.repository.list_owned(ModelConfig, chat_id):
            if all(getattr(record, name) == getattr(source, name) for name in fields):
                return record.id
        return self.repository.add(ModelConfig(chat_id=chat_id, **{name: getattr(source, name) for name in fields})).id


def _episode_candidates(layout: MemoryLayout, sources: MemorySources) -> dict[str, str]:
    return {f"E{number}": f"《{sources.episodes[number].title}》{sources.episodes[number].summary}"
            for segment in layout.memory if segment.kind == "episode" for number in segment.numbers}


def _summary_candidates(layout: MemoryLayout, sources: MemorySources) -> dict[str, str]:
    return {f"R{number}": sources.rounds[number].summary
            for segment in layout.memory if segment.kind == "summary" for number in segment.numbers}


def _recall_layout(context: RecallContext, settings: RecallSettings, layout: MemoryLayout, sources: MemorySources,
                   client: ModelClient) -> MemoryLayout:
    episodes = judge(context, "episode", _episode_candidates(layout, sources), settings.episode_limit, client)
    opened = expand_layout(layout, sources, episodes=episodes)
    summaries = judge(context, "summary", _summary_candidates(opened, sources), settings.summary_limit, client)
    return expand_layout(opened, sources, summaries=summaries)


@recorded_workflow("memory_recall")
def run_recall(database: Database, client: ModelClient, chat_id: str, user_input: str, instruction: str = "") -> RecallResult:
    with database.read() as session:
        repository = Repository(session)
        latest = repository.latest_round(chat_id)
        if latest is not None and latest.archive_step != "complete":
            raise ConflictError("请先完成当前回合归档")
        snapshot = MemoryService(repository).snapshot(chat_id)
        settings = RecallSettingsService(repository).read(chat_id)
        connection = (ModelService(repository, chat_id).connection(settings.model_config_id)
                      if settings.enabled and settings.model_config_id else None)
        character = repository.get(Character, repository.owner_id(chat_id, Character))
        identity = repository.get(UserIdentity, repository.owner_id(chat_id, UserIdentity))
        names = {"character_name": character.name, "user_name": identity.name}

    layout = snapshot.layout
    if connection is not None:
        rounds = list(snapshot.sources.rounds.values())
        basis = rounds[-settings.depth:] if settings.depth else []
        context = RecallContext(**names, basis_rounds=[render_round(record, names["user_name"]) for record in basis],
                                user_input=user_input, instruction=instruction, connection=connection)
        layout = _recall_layout(context, settings, layout, snapshot.sources, client)
    timeline = render_timeline(layout, snapshot.sources, snapshot.settings)
    return RecallResult(layout=layout, timeline=ChatMemory(chat_id=chat_id, **timeline.model_dump()))
