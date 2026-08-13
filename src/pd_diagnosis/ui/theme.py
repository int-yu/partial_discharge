from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase


def ensure_chinese_font() -> str:
    """Return a Chinese-capable family, loading a Windows system font for headless runs."""
    preferred = ("Microsoft YaHei UI", "Microsoft YaHei", "DengXian", "SimHei")
    families = set(QFontDatabase.families())
    for family in preferred:
        if family in families:
            return family
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/Deng.ttf"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ):
        if path.is_file():
            font_id = QFontDatabase.addApplicationFont(str(path))
            loaded = QFontDatabase.applicationFontFamilies(font_id)
            if loaded:
                return loaded[0]
    return "Sans Serif"


def build_stylesheet(*, dark: bool = False) -> str:
    colors = (
        {
            "window": "#0F172A",
            "surface": "#172033",
            "surface_alt": "#1E293B",
            "text": "#F8FAFC",
            "muted": "#A8B3C5",
            "outline": "#334155",
            "primary": "#38BDF8",
            "primary_hover": "#7DD3FC",
            "on_primary": "#082F49",
            "success": "#34D399",
            "warning": "#FBBF24",
            "error": "#FB7185",
        }
        if dark
        else {
            "window": "#F4F7FB",
            "surface": "#FFFFFF",
            "surface_alt": "#EEF3F8",
            "text": "#172033",
            "muted": "#5D6B7E",
            "outline": "#D6DEE8",
            "primary": "#087EA4",
            "primary_hover": "#066987",
            "on_primary": "#FFFFFF",
            "success": "#16835B",
            "warning": "#9A6700",
            "error": "#C93756",
        }
    )
    return f"""
    * {{
        font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
        color: {colors['text']};
    }}
    QMainWindow, QWidget#AppRoot {{ background: {colors['window']}; }}
    QWidget#Sidebar {{ background: {colors['surface']}; border-right: 1px solid {colors['outline']}; }}
    QLabel#AppTitle {{ font-size: 17pt; font-weight: 600; }}
    QLabel#PageTitle {{ font-size: 17pt; font-weight: 600; }}
    QLabel#SectionTitle {{ font-size: 14pt; font-weight: 600; }}
    QLabel#MutedLabel {{ color: {colors['muted']}; }}
    QLabel#ResultLabel {{ font-size: 17pt; font-weight: 600; color: {colors['primary']}; }}
    QLabel#ConfidenceLabel {{ font-size: 14pt; font-weight: 600; }}
    QLabel#WarningLabel {{ color: {colors['warning']}; }}
    QFrame#Card {{
        background: {colors['surface']};
        border: 1px solid {colors['outline']};
        border-radius: 10px;
    }}
    QListWidget#Navigation {{ background: transparent; border: none; outline: none; }}
    QListWidget#Navigation::item {{ border-radius: 8px; padding: 12px 14px; margin: 3px 8px; }}
    QListWidget#Navigation::item:selected {{ background: {colors['primary']}; color: {colors['on_primary']}; }}
    QListWidget#Navigation::item:hover:!selected {{ background: {colors['surface_alt']}; }}
    QPushButton {{
        min-height: 42px;
        padding: 0 16px;
        border: 1px solid {colors['outline']};
        border-radius: 7px;
        background: {colors['surface']};
    }}
    QPushButton:hover {{ border-color: {colors['primary']}; background: {colors['surface_alt']}; }}
    QPushButton:focus {{ border: 2px solid {colors['primary']}; }}
    QPushButton:disabled {{ color: {colors['muted']}; background: {colors['surface_alt']}; }}
    QPushButton#PrimaryButton {{
        background: {colors['primary']}; color: {colors['on_primary']};
        border-color: {colors['primary']}; font-weight: 600;
    }}
    QPushButton#PrimaryButton:hover {{ background: {colors['primary_hover']}; }}
    QPushButton#DangerButton {{ color: {colors['error']}; }}
    QLineEdit, QComboBox {{
        min-height: 42px; padding: 0 10px; background: {colors['surface']};
        border: 1px solid {colors['outline']}; border-radius: 7px;
    }}
    QLineEdit:focus, QComboBox:focus {{ border: 2px solid {colors['primary']}; }}
    QTableWidget {{
        background: {colors['surface']}; alternate-background-color: {colors['surface_alt']};
        border: 1px solid {colors['outline']}; border-radius: 8px; gridline-color: {colors['outline']};
        selection-background-color: {colors['primary']}; selection-color: {colors['on_primary']};
    }}
    QHeaderView::section {{
        background: {colors['surface_alt']}; padding: 10px; border: none;
        border-bottom: 1px solid {colors['outline']}; font-weight: 600;
    }}
    QProgressBar {{
        min-height: 20px; border: 1px solid {colors['outline']}; border-radius: 6px;
        text-align: center; background: {colors['surface_alt']};
    }}
    QProgressBar::chunk {{ background: {colors['primary']}; border-radius: 5px; }}
    QTabWidget::pane {{ border: 1px solid {colors['outline']}; border-radius: 8px; background: {colors['surface']}; }}
    QTabBar::tab {{ padding: 10px 18px; }}
    QTabBar::tab:selected {{ color: {colors['primary']}; border-bottom: 2px solid {colors['primary']}; }}
    QStatusBar {{ background: {colors['surface']}; border-top: 1px solid {colors['outline']}; }}
    """


def chart_colors(*, dark: bool = False) -> dict[str, str]:
    return {
        "background": "#172033" if dark else "#FFFFFF",
        "text": "#F8FAFC" if dark else "#172033",
        "grid": "#475569" if dark else "#D6DEE8",
        "primary": "#38BDF8" if dark else "#087EA4",
        "secondary": "#34D399" if dark else "#16835B",
    }
