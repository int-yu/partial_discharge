from __future__ import annotations

import sqlite3
from dataclasses import replace
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


def test_result_upsert_does_not_delete_referenced_history_row(engine, tmp_path):
    database = tmp_path / "history.sqlite3"
    repository = HistoryRepository(database)
    result = engine.diagnose([0.0] * 100)
    repository.save_result(result)

    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE history_note ("
            "run_id TEXT PRIMARY KEY REFERENCES diagnosis_history(run_id), "
            "note TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO history_note(run_id, note) VALUES (?, ?)",
            (result.run_id, "keep me"),
        )
        original_rowid = connection.execute(
            "SELECT rowid FROM diagnosis_history WHERE run_id = ?", (result.run_id,)
        ).fetchone()[0]

    repository.save_result(replace(result, confidence=0.5))

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT note FROM history_note").fetchone()[0] == "keep me"
        updated_rowid = connection.execute(
            "SELECT rowid FROM diagnosis_history WHERE run_id = ?", (result.run_id,)
        ).fetchone()[0]
    assert updated_rowid == original_rowid
    assert repository.get(result.run_id).confidence == 0.5


def test_legacy_schema_metadata_is_normalized_to_one_version_row(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE schema_info (version INTEGER NOT NULL)")
        connection.executemany(
            "INSERT INTO schema_info(version) VALUES (?)", [(1,), (1,), (1,)]
        )

    HistoryRepository(database)

    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(schema_info)")
        }
        rows = connection.execute(
            "SELECT singleton, version FROM schema_info"
        ).fetchall()
    assert columns == {"singleton", "version"}
    assert rows == [(1, 1)]
