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


class _PythonExampleAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.examples: dict[str, str] = {}
        self._name: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        name = dict(attrs).get("data-python-example")
        if name:
            self._name = name
            self._parts = []

    def handle_data(self, data):
        if self._name is not None:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag == "code" and self._name is not None:
            self.examples[self._name] = "".join(self._parts)
            self._name = None
            self._parts = []


class _LessonSectionAudit(HTMLParser):
    def __init__(self, section_ids: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: dict[str, str] = {}
        self._section_ids = section_ids
        self._active_id: str | None = None
        self._depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        section_id = dict(attrs).get("id")
        if self._active_id is None and tag == "section" and section_id in self._section_ids:
            self._active_id = section_id
            self._depth = 1
            self._parts = []
        elif self._active_id is not None:
            self._depth += 1

    def handle_data(self, data):
        if self._active_id is not None:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if self._active_id is None:
            return
        self._depth -= 1
        if self._depth == 0:
            self.sections[self._active_id] = "".join(self._parts)
            self._active_id = None
            self._parts = []


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


def test_beginner_entrypoint_and_storage_fallback(project_root):
    page = project_root / "docs" / "educate" / "index.html"
    text = page.read_text(encoding="utf-8")

    assert '<a class="button primary" href="#pyside-intro"' in text
    assert "const storage = {" in text
    assert "get(key) { try { return localStorage.getItem(key); } catch { return null; } }" in text
    assert "set(key, value) { try { localStorage.setItem(key, value); } catch {} }" in text
    assert "const savedTheme = storage.get('pd-educate-theme');" in text
    assert "storage.set('pd-educate-theme', root.dataset.theme);" in text


def test_foundation_examples_are_complete_python(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    audit = _PythonExampleAudit()
    audit.feed(text)
    required = {
        "first-window",
        "event-loop-timer",
        "widgets-form",
        "nested-layouts",
        "signals-slots",
        "main-window",
        "file-dialog",
        "stacked-pages",
        "qss-states",
        "diagnosis-ui",
        "thread-pool",
    }
    assert required <= audit.examples.keys()
    for name in required:
        compile(audit.examples[name], f"<{name}>", "exec")


def test_guided_diagnosis_ui_uses_six_explicit_stages(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")

    for stage in (
        "步骤 1：窗口骨架",
        "步骤 2：文件选择",
        "步骤 3：输入状态",
        "步骤 4：模拟诊断",
        "步骤 5：结果卡片",
        "步骤 6：错误恢复",
    ):
        assert stage in text


def test_widgets_show_entered_text_exercise_has_compilable_answer(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    lesson_audit = _LessonSectionAudit({"widgets"})
    lesson_audit.feed(text)
    assert "显示已输入文本" in lesson_audit.sections["widgets"]

    example_audit = _PythonExampleAudit()
    example_audit.feed(text)
    answer = example_audit.examples["widgets-show-entered-text-answer"]
    compile(answer, "<widgets-show-entered-text-answer>", "exec")


def test_foundation_lessons_use_full_teaching_template(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    required_sections = {
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
    }
    audit = _LessonSectionAudit(required_sections)
    audit.feed(text)
    assert required_sections == audit.sections.keys()
    for section_id, content in audit.sections.items():
        for marker in (
        "本节只学三件事",
        "运行前准备",
        "运行后应该看到什么",
        "程序按什么顺序运行",
        "逐行解释",
        "关键语法放大镜",
        "对象关系",
        "改一个地方看变化",
        "常见错误",
        "最小练习",
        "参考答案",
        "过关检查",
        ):
            assert marker in content, f"{section_id} is missing {marker}"


def test_main_window_ownership_and_qss_success_answer_are_safe(project_root):
    """Protect the two advanced examples from teaching unsafe Qt lifetime/state patterns."""
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")

    lessons = _LessonSectionAudit({"main-window-basics"})
    lessons.feed(text)
    main_window_lesson = lessons.sections["main-window-basics"]
    assert "QApplication 负责应用级资源与事件循环，不是顶层窗口的 Qt 父对象" in main_window_lesson
    assert "模块级 window Python 引用保活" in main_window_lesson

    success_answer = text.partition("<summary>参考答案：成功状态</summary>")[2].partition("</details>")[0]
    steps = (
        'self.status_label.setProperty("severity", "success")',
        'self.status_label.style().unpolish(self.status_label)',
        'self.status_label.style().polish(self.status_label)',
        "self.status_label.update()",
    )
    positions = [success_answer.index(step) for step in steps]
    assert positions == sorted(positions)
