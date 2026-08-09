from __future__ import annotations

from pathlib import Path

import pd_diagnosis.paths as paths


def test_default_model_path_prefers_environment(monkeypatch, tmp_path: Path) -> None:
    configured = tmp_path / "configured-model"
    monkeypatch.setenv("PD_DIAGNOSIS_MODEL", str(configured))

    assert paths.default_model_path() == configured


def test_default_model_path_prefers_repository_model(monkeypatch, tmp_path: Path) -> None:
    repository_model = tmp_path / "models" / "default"
    repository_model.mkdir(parents=True)
    (repository_model / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.delenv("PD_DIAGNOSIS_MODEL", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paths, "installed_model_path", lambda: tmp_path / "installed-model")

    assert paths.default_model_path() == repository_model


def test_default_model_path_falls_back_to_installed_data(monkeypatch, tmp_path: Path) -> None:
    installed_model = tmp_path / "installed" / "models" / "default"
    installed_model.mkdir(parents=True)
    (installed_model / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.delenv("PD_DIAGNOSIS_MODEL", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paths, "installed_model_path", lambda: installed_model)

    assert paths.default_model_path() == installed_model
