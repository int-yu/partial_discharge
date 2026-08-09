import os
import subprocess
import sys


def test_public_api_does_not_import_qt(project_root):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root / "src")
    command = (
        "import builtins, sys; "
        "original_import = builtins.__import__; "
        "builtins.__import__ = lambda name, *args, **kwargs: "
        "(_ for _ in ()).throw(AssertionError('SDK attempted GUI import')) "
        "if name.startswith(('PySide6', 'matplotlib')) "
        "else original_import(name, *args, **kwargs); "
        "import pd_diagnosis; "
        "assert not any(name.startswith('PySide6') for name in sys.modules)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", command],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
