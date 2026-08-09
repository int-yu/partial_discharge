"""Stable public API for partial-discharge diagnosis."""

from .engine import DiagnosisEngine
from .errors import (
    ArtifactCompatibilityError,
    DiagnosisError,
    InvalidSignalError,
    PersistenceWarning,
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
    "PersistenceWarning",
    "Signal",
]

__version__ = "0.1.0"
