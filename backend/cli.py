"""Command-line administration of built-in users.

    python -m backend.cli user add <name> [--admin]   asks for the password
    python -m backend.cli user passwd <name>          also signs the user out everywhere
    python -m backend.cli user disable|enable <name>
    python -m backend.cli user list
"""

import argparse
import getpass
import sys

from backend.config import Settings
from backend.modules.accounts.service import AccountService
from backend.repository.accounts import AccountRepository
from backend.repository.database import Database
from backend.shared.errors import ConflictError, NotFoundError


def _password() -> str:
    first = getpass.getpass("密码：")
    if getpass.getpass("再输一次：") != first:
        raise ValueError("两次输入不一致")
    return first


def run(argv: list[str], database: Database, read_password=_password, out=print) -> None:
    parser = argparse.ArgumentParser(prog="python -m backend.cli")
    users = parser.add_subparsers(dest="group", required=True).add_parser("user").add_subparsers(
        dest="command", required=True)
    add = users.add_parser("add")
    add.add_argument("username")
    add.add_argument("--admin", action="store_true")
    for name in ("passwd", "disable", "enable"):
        users.add_parser(name).add_argument("username")
    users.add_parser("list")
    arguments = parser.parse_args(argv)

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


def main() -> int:
    database = Database(Settings())
    try:
        run(sys.argv[1:], database)
    except (ValueError, ConflictError, NotFoundError) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        database.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
