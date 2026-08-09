from __future__ import annotations

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "QtAgg")


def test_main_window_renders_result(engine, project_root, tmp_path):
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from pd_diagnosis.service import DiagnosisService
    from pd_diagnosis.storage import HistoryRepository
    from pd_diagnosis.ui.main_window import MainWindow
    from pd_diagnosis.ui.theme import ensure_chinese_font

    application = QApplication.instance() or QApplication([])
    application.setFont(QFont(ensure_chinese_font(), 11))
    history = HistoryRepository(tmp_path / "ui.sqlite3")
    window = MainWindow(
        DiagnosisService(engine, history),
        history,
        model_path=project_root / "models" / "default",
    )
    path = project_root / "data" / "train" / "0" / "a1.txt"
    window.single_path.setText(str(path))
    window._show_single_result(engine.diagnose_file(path))

    assert window.minimumWidth() == 1024
    assert window.navigation.count() == 4
    assert window.result_label.text() == "金属突出物缺陷"
    assert window.feature_table.item(2, 4).text() == "偏度"
    window.close()
