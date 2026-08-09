from __future__ import annotations

import os

import numpy as np


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "QtAgg")


def test_main_window_renders_result(engine, project_root, tmp_path):
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
    history = HistoryRepository(tmp_path / "ui.sqlite3")
    window = MainWindow(
        DiagnosisService(engine, history),
        history,
        model_path=project_root / "models" / "default",
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
