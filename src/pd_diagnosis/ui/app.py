from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QLocale, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen

from ..engine import DiagnosisEngine
from ..logging_config import configure_logging
from ..paths import default_database_path, default_model_path
from ..service import DiagnosisService
from ..storage import HistoryRepository
from .theme import ensure_chinese_font

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    log_path = configure_logging()
    application = QApplication(list(argv) if argv is not None else sys.argv)
    application.setApplicationName("局部放电类型智能诊断")
    application.setOrganizationName("int-yu")
    application.setStyle("Fusion")
    QLocale.setDefault(QLocale(QLocale.Chinese, QLocale.China))
    application.setFont(QFont(ensure_chinese_font(), 11))

    splash = _create_splash()
    splash.show()
    application.processEvents()
    model_path = default_model_path().resolve()
    database_path = default_database_path()
    logger.info(
        "application_start python=%s platform=%s model_path=%s database_path=%s log_path=%s",
        platform.python_version(),
        platform.platform(),
        model_path,
        database_path,
        log_path,
    )
    try:
        splash.showMessage(
            "正在校验并加载诊断模型…",
            Qt.AlignHCenter | Qt.AlignBottom,
            QColor("#5D6B7E"),
        )
        application.processEvents()
        engine = DiagnosisEngine.from_bundle(model_path)
        history = HistoryRepository(database_path)
        service = DiagnosisService(engine, history)
    except Exception as exc:
        logger.exception("application_start_failed model_path=%s", model_path)
        splash.close()
        QMessageBox.critical(
            None,
            "应用启动失败",
            f"无法加载模型 bundle：\n{model_path}\n\n{exc}\n\n"
            "可设置 PD_DIAGNOSIS_MODEL 环境变量指定模型目录。",
        )
        return 1

    from .main_window import MainWindow

    window = MainWindow(service, history, model_path=model_path)
    window.show()
    splash.finish(window)
    return application.exec()


def _create_splash() -> QSplashScreen:
    pixmap = QPixmap(540, 220)
    pixmap.fill(QColor("#F4F7FB"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor("#087EA4"))
    painter.setFont(QFont("Microsoft YaHei UI", 20, QFont.DemiBold))
    painter.drawText(0, 55, 540, 55, Qt.AlignCenter, "局部放电类型智能诊断")
    painter.setPen(QColor("#5D6B7E"))
    painter.setFont(QFont("Microsoft YaHei UI", 11))
    painter.drawText(0, 105, 540, 35, Qt.AlignCenter, "正在准备诊断工作台")
    painter.end()
    splash = QSplashScreen(pixmap)
    splash.setWindowFlag(Qt.WindowStaysOnTopHint)
    return splash


if __name__ == "__main__":
    raise SystemExit(main())
