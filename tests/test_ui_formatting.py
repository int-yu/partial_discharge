from __future__ import annotations

from PySide6.QtCore import QDateTime, QLocale, Qt

from pd_diagnosis.ui.formatting import display_time


def test_display_time_converts_utc_and_uses_locale_short_format():
    locale = QLocale(QLocale.Chinese, QLocale.China)
    value = "2026-08-10T01:02:03+00:00"
    parsed = QDateTime.fromString(value, Qt.ISODate)
    expected = locale.toString(parsed.toLocalTime(), QLocale.ShortFormat)

    assert display_time(value, locale) == expected


def test_display_time_preserves_invalid_fallback_text():
    assert display_time("时间未知") == "时间未知"
