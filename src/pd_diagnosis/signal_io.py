from __future__ import annotations

from pathlib import Path

import numpy as np

from .errors import InvalidSignalError
from .types import Pathish


def read_txt_signal(path: Pathish) -> np.ndarray:
    source = Path(path)
    if source.suffix.lower() != ".txt":
        raise InvalidSignalError(f"正式文件接口仅支持 TXT：{source.name}")
    if not source.is_file():
        raise InvalidSignalError(f"信号文件不存在：{source}")
    try:
        text = source.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidSignalError(f"TXT 必须使用 UTF-8 或 ASCII 编码：{source}") from exc
    values: list[float] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for token_number, token in enumerate(line.split(), start=1):
            try:
                values.append(float(token))
            except ValueError as exc:
                raise InvalidSignalError(
                    f"第 {line_number} 行第 {token_number} 个值不是数字：{token!r}"
                ) from exc
    if not values:
        raise InvalidSignalError(f"信号文件为空：{source}")
    return np.asarray(values, dtype=np.float32)
