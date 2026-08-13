from __future__ import annotations

import pd_diagnosis.launcher as launcher


def test_launcher_reports_missing_gui_dependencies(monkeypatch, capsys) -> None:
    def missing_gui():
        raise ModuleNotFoundError("No module named 'PySide6'", name="PySide6")

    monkeypatch.setattr(launcher, "_load_application", missing_gui)

    assert launcher.main(["--demo"]) == 2
    error = capsys.readouterr().err
    assert "PySide6" in error
    assert 'pip install -e ".[gui]"' in error


def test_launcher_delegates_arguments_and_exit_code(monkeypatch) -> None:
    received: list[list[str] | None] = []

    def application(argv):
        received.append(argv)
        return 7

    monkeypatch.setattr(launcher, "_load_application", lambda: application)

    assert launcher.main(["--demo"]) == 7
    assert received == [["--demo"]]
