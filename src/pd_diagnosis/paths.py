from __future__ import annotations

import os
import sysconfig
from pathlib import Path

from platformdirs import user_data_path


def app_data_dir() -> Path:
    path = Path(user_data_path("PartialDischargeDiagnosis", "int-yu"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_database_path() -> Path:
    return app_data_dir() / "diagnosis.sqlite3"


def installed_model_path() -> Path:
    data_root = Path(sysconfig.get_path("data"))
    return data_root / "share" / "partial-discharge-diagnosis" / "models" / "default"


def default_model_path() -> Path:
    configured = os.environ.get("PD_DIAGNOSIS_MODEL")
    if configured:
        return Path(configured).expanduser()

    repository_model = Path.cwd() / "models" / "default"
    if (repository_model / "manifest.json").is_file():
        return repository_model

    return installed_model_path()
