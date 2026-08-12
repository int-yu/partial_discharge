from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .engine import DiagnosisEngine
from .errors import DiagnosisError
from .storage import HistoryRepository
from .types import DiagnosisResult, Pathish, Signal


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
        self._save_result(result)
        return result

    def diagnose_file(self, path: Pathish) -> DiagnosisResult:
        source = str(Path(path).resolve())
        try:
            result = self.engine.diagnose_file(path)
        except DiagnosisError as exc:
            self._save_error(source, str(exc))
            raise
        self._save_result(result)
        return result

    def _save_result(self, result: DiagnosisResult) -> None:
        if self.history is not None:
            self.history.save_result(result)

    def _save_error(self, source_id: str | None, message: str) -> None:
        if self.history is not None:
            self.history.save_error(
                run_id=str(uuid4()),
                created_at=datetime.now(timezone.utc),
                source_id=source_id,
                model_version=self.engine.bundle.model_version,
                message=message,
            )
