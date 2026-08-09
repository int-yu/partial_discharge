"""Stable public API for partial-discharge diagnosis."""

from .engine import DiagnosisEngine
from .errors import (
    ArtifactCompatibilityError,
    DiagnosisError,
    InvalidSignalError,
)
from .types import (
    BatchDiagnosisItem,
    BatchDiagnosisResult,
    DiagnosisResult,
    Signal,
)

__all__ = [
    "ArtifactCompatibilityError",
    "BatchDiagnosisItem",
    "BatchDiagnosisResult",
    "DiagnosisEngine",
    "DiagnosisError",
    "DiagnosisResult",
    "InvalidSignalError",
    "Signal",
]

__version__ = "0.1.0"
