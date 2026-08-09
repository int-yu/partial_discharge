from __future__ import annotations

import sys
from collections.abc import Callable, Sequence

ApplicationMain = Callable[[Sequence[str] | None], int]


def _load_application() -> ApplicationMain:
    from .ui.app import main as application_main

    return application_main


def main(argv: Sequence[str] | None = None) -> int:
    try:
        application_main = _load_application()
    except ModuleNotFoundError as error:
        missing_module = error.name or ""
        if missing_module == "PySide6" or missing_module.startswith("matplotlib"):
            print(
                "桌面界面依赖未安装（缺少 "
                f"{missing_module}）。请在项目目录运行：\n"
                '  pip install -e ".[gui]"',
                file=sys.stderr,
            )
            return 2
        raise

    return application_main(argv)
