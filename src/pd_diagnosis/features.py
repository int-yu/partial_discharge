from __future__ import annotations

from collections import OrderedDict
from typing import Mapping, Sequence

import numpy as np

from .errors import InvalidSignalError

FEATURE_NAMES = (
    "最大值(mV)",
    "峰峰值(mV)",
    "脉冲均值(V)",
    "脉冲方差",
    "频谱主频率(Hz)",
    "频谱主频率峰值(V)",
    "频谱均值(V)",
    "频谱方差",
    "峰度",
    "偏度",
)

FEATURE_SCHEMA = "legacy-v1"


def validate_signal(samples: Sequence[float], *, min_samples: int = 100) -> np.ndarray:
    try:
        values = np.asarray(samples, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise InvalidSignalError("信号必须是一维数值序列") from exc
    if values.ndim != 1:
        raise InvalidSignalError(f"信号必须是一维数组，当前维度为 {values.ndim}")
    if values.size < min_samples:
        raise InvalidSignalError(f"信号至少需要 {min_samples} 个采样点，当前为 {values.size}")
    invalid = np.flatnonzero(~np.isfinite(values))
    if invalid.size:
        raise InvalidSignalError(f"第 {int(invalid[0]) + 1} 个采样点不是有限数值")
    return values


def extract_feature_vector(
    samples: Sequence[float],
    *,
    sampling_rate_hz: int = 1_000_000,
    min_samples: int = 100,
) -> np.ndarray:
    """Extract the ten legacy-v1 features without changing model behaviour."""
    signal = validate_signal(samples, min_samples=min_samples)
    if sampling_rate_hz <= 0:
        raise InvalidSignalError("采样率必须为正整数")

    count = len(signal)
    maximum = np.max(signal) * 1000
    peak_to_peak = (np.max(signal) - np.min(signal)) * 1000
    pulse_mean = np.mean(signal)
    pulse_variance = np.var(signal)

    dominant_frequency = 0.0
    dominant_peak = 0.0
    spectral_mean = 0.0
    spectral_variance = 0.0
    if count > 1:
        fft_magnitude = np.abs(np.fft.fft(signal)) / count
        frequencies = np.fft.fftfreq(count, 1 / sampling_rate_hz)
        positive = frequencies > 0
        positive_frequencies = frequencies[positive]
        positive_magnitude = fft_magnitude[positive]
        if len(positive_magnitude):
            dominant_index = int(np.argmax(positive_magnitude))
            dominant_frequency = positive_frequencies[dominant_index]
            dominant_peak = positive_magnitude[dominant_index]
            spectral_mean = np.mean(positive_magnitude)
            spectral_variance = np.var(positive_magnitude)

    standard_deviation = np.std(signal)
    kurtosis = (
        np.mean((signal - np.mean(signal)) ** 4) / (standard_deviation**4 + 1e-10) - 3
        if count > 3
        else 0.0
    )
    skewness = (
        np.mean((signal - np.mean(signal)) ** 3) / (standard_deviation**3 + 1e-10)
        if count > 1
        else 0.0
    )

    return np.asarray(
        [
            maximum,
            peak_to_peak,
            pulse_mean,
            pulse_variance,
            dominant_frequency,
            dominant_peak,
            spectral_mean,
            spectral_variance,
            kurtosis,
            skewness,
        ],
        dtype=np.float32,
    )


def feature_mapping(vector: Sequence[float]) -> Mapping[str, float]:
    if len(vector) != len(FEATURE_NAMES):
        raise ValueError(f"Expected {len(FEATURE_NAMES)} features, got {len(vector)}")
    return OrderedDict((name, float(value)) for name, value in zip(FEATURE_NAMES, vector))
