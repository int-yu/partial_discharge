from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from pd_diagnosis.logging_config import configure_logging


def test_configure_logging_creates_utf8_rotating_log(tmp_path):
    log_path = tmp_path / "logs" / "application.log"

    configured = configure_logging(log_path)
    logger = logging.getLogger("pd_diagnosis.test")
    logger.warning("日志初始化测试")
    for handler in logging.getLogger("pd_diagnosis").handlers:
        handler.flush()

    assert configured == log_path.resolve()
    assert "日志初始化测试" in log_path.read_text(encoding="utf-8")
    assert any(
        isinstance(handler, RotatingFileHandler)
        for handler in logging.getLogger("pd_diagnosis").handlers
    )
