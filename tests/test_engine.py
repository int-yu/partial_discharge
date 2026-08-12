from __future__ import annotations

import numpy as np
import pytest

from pd_diagnosis import InvalidSignalError, Signal


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
