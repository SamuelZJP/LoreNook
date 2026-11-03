from backend.repository.models import Character
from backend.repository.queries import Repository
from backend.status_bar.models import CharacterStatusBar, ChatStatusBarSettings
from backend.status_bar.schemas import ChatStatusBar, ChatStatusBarPatch, StatusBar


class StatusBarService:
    def __init__(self, repository: Repository):
        self.repository = repository
        self.session = repository.session

    def read(self, character_id: str) -> StatusBar:
        row = self.session.get(CharacterStatusBar, character_id)
        return StatusBar(code=row.code if row is not None else "")

    def replace(self, character_id: str, code: str) -> StatusBar:
        row = self.session.get(CharacterStatusBar, character_id)
        if not code.strip():
            if row is not None:
                self.session.delete(row)
            return StatusBar()
        if row is None:
            self.repository.add(CharacterStatusBar(character_id=character_id, code=code))
        else:
            row.code = code
        return StatusBar(code=code)

    def read_chat(self, chat_id: str) -> ChatStatusBar:
        settings = self.session.get(ChatStatusBarSettings, chat_id)
        return ChatStatusBar(code=self.read(self.repository.owner_id(chat_id, Character)).code,
                             enabled=settings.enabled if settings is not None else True)

    def update_chat(self, chat_id: str, patch: ChatStatusBarPatch) -> ChatStatusBar:
        if patch.code is not None:
            self.replace(self.repository.owner_id(chat_id, Character), patch.code)
        if patch.enabled is not None:
            settings = self.session.get(ChatStatusBarSettings, chat_id)
            if settings is None:
                self.repository.add(ChatStatusBarSettings(chat_id=chat_id, enabled=patch.enabled))
            else:
                settings.enabled = patch.enabled
        self.session.flush()
        return self.read_chat(chat_id)

    def copy_for_chat(self, session, chat_id: str, payload) -> None:
        """Chat-created hook: the chat's character copy gets the card's status bar."""
        source = session.get(CharacterStatusBar, payload.character_id)
        if source is not None:
            self.repository.add(CharacterStatusBar(character_id=self.repository.owner_id(chat_id, Character),
                                                   code=source.code))
