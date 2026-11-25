"""Built-in users and browser sessions. There is no self-service sign-up; users are created from the command line."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import re
import secrets

from backend.modules.accounts.passwords import DUMMY_HASH, hash_password, verify_password
from backend.repository.accounts import AccountRepository
from backend.repository.models import LoginSession, User
from backend.shared.errors import ConflictError, NotFoundError

SESSION_DAYS = 30
# Extending on every request would write on every request; once a day is enough for a 30-day window.
REFRESH_AFTER = timedelta(days=1)
USERNAME = re.compile(r"[A-Za-z0-9_.\-一-鿿]{2,32}")
MIN_PASSWORD = 8
ROLES = ("admin", "user")


@dataclass(frozen=True)
class Account:
    id: str
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _account(user: User) -> Account:
    return Account(id=user.id, username=user.username, role=user.role)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def validate_credentials(username: str, password: str) -> None:
    if not USERNAME.fullmatch(username):
        raise ValueError("用户名为 2–32 位字母、数字、汉字或 _ . -")
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"密码至少 {MIN_PASSWORD} 位")


class AccountService:
    def __init__(self, repository: AccountRepository, clock=lambda: datetime.now(UTC)):
        self.repository = repository
        self.clock = clock

    # Administration (command line)

    def create_user(self, username: str, password: str, role: str = "user") -> Account:
        validate_credentials(username, password)
        if role not in ROLES:
            raise ValueError(f"角色只能是 {', '.join(ROLES)}")
        if self.repository.user_by_name(username) is not None:
            raise ConflictError(f"用户 {username} 已存在")
        return _account(self.repository.add(User(username=username, password_hash=hash_password(password), role=role)))

    def set_password(self, username: str, password: str) -> None:
        validate_credentials(username, password)
        user = self._user(username)
        user.password_hash = hash_password(password)
        self.repository.delete_sessions(user.id)

    def set_disabled(self, username: str, disabled: bool) -> None:
        user = self._user(username)
        user.disabled = disabled
        if disabled:
            self.repository.delete_sessions(user.id)

    def list_users(self) -> list[User]:
        return self.repository.users()

    def _user(self, username: str) -> User:
        user = self.repository.user_by_name(username)
        if user is None:
            raise NotFoundError(f"用户 {username} 不存在")
        return user

    # Sessions

    def login(self, username: str, password: str) -> tuple[str, Account] | None:
        """A new session token for valid credentials, else None."""
        user = self.repository.user_by_name(username)
        valid = verify_password(password, user.password_hash if user is not None else DUMMY_HASH)
        if user is None or not valid or user.disabled:
            return None
        token = secrets.token_urlsafe(32)
        now = self.clock()
        self.repository.delete_expired_sessions(now)
        self.repository.add(LoginSession(user_id=user.id, token_hash=_token_hash(token),
                                         expires_at=now + timedelta(days=SESSION_DAYS), last_seen_at=now))
        return token, _account(user)

    def resolve(self, token: str) -> tuple[Account | None, bool]:
        """Read-only: the signed-in account, and whether the session is due for `refresh`."""
        found = self.repository.login_session(_token_hash(token))
        if found is None:
            return None, False
        record, user = found
        now = self.clock()
        if record.expires_at <= now or user.disabled:
            return None, False
        return _account(user), now - record.last_seen_at >= REFRESH_AFTER

    def refresh(self, token: str) -> None:
        found = self.repository.login_session(_token_hash(token))
        if found is not None:
            now = self.clock()
            found[0].last_seen_at = now
            found[0].expires_at = now + timedelta(days=SESSION_DAYS)

    def logout(self, token: str) -> None:
        self.repository.delete_session(_token_hash(token))
