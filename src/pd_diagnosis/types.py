from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from os import PathLike
from typing import Mapping, Sequence
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Signal:
    samples: Sequence[float]
    sampling_rate_hz: int = 1_000_000
    source_id: str | None = None


@dataclass(frozen=True, slots=True)
class DiagnosisResult:
    class_id: int
    label: str
    confidence: float
    probabilities: Mapping[str, float]
    features: Mapping[str, float]
    model_version: str
    source_id: str | None = None
    warnings: tuple[str, ...] = ()
    run_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class BatchDiagnosisItem:
    source: str
    result: DiagnosisResult | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.result is not None


@dataclass(frozen=True, slots=True)
class BatchDiagnosisResult:
    items: tuple[BatchDiagnosisItem, ...]

    @property
    def succeeded(self) -> int:
        return sum(item.succeeded for item in self.items)

    @property
    def failed(self) -> int:
        return len(self.items) - self.succeeded


Pathish = str | PathLike[str]
