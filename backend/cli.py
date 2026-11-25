"""Command-line administration of built-in users and demo links.

    python -m backend.cli user add <name> [--admin]   asks for the password
    python -m backend.cli user passwd <name>          also signs the user out everywhere
    python -m backend.cli user disable|enable <name>
    python -m backend.cli user list
    python -m backend.cli demo link [--note TEXT] [--minutes 60] [--rounds 40] [--images 20] [--open-days 7]
    python -m backend.cli demo list
    python -m backend.cli demo revoke <id>
"""

import argparse
from datetime import UTC, datetime
import getpass
import sys

from backend.config import Settings
from backend.demo.passes import DemoPasses, Limits, status
from backend.modules.accounts.service import AccountService
from backend.repository.accounts import AccountRepository
from backend.repository.database import Database
from backend.shared import scope as scopes
from backend.shared.errors import ConflictError, NotFoundError


def _password() -> str:
    first = getpass.getpass("密码：")
    if getpass.getpass("再输一次：") != first:
        raise ValueError("两次输入不一致")
    return first


def run(argv: list[str], database: Database, read_password=_password, out=print, origin: str = "") -> None:
    parser = argparse.ArgumentParser(prog="python -m backend.cli")
    groups = parser.add_subparsers(dest="group", required=True)
    users = groups.add_parser("user").add_subparsers(dest="command", required=True)
    add = users.add_parser("add")
    add.add_argument("username")
    add.add_argument("--admin", action="store_true")
    for name in ("passwd", "disable", "enable"):
        users.add_parser(name).add_argument("username")
    users.add_parser("list")
    demos = groups.add_parser("demo").add_subparsers(dest="command", required=True)
    link = demos.add_parser("link")
    link.add_argument("--note", default="")
    defaults = Limits()
    for name in ("minutes", "rounds", "images", "open_days"):
        link.add_argument(f"--{name.replace('_', '-')}", type=_positive, default=getattr(defaults, name))
    demos.add_parser("list")
    demos.add_parser("revoke").add_argument("id")
    arguments = parser.parse_args(argv)

    if arguments.group == "demo":
        _demo(arguments, database, out, origin)
        return
    with database.transaction() as session:
        service = AccountService(AccountRepository(session))
        match arguments.command:
            case "add":
                account = service.create_user(arguments.username, read_password(),
                                              "admin" if arguments.admin else "user")
                out(f"已创建 {account.username}（{account.role}）")
            case "passwd":
                service.set_password(arguments.username, read_password())
                out(f"已修改 {arguments.username} 的密码")
            case "disable" | "enable":
                service.set_disabled(arguments.username, arguments.command == "disable")
                out(f"已{'停用' if arguments.command == 'disable' else '启用'} {arguments.username}")
            case "list":
                for user in service.list_users():
                    out(f"{user.username}\t{user.role}\t{'停用' if user.disabled else '正常'}")


def _positive(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("不能为负数")
    return value


def _demo(arguments, database: Database, out, origin: str) -> None:
    with scopes.scoped(scopes.SYSTEM), database.transaction() as session:
        passes = DemoPasses(session)
        match arguments.command:
            case "link":
                if arguments.minutes == 0:
                    raise ValueError("体验时长至少 1 分钟")
                token, record = passes.create(arguments.note, Limits(
                    minutes=arguments.minutes, rounds=arguments.rounds, images=arguments.images,
                    open_days=arguments.open_days))
                out(f"{origin.rstrip('/')}/try/{token}")
                out(f"{record.id}\t{record.minutes} 分钟\t{record.rounds_limit} 轮\t{record.images_limit} 张图"
                    f"\t{record.open_before.astimezone():%Y-%m-%d %H:%M} 前打开")
            case "list":
                now = datetime.now(UTC)
                for record in passes.all():
                    out(f"{record.id}\t{status(record, now)}\t写作 {record.rounds_used}/{record.rounds_limit}"
                        f"\t生图 {record.images_used}/{record.images_limit}\t{record.note}")
            case "revoke":
                passes.revoke(arguments.id)
                out(f"已作废 {arguments.id}")


def main() -> int:
    settings = Settings()
    database = Database(settings)
    try:
        run(sys.argv[1:], database, origin=settings.public_origin)
    except (ValueError, ConflictError, NotFoundError) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        database.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
