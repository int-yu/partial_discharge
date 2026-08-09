from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "QtAgg")


def test_single_worker_reads_once_persists_once_and_emits_immutable_outcome(
    engine, monkeypatch, tmp_path
):
    from PySide6.QtWidgets import QApplication

    import pd_diagnosis.ui.workers as workers
    from pd_diagnosis.service import DiagnosisService
    from pd_diagnosis.storage import HistoryRepository
    from pd_diagnosis.ui.workers import SingleDiagnosisTask

    QApplication.instance() or QApplication([])
    repository = HistoryRepository(tmp_path / "worker.sqlite3")
    service = DiagnosisService(engine, repository)
    selected_path = str(tmp_path / "selected.txt")
    snapshot = np.linspace(-1.0, 1.0, 100, dtype=np.float32)
    reads: list[str] = []

    def read_once(path):
        reads.append(str(path))
        return snapshot

    monkeypatch.setattr(workers, "read_txt_signal", read_once)
    outcomes = []
    errors = []
    task = SingleDiagnosisTask(service, selected_path)
    task.signals.result.connect(outcomes.append)
    task.signals.error.connect(errors.append)

    task.run()

    assert errors == []
    assert reads == [selected_path]
    assert repository.count() == 1
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.path == selected_path
    np.testing.assert_array_equal(outcome.samples, snapshot)
    assert not outcome.samples.flags.writeable
    with pytest.raises(ValueError):
        outcome.samples[0] = 99.0
