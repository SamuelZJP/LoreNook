"""The shape every model-backed archive step shares; each step supplies only what differs.

read context -> call the model outside any transaction -> commit the result, or record the failure.
Input that changed during the call is a conflict: nothing is saved from a stale context.
"""

from collections.abc import Callable

from backend.repository.archive import ArchiveRepository
from backend.repository.database import Database
from backend.shared.errors import ConflictError, ModelCallError, ModelConfigurationError


def run_archive_step(database: Database, *, round_id: str, step: str, load: Callable, generate: Callable,
                     save: Callable, failures: tuple[type[Exception], ...], changed_message: str):
    with database.read() as session:
        context = load(ArchiveRepository(session))

    def ensure_unchanged(repository: ArchiveRepository) -> None:
        current = load(repository)
        # Python equality treats True == 1; JSON state types must still detect a change.
        if current != context or current.model_dump_json() != context.model_dump_json():
            raise ConflictError(changed_message)

    try:
        generated = generate(context)
    except (*failures, ModelCallError, ModelConfigurationError) as error:
        with database.transaction() as session:
            repository = ArchiveRepository(session)
            ensure_unchanged(repository)
            repository.save_error(round_id, step, str(error)[:2000])
        raise
    with database.transaction() as session:
        repository = ArchiveRepository(session)
        ensure_unchanged(repository)
        return save(repository, generated)
