"""Users and their login sessions."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.repository.models import LoginSession, User


class AccountRepository:
    def __init__(self, session: Session):
        self.session = session

    def user_by_name(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def users(self) -> list[User]:
        return list(self.session.scalars(select(User).order_by(User.created_at, User.username)))

    def add(self, record):
        self.session.add(record)
        self.session.flush()
        return record

    def login_session(self, token_hash: str) -> tuple[LoginSession, User] | None:
        row = self.session.execute(select(LoginSession, User).join(User, User.id == LoginSession.user_id)
                                   .where(LoginSession.token_hash == token_hash)).first()
        return (row[0], row[1]) if row is not None else None

    def delete_session(self, token_hash: str) -> None:
        self.session.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash))

    def delete_sessions(self, user_id: str) -> None:
        self.session.execute(delete(LoginSession).where(LoginSession.user_id == user_id))

    def delete_expired_sessions(self, now: datetime) -> None:
        self.session.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
