from __future__ import annotations

import os

import numpy as np


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "QtAgg")


def test_main_window_renders_result(engine, project_root, tmp_path):
    from PySide6.QtCore import QLocale, QSettings
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from pd_diagnosis.service import DiagnosisService
    from pd_diagnosis.signal_io import read_txt_signal
    from pd_diagnosis.storage import HistoryRepository
    from pd_diagnosis.ui.main_window import MainWindow
    from pd_diagnosis.ui.theme import ensure_chinese_font
    from pd_diagnosis.ui.workers import SingleDiagnosisOutcome

    application = QApplication.instance() or QApplication([])
    application.setFont(QFont(ensure_chinese_font(), 11))
    settings = QSettings(str(tmp_path / "ui.ini"), QSettings.IniFormat)
    settings.setValue("ui/dark_theme", True)
    history = HistoryRepository(tmp_path / "ui.sqlite3")
    window = MainWindow(
        DiagnosisService(engine, history),
        history,
        model_path=project_root / "models" / "default",
        settings=settings,
    )
    path = project_root / "data" / "train" / "0" / "a1.txt"
    samples = read_txt_signal(path)
    samples.setflags(write=False)
    received = []
    window.waveform_canvas.plot_signal = lambda values: received.append(values)
    window.single_path.setText(str(path))
    outcome = SingleDiagnosisOutcome(
        path=str(path),
        samples=samples,
        result=engine.diagnose(samples),
    )
    window.single_path.setText(str(tmp_path / "changed-after-start.txt"))
    window._show_single_result(outcome)

    assert window.minimumWidth() == 1024
    assert window.navigation.count() == 4
    assert window.thread_pool.maxThreadCount() == 1
    assert window.dark_theme
    assert window.theme_combo.currentIndex() == 1
    assert engine.bundle.feature_schema in window.model_contract_label.text()
    assert QLocale().toString(engine.bundle.sampling_rate_hz) in window.model_contract_label.text()
    for widget in (
        window.navigation,
        window.single_path,
        window.batch_path,
        window.feature_table,
        window.batch_table,
        window.history_table,
        window.waveform_canvas,
        window.prpd_canvas,
        window.probability_canvas,
        window.result_label,
    ):
        assert widget.accessibleName()
    assert len(received) == 1
    np.testing.assert_array_equal(received[0], samples)
    window._set_single_running(True)
    assert not window.single_path.isEnabled()
    assert not window.single_browse.isEnabled()
    assert not window.diagnose_button.isEnabled()
    window._finish_single()
    assert window.single_path.isEnabled()
    assert window.single_browse.isEnabled()
    assert window.diagnose_button.isEnabled()
    assert window.result_label.text() == "金属突出物缺陷"
    assert window.feature_table.item(2, 4).text() == "偏度"
    window.close()
    settings.sync()
    assert settings.value("window/geometry") is not None
    assert settings.value("window/diagnosis_splitter") is not None


def test_history_pagination_and_query_reset(engine, project_root, tmp_path):
    from datetime import datetime, timezone

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from pd_diagnosis.service import DiagnosisService
    from pd_diagnosis.storage import HistoryRepository
    from pd_diagnosis.ui.main_window import MainWindow

    QApplication.instance() or QApplication([])
    history = HistoryRepository(tmp_path / "pages.sqlite3")
    for index in range(205):
        history.save_error(
            run_id=f"run-{index:03d}",
            created_at=datetime.now(timezone.utc),
            source_id=f"source-{index:03d}.txt",
            model_version="test",
            message="bad input",
        )
    window = MainWindow(
        DiagnosisService(engine, history),
        history,
        model_path=project_root / "models" / "default",
        settings=QSettings(str(tmp_path / "pages.ini"), QSettings.IniFormat),
    )

    assert window.history_table.rowCount() == 100
    assert not window.history_previous.isEnabled()
    assert window.history_next.isEnabled()

    window._next_history_page()
    window._next_history_page()

    assert window.history_offset == 200
    assert window.history_table.rowCount() == 5
    assert window.history_previous.isEnabled()
    assert not window.history_next.isEnabled()

    window.history_query.setText("source-000")
    window._search_history()

    assert window.history_offset == 0
    assert window.history_table.rowCount() == 1
    window.close()
