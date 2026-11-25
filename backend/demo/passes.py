"""The rules of a demo link: create, redeem (again while it runs), run out, close, purge. Runs in the system scope."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.demo.graph import account_rows, copy_rows, delete_rows
from backend.demo.models import DemoPass
from backend.modules.accounts.passwords import hash_password
from backend.modules.accounts.service import AccountService
from backend.repository.accounts import AccountRepository
from backend.repository.models import Chat, User
from backend.shared.errors import NotFoundError

# Finished demos keep their data this long, so their use can still be looked at.
KEEP_AFTER_END = timedelta(hours=24)


class DemoLinkError(Exception):
    """The link cannot be redeemed; the message is for the visitor."""


class DemoUnavailableError(Exception):
    """Demo links are not set up on this server."""


@dataclass(frozen=True)
class Limits:
    minutes: int = 60
    rounds: int = 40
    images: int = 20
    open_days: int = 7


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def status(record: DemoPass, now: datetime) -> str:
    if record.purged_at is not None:
        return "已清理"
    if record.expires_at is None:
        return "未打开" if now < record.open_before else "已失效"
    return "体验中" if now < record.expires_at else "已结束"


def is_active(record: DemoPass | None, now: datetime) -> bool:
    return record is not None and record.expires_at is not None and now < record.expires_at


@dataclass(frozen=True)
class Redeemed:
    session_token: str
    expires_at: datetime
    chat_id: str | None


class DemoPasses:
    def __init__(self, session: Session, clock=lambda: datetime.now(UTC)):
        self.session = session
        self.clock = clock

    def create(self, note: str = "", limits: Limits = Limits()) -> tuple[str, DemoPass]:
        token = secrets.token_urlsafe(24)
        record = DemoPass(token_hash=token_hash(token), note=note, minutes=limits.minutes,
                          rounds_limit=limits.rounds, images_limit=limits.images,
                          open_before=self.clock() + timedelta(days=limits.open_days))
        self.session.add(record)
        self.session.flush()
        return token, record

    def redeem(self, token: str, template_username: str) -> Redeemed:
        """The first redeem creates the account; later ones, while the demo runs, sign in to the same account."""
        record = self.session.scalar(select(DemoPass).where(DemoPass.token_hash == token_hash(token)))
        now = self.clock()
        current = status(record, now) if record is not None else None
        accounts = AccountRepository(self.session)
        if current == "体验中":
            user = self.session.get(User, record.user_id)
        elif current == "未打开":
            template = accounts.user_by_name(template_username) if template_username else None
            if template is None:
                raise DemoUnavailableError("体验暂不可用")
            user = accounts.add(User(username=self._free_username(accounts), role="demo",
                                     password_hash=hash_password(secrets.token_urlsafe(32))))
            copy_rows(self.session, account_rows(self.session, template.id), template.id, user.id)
            record.redeemed_at, record.expires_at, record.user_id = now, now + timedelta(minutes=record.minutes), user.id
        else:
            raise DemoLinkError("体验链接无效或已失效")
        session_token = AccountService(accounts, clock=self.clock).open_session(user, record.expires_at)
        chat_id = self.session.scalar(select(Chat.id).where(Chat.owner_id == user.id)
                                      .order_by(Chat.created_at.desc(), Chat.id).limit(1))
        return Redeemed(session_token, record.expires_at, chat_id)

    @staticmethod
    def _free_username(accounts: AccountRepository) -> str:
        while True:
            name = f"体验-{secrets.token_hex(3)}"
            if accounts.user_by_name(name) is None:
                return name

    def of_user(self, user_id: str) -> DemoPass | None:
        return self.session.scalar(select(DemoPass).where(DemoPass.user_id == user_id))

    def all(self) -> list[DemoPass]:
        return list(self.session.scalars(select(DemoPass).order_by(DemoPass.created_at, DemoPass.id)))

    def revoke(self, pass_id: str) -> None:
        """An unopened link stops working; a running demo ends now."""
        record = self.session.get(DemoPass, pass_id)
        if record is None:
            raise NotFoundError(f"体验链接 {pass_id} 不存在")
        now = self.clock()
        if record.expires_at is None:
            record.open_before = min(record.open_before, now)
        else:
            record.expires_at = min(record.expires_at, now)

    def close_finished(self) -> list[str]:
        """Disables the accounts of demos that have ended and signs them out; returns their user IDs."""
        closed = []
        found = self.session.execute(select(DemoPass, User).join(User, User.id == DemoPass.user_id)
                                     .where(DemoPass.expires_at <= self.clock(), User.disabled.is_(False)))
        for _, user in found:
            AccountService(AccountRepository(self.session)).set_disabled(user.username, True)
            closed.append(user.id)
        return closed

    def purge_old(self) -> list[str]:
        """Removes the data of demos that ended long enough ago; returns the IDs of the chats removed."""
        chats = []
        for record in self.session.scalars(select(DemoPass).where(
                DemoPass.expires_at <= self.clock() - KEEP_AFTER_END, DemoPass.purged_at.is_(None))):
            rows = account_rows(self.session, record.user_id)
            chats += [row["id"] for table, found in rows.items() if table.name == "chats" for row in found]
            delete_rows(self.session, rows)
            record.purged_at = self.clock()
        return chats
