from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 CI path
    import tomli as tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _pyproject():
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as stream:
        return tomllib.load(stream)


def test_pyproject_declares_quality_typing_and_repository_contract():
    config = _pyproject()
    project = config["project"]
    dev = project["optional-dependencies"]["dev"]

    assert project["urls"]["Repository"] == "https://github.com/int-yu/partial_discharge"
    assert "license" not in project
    assert any(requirement.startswith("ruff") for requirement in dev)
    assert any(requirement.startswith("mypy") for requirement in dev)
    assert "ruff" in config["tool"]
    assert "mypy" in config["tool"]
    assert config["tool"]["setuptools"]["package-data"]["pd_diagnosis"] == ["py.typed"]
    assert (PROJECT_ROOT / "src" / "pd_diagnosis" / "py.typed").is_file()
    installed_files = config["tool"]["setuptools"]["data-files"][
        "share/partial-discharge-diagnosis/models/default"
    ]
    assert {Path(value).name for value in installed_files} == {
        "manifest.json",
        "scaler.npz",
        "weights.pth",
    }


def test_windows_ci_matrix_runs_all_quality_gates():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "windows-latest" in workflow
    for version in ('"3.10"', '"3.11"', '"3.12"'):
        assert version in workflow
    assert 'pip install -e ".[gui,dev]"' in workflow
    assert "ruff check ." in workflow
    assert "mypy src/pd_diagnosis" in workflow
    assert "pytest" in workflow
    assert "QT_QPA_PLATFORM: offscreen" in workflow
    assert "MPLBACKEND: QtAgg" in workflow
