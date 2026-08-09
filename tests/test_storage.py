from __future__ import annotations

from datetime import datetime, timezone

from pd_diagnosis.storage import HistoryRepository


def test_history_persists_and_searches(engine, project_root, tmp_path):
    database = tmp_path / "history.sqlite3"
    repository = HistoryRepository(database)
    result = engine.diagnose_file(project_root / "data" / "train" / "0" / "a1.txt")
    repository.save_result(result)

    reopened = HistoryRepository(database)
    assert reopened.count() == 1
    records = reopened.list(query="金属突出")
    assert len(records) == 1
    assert records[0].run_id == result.run_id
    assert records[0].probabilities["金属突出物缺陷"] > 0.96


def test_history_records_structured_error(tmp_path):
    repository = HistoryRepository(tmp_path / "history.sqlite3")
    repository.save_error(
        run_id="failed-run",
        created_at=datetime.now(timezone.utc),
        source_id="broken.txt",
        model_version="test",
        message="输入无效",
    )
    record = repository.get("failed-run")
    assert record.status == "error"
    assert record.error_message == "输入无效"
    assert repository.delete(["failed-run"]) == 1
    assert repository.count() == 0
