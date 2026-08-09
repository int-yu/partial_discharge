from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ..service import DiagnosisService
from ..types import BatchDiagnosisItem


class TaskSignals(QObject):
    result = Signal(object)
    item = Signal(int, object)
    progress = Signal(int, int)
    error = Signal(str)
    finished = Signal()


class SingleDiagnosisTask(QRunnable):
    def __init__(self, service: DiagnosisService, path: str) -> None:
        super().__init__()
        self.service = service
        self.path = path
        self.signals = TaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.result.emit(self.service.diagnose_file(self.path))
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class BatchDiagnosisTask(QRunnable):
    def __init__(self, service: DiagnosisService, paths: list[str]) -> None:
        super().__init__()
        self.service = service
        self.paths = paths
        self.signals = TaskSignals()
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @Slot()
    def run(self) -> None:
        total = len(self.paths)
        for index, path in enumerate(self.paths):
            if self._cancelled.is_set():
                break
            try:
                item = BatchDiagnosisItem(source=path, result=self.service.diagnose_file(path))
            except Exception as exc:
                item = BatchDiagnosisItem(source=path, error=str(exc))
            self.signals.item.emit(index, item)
            self.signals.progress.emit(index + 1, total)
        self.signals.finished.emit()
