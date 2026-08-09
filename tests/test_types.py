from __future__ import annotations

import pytest

from pd_diagnosis.types import BatchDiagnosisItem


def test_batch_item_rejects_missing_result_and_error():
    with pytest.raises(ValueError, match="result.*error"):
        BatchDiagnosisItem(source="signal.txt")


def test_batch_item_rejects_result_and_error_together(engine):
    result = engine.diagnose([0.0] * 100)

    with pytest.raises(ValueError, match="result.*error"):
        BatchDiagnosisItem(source="signal.txt", result=result, error="failed")


def test_batch_item_accepts_exactly_one_outcome(engine):
    result = engine.diagnose([0.0] * 100)

    success = BatchDiagnosisItem(source="signal.txt", result=result)
    failure = BatchDiagnosisItem(source="signal.txt", error="failed")

    assert success.succeeded
    assert not failure.succeeded
