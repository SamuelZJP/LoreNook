import pytest
from alembic import command
from sqlalchemy import text

from backend.modules.admin.service import AdminService
from backend.repository.admin import AdminRepository
from backend.repository.archive import ArchiveRepository
from backend.schemas.admin import AdminBatch
from backend.shared.errors import ConflictError
from backend.tests.conftest import migration_config
from backend.tests.test_admin import apply, create, edit, managed_history
from backend.tests.test_catalog_api import run_api
from backend.tests.test_writing import database_contents


def imported(ids, start=5, end=6):
    return create("episodes", id="imported", chat_id=ids["chat_id"],
                  start_round_id=ids["rounds"][start], end_round_id=ids["rounds"][end],
                  title="历史情节", summary=" 历史原文\r\n", created_by_round_id=None)


def test_imported_episode_through_latest_round_reads_and_allows_future_archiving(database, managed_history):
    ids = managed_history

    async def scenario(client):
        result = await apply(client, [imported(ids)])
        assert result.status_code == 200, result.text
        episodes = (await client.get(f"/api/chats/{ids['chat_id']}/episodes")).json()
        assert episodes[-1]["created_by_round_id"] is None
        assert episodes[-1]["summary"] == " 历史原文\r\n"
        assert (await client.get(f"/api/chats/{ids['chat_id']}/memory")).status_code == 200
        archive = (await client.get(f"/api/chats/{ids['chat_id']}/archive")).json()
        assert archive["round"]["archive_step"] == "complete" and archive["episode"] is None
        # Imported history is edited through data management, not latest-round editing.
        assert (await client.put(f"/api/chats/{ids['chat_id']}/episodes/imported",
                                 json={"summary": "改写"})).status_code == 409

    run_api(database, scenario)
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        assert repo.unrepresented_rounds(ids["chat_id"]) == []
        eighth = repo.create_round(ids["chat_id"], "输入八", "输出八")
        assert eighth.round_no == 8
        repo.save_state(eighth.id, {})
        repo.save_summary(eighth.id, "摘要八")
        repo.save_decision(eighth.id)
        ninth = repo.create_round(ids["chat_id"], "输入九", "输出九")
        repo.save_state(ninth.id, {})
        repo.save_summary(ninth.id, "摘要九")
        # Normal archives must still end before their creating round.
        with pytest.raises(ConflictError):
            repo.save_decision(ninth.id, start_round_id=eighth.id, end_round_id=ninth.id)
        repo.save_decision(ninth.id, start_round_id=eighth.id, end_round_id=eighth.id)
        episode = repo.save_episode(ninth.id, "后续正常情节")
        assert episode.created_by_round_id == ninth.id
        service = AdminService(AdminRepository(session))
        service.apply(AdminBatch.model_validate({
            "expected_revision": service.snapshot().revision,
            "operations": [edit("episodes", "imported", title="已导入")],
        }))


@pytest.mark.parametrize("start,end", [(4, 6), (6, 6), (6, 5)])
def test_imported_episode_cannot_overlap_skip_or_reverse_history(database, managed_history, start, end):
    before = database_contents(database)

    async def scenario(client):
        result = await apply(client, [imported(managed_history, start, end)])
        assert result.status_code == 409, result.text

    run_api(database, scenario)
    assert database_contents(database) == before


def test_imported_episode_cannot_cover_pending_round(database, managed_history):
    ids = managed_history
    before = database_contents(database)

    async def scenario(client):
        result = await apply(client, [
            edit("rounds", ids["rounds"][-1], archive_step="round_summary", summary=None, episode_required=None),
            imported(ids),
        ])
        assert result.status_code == 409, result.text

    run_api(database, scenario)
    assert database_contents(database) == before


def test_downgrade_refuses_to_discard_imported_history(database, managed_history, tmp_path):
    ids = managed_history
    with database.transaction() as session:
        service = AdminService(AdminRepository(session))
        service.apply(AdminBatch.model_validate({
            "expected_revision": service.snapshot().revision, "operations": [imported(ids)],
        }))
    database.dispose()
    config = migration_config(tmp_path / "test.db")
    command.downgrade(config, "e36b9c7210af")

    def episodes():
        with database.read() as session:
            return session.execute(text("SELECT * FROM episodes ORDER BY id")).all()
    before = episodes()
    with pytest.raises(ValueError, match="Cannot downgrade"):
        command.downgrade(config, "d49c370021ae")
    assert episodes() == before
    with database.read() as session:
        assert session.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "e36b9c7210af"
