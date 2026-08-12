from __future__ import annotations

from pathlib import Path

import pytest

from pd_diagnosis import DiagnosisEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def engine(project_root: Path) -> DiagnosisEngine:
    return DiagnosisEngine.from_bundle(project_root / "models" / "default", device="cpu")
