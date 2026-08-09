from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
import torch

import pd_diagnosis.engine as engine_module
from pd_diagnosis import DiagnosisEngine, DiagnosisError, InvalidSignalError, Signal
from pd_diagnosis.features import FEATURE_NAMES

GOLDEN = {
    "0/a1.txt": (0, [0.9635154009, 0.0097595816, 0.0115856454, 0.0151393125]),
    "1/b1.txt": (1, [0.0169856548, 0.9475414157, 0.0147483377, 0.0207247119]),
    "2/c1.txt": (2, [0.0105654420, 0.0090924371, 0.9713428020, 0.0089993328]),
    "3/d1.txt": (3, [0.0074817995, 0.0277054328, 0.0097404867, 0.9550722837]),
}


@pytest.mark.parametrize("relative, expected", GOLDEN.items())
def test_migrated_bundle_matches_legacy_probabilities(engine, project_root, relative, expected):
    class_id, probabilities = expected
    result = engine.diagnose_file(project_root / "data" / "train" / relative)
    assert result.class_id == class_id
    np.testing.assert_allclose(
        list(result.probabilities.values()), probabilities, rtol=2e-6, atol=2e-7
    )


def test_sampling_rate_must_match_bundle(engine):
    with pytest.raises(InvalidSignalError, match="模型要求 1000000 Hz"):
        engine.diagnose(Signal([1.0] * 100, sampling_rate_hz=500_000))


def test_batch_continues_after_invalid_file(engine, project_root, tmp_path):
    invalid = tmp_path / "short.txt"
    invalid.write_text("1 2 3", encoding="utf-8")
    valid = project_root / "data" / "train" / "0" / "a1.txt"
    result = engine.diagnose_files([invalid, valid])
    assert result.failed == 1
    assert result.succeeded == 1
    assert result.items[0].error
    assert result.items[1].result.class_id == 0


def test_engine_rejects_non_finite_features(engine, monkeypatch):
    features = np.zeros(len(FEATURE_NAMES), dtype=np.float32)
    features[0] = np.nan
    monkeypatch.setattr(engine_module, "extract_feature_vector", lambda *args, **kwargs: features)

    with pytest.raises(DiagnosisError, match="特征.*有限"):
        engine.diagnose([0.0] * 100)


def test_engine_rejects_non_finite_normalized_inputs(engine, monkeypatch):
    features = np.full(len(FEATURE_NAMES), np.finfo(np.float32).max, dtype=np.float32)
    bundle = replace(
        engine.bundle,
        scaler_mean=np.zeros(len(FEATURE_NAMES), dtype=np.float64),
        scaler_scale=np.full(len(FEATURE_NAMES), np.finfo(np.float32).tiny),
    )
    guarded_engine = DiagnosisEngine(bundle, engine._model, engine.device)
    monkeypatch.setattr(engine_module, "extract_feature_vector", lambda *args, **kwargs: features)

    with pytest.raises(DiagnosisError, match="标准化.*有限"):
        guarded_engine.diagnose([0.0] * 100)


class _StaticModel(torch.nn.Module):
    def __init__(self, output):
        super().__init__()
        self.output = output

    def forward(self, values):
        return self.output.to(values.device)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf")])
def test_engine_rejects_non_finite_logits(engine, bad_value):
    logits = torch.zeros((1, len(engine.bundle.classes)), dtype=torch.float32)
    logits[0, 0] = bad_value
    guarded_engine = DiagnosisEngine(engine.bundle, _StaticModel(logits), engine.device)

    with pytest.raises(DiagnosisError, match="logits.*有限"):
        guarded_engine.diagnose([0.0] * 100)


def test_engine_rejects_non_finite_probabilities(engine, monkeypatch):
    logits = torch.zeros((1, len(engine.bundle.classes)), dtype=torch.float32)
    guarded_engine = DiagnosisEngine(engine.bundle, _StaticModel(logits), engine.device)
    monkeypatch.setattr(
        engine_module.torch,
        "softmax",
        lambda *args, **kwargs: torch.full_like(logits, float("nan")),
    )

    with pytest.raises(DiagnosisError, match="概率.*有限"):
        guarded_engine.diagnose([0.0] * 100)


def test_engine_uses_bundle_confidence_warning_threshold(engine):
    guarded_engine = DiagnosisEngine(
        replace(engine.bundle, confidence_warning_threshold=1.0),
        engine._model,
        engine.device,
    )

    result = guarded_engine.diagnose([0.0] * 100)

    assert result.warnings
