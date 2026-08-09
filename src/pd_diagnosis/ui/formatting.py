from __future__ import annotations

from PySide6.QtCore import QDateTime, QLocale, Qt


def display_time(value: str, locale: QLocale | None = None) -> str:
    parsed = QDateTime.fromString(value, Qt.ISODateWithMs)
    if not parsed.isValid():
        parsed = QDateTime.fromString(value, Qt.ISODate)
    if not parsed.isValid():
        return value
    active_locale = locale or QLocale()
    return active_locale.toString(parsed.toLocalTime(), QLocale.ShortFormat)
