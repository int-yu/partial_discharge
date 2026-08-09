from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Event

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ..service import DiagnosisService
from ..signal_io import read_txt_signal
from ..types import BatchDiagnosisItem, DiagnosisResult, Signal as DiagnosisSignal

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SingleDiagnosisOutcome:
    path: str
    samples: np.ndarray
    result: DiagnosisResult

    def __post_init__(self) -> None:
        snapshot = np.array(self.samples, dtype=np.float32, copy=True)
        snapshot.setflags(write=False)
        object.__setattr__(self, "samples", snapshot)


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
            source = Path(self.path)
            samples = np.array(read_txt_signal(source), dtype=np.float32, copy=True)
            samples.setflags(write=False)
            result = self.service.diagnose(
                DiagnosisSignal(
                    samples,
                    sampling_rate_hz=self.service.engine.bundle.sampling_rate_hz,
                    source_id=str(source.resolve()),
                )
            )
            self.signals.result.emit(
                SingleDiagnosisOutcome(path=self.path, samples=samples, result=result)
            )
        except Exception as exc:
            logger.exception("single_diagnosis_failed path=%s", self.path)
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
                logger.exception(
                    "batch_diagnosis_item_failed index=%s path=%s", index, path
                )
                item = BatchDiagnosisItem(source=path, error=str(exc))
            self.signals.item.emit(index, item)
            self.signals.progress.emit(index + 1, total)
        self.signals.finished.emit()
