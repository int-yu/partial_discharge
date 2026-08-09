from __future__ import annotations

import numpy as np

from .features import validate_signal


def generate_prpd_matrix(
    samples: np.ndarray,
    *,
    sampling_rate_hz: int = 1_000_000,
    mains_frequency_hz: float = 50.0,
    phase_bins: int = 72,
    amplitude_bins: int = 60,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a visualization-only PRPD histogram from prominent pulse samples."""
    values = validate_signal(samples)
    threshold = float(np.percentile(np.abs(values), 95))
    indices = np.flatnonzero(np.abs(values) >= threshold)
    if not len(indices):
        indices = np.arange(len(values))
    phases = (indices / sampling_rate_hz * mains_frequency_hz * 360.0) % 360.0
    amplitudes = np.abs(values[indices])
    max_amplitude = max(float(np.max(amplitudes)), 1.0)
    matrix, phase_edges, amplitude_edges = np.histogram2d(
        phases,
        amplitudes,
        bins=(phase_bins, amplitude_bins),
        range=((0.0, 360.0), (0.0, max_amplitude * 1.05)),
    )
    return phase_edges, amplitude_edges, matrix
