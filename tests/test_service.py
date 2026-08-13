from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from pd_diagnosis import InvalidSignalError, Signal
from pd_diagnosis.service import DiagnosisService


class _FailingHistory:
    def save_result(self, result):
        raise sqlite3.OperationalError("database is locked")

    def save_error(self, **kwargs):
        raise sqlite3.OperationalError("database is locked")


def test_persistence_failure_does_not_discard_successful_diagnosis(engine, caplog):
    service = DiagnosisService(engine, _FailingHistory())

    result = service.diagnose(Signal([0.0] * 100, source_id="memory-signal"))

    assert result.label
    assert any("历史记录保存失败" in warning for warning in result.warnings)
    assert "database is locked" in caplog.text


def test_error_persistence_failure_preserves_original_diagnosis_error(caplog):
    original = InvalidSignalError("bad signal")

    class FailingEngine:
        bundle = SimpleNamespace(model_version="test-model")

        def diagnose(self, signal):
            raise original

    service = DiagnosisService(FailingEngine(), _FailingHistory())

    with pytest.raises(InvalidSignalError) as captured:
        service.diagnose(Signal([0.0] * 100, source_id="broken-signal"))

    assert captured.value is original
    assert "database is locked" in caplog.text
