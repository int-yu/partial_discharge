from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from ..storage import HistoryRecord

HISTORY_CSV_FIELDS = (
    "时间",
    "来源",
    "模型建议",
    "置信度",
    "模型版本",
    "状态",
    "错误",
)


def export_history_csv(records: Iterable[HistoryRecord], path: Path) -> int:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with destination.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HISTORY_CSV_FIELDS)
        for record in records:
            writer.writerow(
                [
                    record.created_at,
                    record.source_id,
                    record.label,
                    record.confidence,
                    record.model_version,
                    record.status,
                    record.error_message,
                ]
            )
            count += 1
    return count
