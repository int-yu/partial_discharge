from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .types import DiagnosisResult, Pathish


@dataclass(frozen=True, slots=True)
class HistoryRecord:
    run_id: str
    created_at: str
    source_id: str | None
    model_version: str
    class_id: int | None
    label: str | None
    confidence: float | None
    probabilities: dict[str, float]
    features: dict[str, float]
    warnings: tuple[str, ...]
    status: str
    error_message: str | None


class HistoryRepository:
    SCHEMA_VERSION = 1

    def __init__(self, database_path: Pathish) -> None:
        self.path = Path(database_path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_info (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS diagnosis_history (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    source_id TEXT,
                    model_version TEXT NOT NULL,
                    class_id INTEGER,
                    label TEXT,
                    confidence REAL,
                    probabilities_json TEXT NOT NULL DEFAULT '{}',
                    features_json TEXT NOT NULL DEFAULT '{}',
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL CHECK(status IN ('success', 'error')),
                    error_message TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_history_created_at
                    ON diagnosis_history(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_history_label
                    ON diagnosis_history(label);
                """
            )
            self._initialize_schema_info(connection)

    def _initialize_schema_info(self, connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(schema_info)").fetchall()
        }
        if "singleton" not in columns:
            versions = [
                int(row["version"])
                for row in connection.execute("SELECT version FROM schema_info").fetchall()
            ]
            unsupported = {version for version in versions if version != self.SCHEMA_VERSION}
            if unsupported:
                raise RuntimeError(
                    f"不支持的历史数据库版本：{sorted(unsupported)}"
                )
            connection.execute("ALTER TABLE schema_info RENAME TO schema_info_legacy")
            connection.execute(
                "CREATE TABLE schema_info ("
                "singleton INTEGER PRIMARY KEY CHECK(singleton = 1), "
                "version INTEGER NOT NULL)"
            )
            connection.execute(
                "INSERT INTO schema_info(singleton, version) VALUES (1, ?)",
                (self.SCHEMA_VERSION,),
            )
            connection.execute("DROP TABLE schema_info_legacy")
            return

        rows = connection.execute(
            "SELECT singleton, version FROM schema_info"
        ).fetchall()
        if not rows:
            connection.execute(
                "INSERT INTO schema_info(singleton, version) VALUES (1, ?)",
                (self.SCHEMA_VERSION,),
            )
            return
        if len(rows) != 1 or rows[0]["singleton"] != 1:
            raise RuntimeError("历史数据库版本元数据无效")
        if rows[0]["version"] != self.SCHEMA_VERSION:
            raise RuntimeError(f"不支持的历史数据库版本：{rows[0]['version']}")

    def save_result(self, result: DiagnosisResult) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO diagnosis_history (
                    run_id, created_at, source_id, model_version, class_id, label,
                    confidence, probabilities_json, features_json, warnings_json,
                    status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'success', NULL)
                ON CONFLICT(run_id) DO UPDATE SET
                    created_at = excluded.created_at,
                    source_id = excluded.source_id,
                    model_version = excluded.model_version,
                    class_id = excluded.class_id,
                    label = excluded.label,
                    confidence = excluded.confidence,
                    probabilities_json = excluded.probabilities_json,
                    features_json = excluded.features_json,
                    warnings_json = excluded.warnings_json,
                    status = 'success',
                    error_message = NULL
                """,
                (
                    result.run_id,
                    result.created_at.isoformat(),
                    result.source_id,
                    result.model_version,
                    result.class_id,
                    result.label,
                    result.confidence,
                    json.dumps(dict(result.probabilities), ensure_ascii=False),
                    json.dumps(dict(result.features), ensure_ascii=False),
                    json.dumps(result.warnings, ensure_ascii=False),
                ),
            )

    def save_error(
        self,
        *,
        run_id: str,
        created_at: datetime,
        source_id: str | None,
        model_version: str,
        message: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO diagnosis_history (
                    run_id, created_at, source_id, model_version, class_id, label,
                    confidence, probabilities_json, features_json, warnings_json,
                    status, error_message
                ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, '{}', '{}', '[]', 'error', ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    created_at = excluded.created_at,
                    source_id = excluded.source_id,
                    model_version = excluded.model_version,
                    class_id = NULL,
                    label = NULL,
                    confidence = NULL,
                    probabilities_json = '{}',
                    features_json = '{}',
                    warnings_json = '[]',
                    status = 'error',
                    error_message = excluded.error_message
                """,
                (run_id, created_at.isoformat(), source_id, model_version, message),
            )

    def list(self, *, limit: int = 100, offset: int = 0, query: str = "") -> list[HistoryRecord]:
        if limit < 1 or limit > 1000 or offset < 0:
            raise ValueError("limit 必须为 1..1000，offset 不能为负数")
        sql = "SELECT * FROM diagnosis_history"
        parameters: list[object] = []
        if query.strip():
            sql += " WHERE source_id LIKE ? OR label LIKE ? OR model_version LIKE ?"
            pattern = f"%{query.strip()}%"
            parameters.extend([pattern, pattern, pattern])
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        parameters.extend([limit, offset])
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [self._to_record(row) for row in rows]

    def get(self, run_id: str) -> HistoryRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM diagnosis_history WHERE run_id = ?", (run_id,)
            ).fetchone()
        return None if row is None else self._to_record(row)

    def delete(self, run_ids: Iterable[str]) -> int:
        values = [(value,) for value in run_ids]
        if not values:
            return 0
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany("DELETE FROM diagnosis_history WHERE run_id = ?", values)
            return connection.total_changes - before

    def count(self, *, query: str = "") -> int:
        sql = "SELECT COUNT(*) FROM diagnosis_history"
        parameters: list[object] = []
        if query.strip():
            sql += " WHERE source_id LIKE ? OR label LIKE ? OR model_version LIKE ?"
            pattern = f"%{query.strip()}%"
            parameters.extend([pattern, pattern, pattern])
        with self._connect() as connection:
            return int(connection.execute(sql, parameters).fetchone()[0])

    @staticmethod
    def _to_record(row: sqlite3.Row) -> HistoryRecord:
        return HistoryRecord(
            run_id=row["run_id"],
            created_at=row["created_at"],
            source_id=row["source_id"],
            model_version=row["model_version"],
            class_id=row["class_id"],
            label=row["label"],
            confidence=row["confidence"],
            probabilities=json.loads(row["probabilities_json"]),
            features=json.loads(row["features_json"]),
            warnings=tuple(json.loads(row["warnings_json"])),
            status=row["status"],
            error_message=row["error_message"],
        )
