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


def test_history_export_worker_reports_progress_result_error_and_finish(
    monkeypatch, tmp_path
):
    from datetime import datetime, timezone

    import pd_diagnosis.ui.workers as workers
    from pd_diagnosis.storage import HistoryRepository
    from pd_diagnosis.ui.workers import HistoryExportTask

    repository = HistoryRepository(tmp_path / "export.sqlite3")
    repository.save_error(
        run_id="failed-run",
        created_at=datetime.now(timezone.utc),
        source_id="broken.txt",
        model_version="test",
        message="输入无效",
    )
    output = tmp_path / "history.csv"
    task = HistoryExportTask(repository, output)
    progress = []
    results = []
    errors = []
    finished = []
    task.signals.progress.connect(lambda done, total: progress.append((done, total)))
    task.signals.result.connect(results.append)
    task.signals.error.connect(errors.append)
    task.signals.finished.connect(lambda: finished.append(True))

    task.run()

    assert errors == []
    assert progress[-1] == (1, 1)
    assert results[0].path == output.resolve()
    assert results[0].count == 1
    assert finished == [True]

    monkeypatch.setattr(
        workers,
        "export_history_csv",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    failing = HistoryExportTask(repository, tmp_path / "failed.csv")
    failing_errors = []
    failing_finished = []
    failing.signals.error.connect(failing_errors.append)
    failing.signals.finished.connect(lambda: failing_finished.append(True))

    failing.run()

    assert "disk full" in failing_errors[0]
    assert failing_finished == [True]
