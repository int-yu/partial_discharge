from __future__ import annotations

import numpy as np
import pytest

from pd_diagnosis.errors import InvalidSignalError
from pd_diagnosis.features import extract_feature_vector, validate_signal
from pd_diagnosis.signal_io import read_txt_signal


def test_legacy_feature_vector_matches_golden_sample(project_root):
    samples = read_txt_signal(project_root / "data" / "train" / "0" / "a1.txt")
    actual = extract_feature_vector(samples)
    expected = np.asarray(
        [
            380000.0,
            952000.0,
            13.52079963684082,
            5290.76220703125,
            12900.0,
            10.580836296081543,
            0.44573041796684265,
            0.33050209283828735,
            3.387695074081421,
            -0.36419668793678284,
        ],
        dtype=np.float32,
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-6)


@pytest.mark.parametrize(
    "samples, message",
    [
        ([1.0] * 99, "至少需要 100"),
        ([[1.0] * 100], "一维数组"),
        ([1.0] * 99 + [float("nan")], "不是有限数值"),
    ],
)
def test_invalid_signal_is_rejected(samples, message):
    with pytest.raises(InvalidSignalError, match=message):
        validate_signal(samples)
