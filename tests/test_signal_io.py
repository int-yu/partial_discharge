from __future__ import annotations

import numpy as np
import pytest

from pd_diagnosis.errors import InvalidSignalError
from pd_diagnosis.signal_io import read_txt_signal


def test_txt_accepts_line_and_space_separated_values(tmp_path):
    path = tmp_path / "signal.txt"
    path.write_text("1 2\n3\n4 5", encoding="utf-8")
    np.testing.assert_array_equal(read_txt_signal(path), [1, 2, 3, 4, 5])


def test_txt_reports_malformed_token_location(tmp_path):
    path = tmp_path / "signal.txt"
    path.write_text("1 2\n3 nope", encoding="utf-8")
    with pytest.raises(InvalidSignalError, match="第 2 行第 2 个值"):
        read_txt_signal(path)

def test_non_txt_is_not_advertised(tmp_path):
    path = tmp_path / "signal.csv"
    path.write_text("1,2", encoding="utf-8")
    with pytest.raises(InvalidSignalError, match="仅支持 TXT"):
        read_txt_signal(path)
