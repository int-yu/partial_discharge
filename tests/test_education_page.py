from __future__ import annotations

import shutil
import subprocess
from html.parser import HTMLParser

import pytest


BEGINNER_SECTION_IDS = {
    "pyside-intro",
    "first-window",
    "event-loop",
    "widgets",
    "layouts",
    "signals-slots",
    "main-window-basics",
    "dialogs",
    "stacked-pages",
    "qss",
    "mini-project",
    "threading",
    "sdk",
    "project-map",
    "source-course",
}


class _EducationPageAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.fragment_links: set[str] = set()
        self.landmarks: set[str] = set()
        self.scripts: list[str] = []
        self.text_parts: list[str] = []
        self._script_parts: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids.add(element_id)
        href = attributes.get("href", "")
        if href.startswith("#") and len(href) > 1:
            self.fragment_links.add(href[1:])
        if tag in {"main", "nav", "aside"}:
            self.landmarks.add(tag)
        if tag == "script":
            assert "src" not in attributes, "教程必须保持单文件离线可用"
            self._script_parts = []

    def handle_data(self, data):
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)
        if self._script_parts is not None:
            self._script_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._script_parts is not None:
            self.scripts.append("".join(self._script_parts))
            self._script_parts = None


def test_education_page_structure_links_and_javascript(project_root, tmp_path):
    page = project_root / "docs" / "educate" / "index.html"
    text = page.read_text(encoding="utf-8")
    audit = _EducationPageAudit()
    audit.feed(text)

    assert '<html lang="zh-CN"' in text
    assert 'id="hardening"' in text
    assert audit.landmarks == {"main", "nav", "aside"}
    assert audit.duplicate_ids == set()
    assert audit.fragment_links <= audit.ids
    assert len(audit.scripts) == 2

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable; HTML structure was still checked")
    for index, script in enumerate(audit.scripts):
        script_path = tmp_path / f"education-{index}.js"
        script_path.write_text(script, encoding="utf-8")
        completed = subprocess.run(
            [node, "--check", str(script_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr


def test_beginner_curriculum_and_offline_contract(project_root):
    page = project_root / "docs" / "educate" / "index.html"
    text = page.read_text(encoding="utf-8")
    audit = _EducationPageAudit()
    audit.feed(text)

    assert BEGINNER_SECTION_IDS <= audit.ids
    assert {"鍩虹蹇呭", "椤圭洰蹇呭", "杩涢樁閫夊"} <= set(audit.text_parts)
    assert 'data-level="foundation"' in text
    assert 'data-level="project"' in text
    assert 'data-level="advanced"' in text
    assert "http://" not in text
    assert "https://" not in text
