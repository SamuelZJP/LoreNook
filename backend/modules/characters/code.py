"""Who may give a character Python: the state Schema and state script run unsandboxed on the server."""

from backend.shared import scope as scopes
from backend.shared.errors import ForbiddenError


def check_code_allowed(*sources: str | None) -> None:
    """Refuses non-empty character code unless the current user is an administrator."""
    if not any(source and source.strip() for source in sources):
        return
    scope = scopes.current()
    if scope is None or not scope.is_admin:
        raise ForbiddenError("状态 Schema 和状态脚本是在服务器上运行的 Python 代码，只有管理员可以编写")
