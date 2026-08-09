from __future__ import annotations

import logging
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .engine import DiagnosisEngine
from .errors import DiagnosisError, PersistenceWarning
from .storage import HistoryRepository
from .types import DiagnosisResult, Pathish, Signal

logger = logging.getLogger(__name__)
PERSISTENCE_WARNING_TEXT = str(
    PersistenceWarning("诊断已完成，但历史记录保存失败；诊断结果仍然有效，请检查日志。")
)
PERSISTENCE_EXCEPTIONS = (sqlite3.Error, OSError)


class DiagnosisService:
    """Application service that combines the pure SDK with optional persistence."""

    def __init__(self, engine: DiagnosisEngine, history: HistoryRepository | None = None) -> None:
        self.engine = engine
        self.history = history

    def diagnose(self, signal: Signal) -> DiagnosisResult:
        try:
            result = self.engine.diagnose(signal)
        except DiagnosisError as exc:
            self._save_error(signal.source_id, str(exc))
            raise
        return self._save_result(result)

    def diagnose_file(self, path: Pathish) -> DiagnosisResult:
        source = str(Path(path).resolve())
        try:
            result = self.engine.diagnose_file(path)
        except DiagnosisError as exc:
            self._save_error(source, str(exc))
            raise
        return self._save_result(result)

    def _save_result(self, result: DiagnosisResult) -> DiagnosisResult:
        if self.history is None:
            return result
        try:
            self.history.save_result(result)
        except PERSISTENCE_EXCEPTIONS:
            logger.exception(
                "history_save_result_failed run_id=%s source_id=%s",
                result.run_id,
                result.source_id,
            )
            return replace(
                result,
                warnings=(*result.warnings, PERSISTENCE_WARNING_TEXT),
            )
        return result

    def _save_error(self, source_id: str | None, message: str) -> None:
        if self.history is None:
            return
        run_id = str(uuid4())
        try:
            self.history.save_error(
                run_id=run_id,
                created_at=datetime.now(timezone.utc),
                source_id=source_id,
                model_version=self.engine.bundle.model_version,
                message=message,
            )
        except PERSISTENCE_EXCEPTIONS:
            logger.exception(
                "history_save_error_failed run_id=%s source_id=%s",
                run_id,
                source_id,
            )
