from __future__ import annotations

import csv
from datetime import datetime, timezone

from pd_diagnosis.storage import HistoryRecord
from pd_diagnosis.ui.history_export import export_history_csv


def test_export_history_csv_writes_bom_order_quotes_and_count(tmp_path):
    record = HistoryRecord(
        run_id="run-1",
        created_at=datetime(2026, 8, 10, tzinfo=timezone.utc).isoformat(),
        source_id="folder/a,b.txt",
        model_version="model-v1",
        class_id=2,
        label="绝缘子表面金属污染物缺陷",
        confidence=0.75,
        probabilities={"绝缘子表面金属污染物缺陷": 0.75},
        features={"偏度": -0.1},
        warnings=(),
        status="success",
        error_message=None,
    )
    output = tmp_path / "history.csv"

    count = export_history_csv([record], output)

    assert count == 1
    assert output.read_bytes().startswith(b"\xef\xbb\xbf")
    with output.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    assert rows[0] == ["时间", "来源", "模型建议", "置信度", "模型版本", "状态", "错误"]
    assert rows[1] == [
        record.created_at,
        "folder/a,b.txt",
        record.label,
        "0.75",
        "model-v1",
        "success",
        "",
    ]
