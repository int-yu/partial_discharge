from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from html import unescape
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

LINEAR_LESSON_IDS = (
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
    "flows",
)


class _EducationPageAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.fragment_links: set[str] = set()
        self.landmarks: set[str] = set()
        self.scripts: list[str] = []
        self.external_resources: list[tuple[str, str, str]] = []
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
        resource_attribute = {"script": "src", "link": "href", "img": "src"}.get(tag)
        if resource_attribute and attributes.get(resource_attribute):
            self.external_resources.append((tag, resource_attribute, attributes[resource_attribute]))
        if tag == "script":
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


class _SectionStructureAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.order: list[str] = []
        self.attributes: dict[str, dict[str, str | None]] = {}
        self.direct_children: dict[str, list[tuple[str, str]]] = {}
        self._active_id: str | None = None
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "section":
            section_id = attributes.get("id")
            if section_id:
                self.order.append(section_id)
                self.attributes[section_id] = attributes
                self.direct_children[section_id] = []
                self._active_id = section_id
                self._depth = 1
            return
        if self._active_id is not None:
            if self._depth == 1:
                self.direct_children[self._active_id].append(
                    (tag, attributes.get("class", "") or "")
                )
            if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta"}:
                self._depth += 1

    def handle_endtag(self, tag):
        if self._active_id is None:
            return
        self._depth -= 1
        if self._depth == 0:
            self._active_id = None


def _expanded_line_spec(spec: str) -> set[int]:
    lines: set[int] = set()
    for part in spec.split(","):
        start_text, separator, end_text = part.strip().partition("-")
        start = int(start_text)
        end = int(end_text) if separator else start
        lines.update(range(start, end + 1))
    return lines


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
    assert {"基础必学", "项目必学", "进阶选学"} <= set(audit.text_parts)
    assert 'data-level="foundation"' in text
    assert 'data-level="project"' in text
    assert 'data-level="advanced"' in text
    assert audit.external_resources == []
    assert re.search(r"url\(\s*['\"]?https?://", text, flags=re.IGNORECASE) is None
    assert "http://" not in text
    assert "https://" not in text


def test_linear_curriculum_order_and_progress_metadata(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    audit = _SectionStructureAudit()
    audit.feed(text)

    positions = [audit.order.index(section_id) for section_id in LINEAR_LESSON_IDS]
    assert positions == sorted(positions)
    for section_id in LINEAR_LESSON_IDS:
        attributes = audit.attributes[section_id]
        assert "lesson" in (attributes.get("class") or "").split(), section_id
        assert attributes.get("data-title"), section_id
        assert attributes.get("data-level") in {"foundation", "project"}, section_id
        children = audit.direct_children[section_id]
        assert any("lesson-meta" in classes.split() for _, classes in children), section_id
    assert "lesson" not in (audit.attributes["source-course"].get("class") or "").split()
    assert "const lessons = [...document.querySelectorAll('.lesson')];" in text


def test_late_foundation_lessons_open_with_metadata_and_heading(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    audit = _SectionStructureAudit()
    audit.feed(text)

    for section_id in ("main-window-basics", "dialogs", "stacked-pages", "qss"):
        first_two = audit.direct_children[section_id][:2]
        assert first_two[0] == ("div", "lesson-meta"), section_id
        assert first_two[1][0] == "h2", section_id


def test_beginner_entrypoint_and_storage_fallback(project_root):
    page = project_root / "docs" / "educate" / "index.html"
    text = page.read_text(encoding="utf-8")

    assert '<a class="button primary" href="#pyside-intro"' in text
    for marker in (
        "function readStoredJson(key, fallback)",
        "function writeStoredJson(key, value)",
        "pd-educate-progress",
        "continueLearning",
        "lesson-complete",
    ):
        assert marker in text
    assert "const savedTheme = readStoredJson('pd-educate-theme', null);" in text
    assert "writeStoredJson('pd-educate-theme', root.dataset.theme);" in text


def test_every_source_file_has_beginner_reading_metadata(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    source_data = text.partition('<script id="source-course-data">')[2].partition("</script>")[0]

    entry_count = len(re.findall(r"\bpath\s*:\s*['\"]", source_data))
    assert entry_count > 0
    for field in ("level", "prerequisites", "firstRead", "skipOnFirstPass"):
        values = re.findall(rf"\b{field}\s*:\s*['\"]([^'\"]+)['\"]", source_data)
        assert len(values) == entry_count, f"{field} covers {len(values)} / {entry_count} entries"
        assert all(value.strip() for value in values)
    levels = re.findall(r"\blevel\s*:\s*['\"]([^'\"]+)['\"]", source_data)
    assert set(levels) == {"项目必学", "进阶选学"}

    final_script = text.rsplit("<script>", 1)[1].partition("</script>")[0]
    for field in ("file.level", "file.prerequisites", "file.firstRead", "file.skipOnFirstPass"):
        assert field in final_script
    assert "innerHTML" not in final_script


def test_source_course_paths_lines_and_key_symbols_match_checkout(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    source_data = text.partition('<script id="source-course-data">')[2].partition("</script>")[0]
    records = re.findall(
        r'path:\s*"([^"]+)"\s*,\s*lines:\s*(\d+|null)', source_data
    )
    assert records
    aggregate_markers = ("*", " + ", "{", "}")
    for relative_path, declared_lines in records:
        if any(marker in relative_path for marker in aggregate_markers):
            continue
        path = project_root / relative_path
        assert path.is_file(), relative_path
        if declared_lines != "null":
            actual_lines = len(path.read_text(encoding="utf-8").splitlines())
            assert int(declared_lines) == actual_lines, relative_path

    def source_entry(path: str) -> str:
        entry = source_data.partition(f'path:"{path}"')[2]
        assert entry, path
        return entry.partition("\n      {\n        group:")[0]

    expected_symbols = {
        "src/pd_diagnosis/bundle.py": (
            "SUPPORTED_ARCHITECTURE",
            "ModelBundle.load",
            "_verify_artifact",
            "_load_scaler",
            "resolve_bundle_artifact",
            "sha256_file",
        ),
        "src/pd_diagnosis/ui/workers.py": (
            "SingleDiagnosisOutcome",
            "HistoryExportOutcome",
            "TaskSignals",
            "SingleDiagnosisTask",
            "BatchDiagnosisTask",
            "HistoryExportTask",
        ),
        "src/pd_diagnosis/ui/main_window.py": (
            "MainWindow",
            "setMaxThreadCount(1)",
            "start_single_diagnosis",
            "_show_single_result",
            "_finish_single",
            "BatchDiagnosisTask",
            "HistoryExportTask",
        ),
        "src/pd_diagnosis/__main__.py": (
            "from .launcher import main",
            "raise SystemExit(main())",
        ),
    }
    for path, symbols in expected_symbols.items():
        entry = source_entry(path)
        for symbol in symbols:
            assert symbol in entry, (path, symbol)

    assert "批量 cancelled 字段" not in source_data
    history_export_entry = source_entry("src/pd_diagnosis/ui/history_export.py")
    assert "生成器细节" not in history_export_entry
    assert "核心生产 Python 文件" in text
    assert "重点测试文件" in text
    assert "100%</strong><span>正式 Python 文件" not in text


def test_project_bridge_gives_beginners_two_traceable_call_chains(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")

    for marker in (
        "先不用界面：直接调用 SDK",
        "把教程里的对象换成项目里的对象",
        "应用启动链",
        "单文件诊断链",
        "第一次阅读只追这一条线",
    ):
        assert marker in text

    chain_headers = (
        "触发",
        "精确文件与可调用对象",
        "输入 → 输出",
        "线程",
        "可能错误",
        "下一步",
    )
    for title in ("应用启动链", "单文件诊断链"):
        table = text.partition(f"<h3>{title}</h3>")[2].partition("</table>")[0]
        assert table
        for header in chain_headers:
            assert f"<th>{header}</th>" in table

    hardening = text.partition('id="hardening"')[2].partition("</section>")[0]
    advanced_topics = (
        "SQLite",
        "bundle 验证",
        "不可变快照",
        "工件哈希",
        "历史分页",
        "CSV 导出",
        "模型内部",
    )
    for topic in advanced_topics:
        card = hardening.partition(f"<h3>进阶选学：{topic}</h3>")[2].partition("</article>")[0]
        assert "初读只需要知道" in card
        assert "暂时可以跳过" in card

    sdk = text.partition('id="sdk"')[2].partition("</section>")[0]
    assert "当前样例模型和数据集用于演示工程接口、调用链和输入输出" in sdk
    assert "不应把样例输出当作现场诊断结论" in sdk


def test_service_source_lesson_matches_persistence_isolation_contract(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    service_summary = text.partition(
        '<summary><code>service.py</code> — 应用服务</summary>'
    )[2].partition("</details>")[0]
    advanced_sqlite = text.partition("<h3>进阶选学：SQLite</h3>")[2].partition("</article>")[0]
    service_entry = text.partition('path:"src/pd_diagnosis/service.py"')[2].partition(
        'path:"src/pd_diagnosis/storage.py"'
    )[0]
    role_match = re.search(r'role:"([^"]+)"', service_entry.partition("parts:[")[0])

    def source_part(title):
        marker = f'title:"{title}"'
        marker_offset = service_entry.index(marker)
        line_start = service_entry.rfind('{range:"', 0, marker_offset)
        line_end = service_entry.index("\n", marker_offset)
        return service_entry[line_start:line_end]

    parts = {
        "policy": source_part("业务层导入与持久化策略"),
        "memory": source_part("内存信号业务流程"),
        "file": source_part("文件业务流程"),
        "result": source_part("成功结果的保存隔离"),
        "error": source_part("诊断错误记录的保存隔离"),
    }

    assert advanced_sqlite and service_summary and service_entry and role_match
    assert "数据库写入异常目前会传播" not in text
    assert "保存成功结果失败时会返回附加 warning 的结果" not in text
    assert "保存诊断错误本身失败时仍继续抛出原始" not in text
    assert "保存失败不会抹掉已有诊断结果" not in text
    for marker in (
        "仅当历史保存抛出 <code>sqlite3.Error</code> 或 <code>OSError</code> 时",
        "诊断结果仍会返回并附加 warning",
        "其他异常继续传播",
    ):
        assert marker in advanced_sqlite
    for marker in (
        "仅当保存抛出 <code>sqlite3.Error</code> 或 <code>OSError</code> 时",
        "其他异常继续传播",
        "可能替代原始 <code>DiagnosisError</code>",
    ):
        assert marker in service_summary
    boundary = "PERSISTENCE_EXCEPTIONS（当前是 sqlite3.Error、OSError）"
    role = role_match.group(1)
    assert boundary in role
    assert "其他异常继续传播" in role
    for name, part in parts.items():
        assert boundary in part, name
        assert "其他异常继续传播" in part, name
    for marker in (
        "warnings=(*result.warnings, PERSISTENCE_WARNING_TEXT)",
        "才返回附加 PERSISTENCE_WARNING_TEXT 的结果",
    ):
        assert marker in parts["result"]
    for marker in (
        "才保留并抛出原始 DiagnosisError",
        "其他异常继续传播，并可能替代原始 DiagnosisError",
    ):
        assert marker in parts["error"]
    for name in ("memory", "file", "error"):
        assert "可能替代原始 DiagnosisError" in parts[name], name


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


def test_deferred_reference_answers_are_compiled_automatically(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    audit = _PythonExampleAudit()
    audit.feed(text)
    reference_answers = {
        "widgets-clear-form-answer",
        "layouts-spacing-answer",
        "signals-reset-answer",
    }

    assert reference_answers <= audit.examples.keys()
    for name in reference_answers:
        compile(audit.examples[name], f"<{name}>", "exec")


def test_late_foundation_reference_answers_are_complete_and_explained(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    audit = _PythonExampleAudit()
    audit.feed(text)
    example_pairs = {
        "main-window": "main-window-answer",
        "file-dialog": "file-dialog-answer",
        "stacked-pages": "stacked-pages-answer",
        "qss-states": "qss-states-answer",
    }

    for canonical_name, answer_name in example_pairs.items():
        answer = audit.examples[answer_name]
        compile(answer, f"<{answer_name}>", "exec")
        canonical_tree = ast.parse(audit.examples[canonical_name])
        statement_lines = {
            node.lineno for node in ast.walk(canonical_tree) if isinstance(node, ast.stmt)
        }
        table_match = re.search(
            rf'<table class="compare line-by-line" '
            rf'data-line-explanation-for="{canonical_name}">(.*?)</table>',
            text,
            flags=re.DOTALL,
        )
        assert table_match, canonical_name
        covered_lines: set[int] = set()
        for spec in re.findall(r'data-lines="([0-9,\-]+)"', table_match.group(1)):
            covered_lines.update(_expanded_line_spec(spec))
        assert statement_lines <= covered_lines, (
            canonical_name,
            sorted(statement_lines - covered_lines),
        )


def test_foundation_examples_run_offscreen(project_root, tmp_path):
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 is unavailable; compile coverage still protects the examples")

    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    audit = _PythonExampleAudit()
    audit.feed(text)
    names = (
        "first-window",
        "event-loop-timer",
        "widgets-form",
        "nested-layouts",
        "signals-slots",
        "main-window",
        "file-dialog",
        "stacked-pages",
        "qss-states",
        "main-window-answer",
        "file-dialog-answer",
        "stacked-pages-answer",
        "qss-states-answer",
    )
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"

    for name in names:
        source = audit.examples[name]
        source = source.replace(
            "raise SystemExit(app.exec())",
            'from PySide6.QtCore import QTimer\nQTimer.singleShot(0, app.quit)\n'
            'raise SystemExit(app.exec())\n',
        )
        source = re.sub(
            r"(?m)^exit_code = app\.exec\(\)\nraise SystemExit\(exit_code\)",
            'from PySide6.QtCore import QTimer\nQTimer.singleShot(0, app.quit)\n'
            'raise SystemExit(app.exec())',
            source,
        )
        program = tmp_path / f"{name}.py"
        program.write_text(source, encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(program)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            check=False,
            timeout=20,
        )
        assert completed.returncode == 0, f"{name}: {completed.stderr}"


def test_thread_pool_and_sdk_examples_execute(project_root, tmp_path):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    audit = _PythonExampleAudit()
    audit.feed(text)
    assert "sdk-diagnosis" in audit.examples
    compile(audit.examples["sdk-diagnosis"], "<sdk-diagnosis>", "exec")

    if importlib.util.find_spec("PySide6") is not None:
        thread_source = audit.examples["thread-pool"].replace(
            "raise SystemExit(app.exec())",
            '''from PySide6.QtCore import QTimer
window.start_button.click()
def verify_result():
    assert "模拟诊断完成" in window.status_label.text(), window.status_label.text()
    assert window.start_button.isEnabled()
    print("thread pool example OK")
    app.quit()
QTimer.singleShot(3000, verify_result)
raise SystemExit(app.exec())
''',
        )
        thread_program = tmp_path / "thread-pool.py"
        thread_program.write_text(thread_source, encoding="utf-8")
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        completed = subprocess.run(
            [sys.executable, str(thread_program)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            check=False,
            timeout=15,
        )
        assert completed.returncode == 0, completed.stderr
        assert "thread pool example OK" in completed.stdout

    sdk_program = tmp_path / "sdk-diagnosis.py"
    sdk_program.write_text(audit.examples["sdk-diagnosis"], encoding="utf-8")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root / "src")
    completed = subprocess.run(
        [sys.executable, str(sdk_program)],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    for field in ("label:", "confidence:", "probabilities:", "model_version:", "source_id:"):
        assert field in completed.stdout


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


def test_guided_diagnosis_stages_keep_prior_capabilities(project_root):
    """Each step must remain a runnable cumulative program, not a replacement demo."""
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    sections = re.findall(
        r"<h3>步骤 [1-6]：.*?</h3>.*?<pre><code(?: [^>]*)?>(.*?)</code></pre>",
        text,
        flags=re.DOTALL,
    )
    assert len(sections) == 6
    programs = [unescape(section) for section in sections]
    requirements = (
        ("self.setWindowTitle", "self.status_label", "layout = QVBoxLayout", "window = DiagnosisWindow"),
        ("self.file_label", "self.choose_button", "def choose_file"),
        ("class UiState", "self.start_button", "def set_state"),
        ("QTimer.singleShot", "def start_diagnosis", "def finish_simulation"),
        ("self.result_label", "self.result_label.setText"),
        ("UiState.ERROR", "self.fail_button", "def start_failure", "def reset"),
    )
    for index, program in enumerate(programs):
        compile(program, f"<diagnosis-stage-{index + 1}>", "exec")
        for prior_requirements in requirements[: index + 1]:
            for marker in prior_requirements:
                assert marker in program


def test_guided_diagnosis_stages_introduce_apis_at_the_claimed_step(project_root):
    """Catch future imports, renamed callbacks, and unexplained state-machine rewrites."""
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    sections = re.findall(
        r"<h3>步骤 [1-6]：.*?</h3>.*?<pre><code(?: [^>]*)?>(.*?)</code></pre>",
        text,
        flags=re.DOTALL,
    )
    programs = [ast.parse(unescape(section)) for section in sections]

    def imports(tree):
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
        return names

    def methods(tree):
        return {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name != "__init__"
        }

    imported = [imports(program) for program in programs]
    assert {"Enum", "auto", "Path", "QTimer", "Slot", "QFileDialog", "QPushButton"}.isdisjoint(imported[0])
    assert {"Path", "Slot", "QFileDialog", "QPushButton"} <= imported[1]
    assert {"Enum", "auto", "QTimer"}.isdisjoint(imported[1])
    assert "Enum" in imported[2]
    assert "auto" not in set().union(*imported)
    assert "QTimer" not in imported[2]
    assert "QTimer" in imported[3]

    stage_methods = [methods(program) for program in programs]
    assert "choose_file" not in stage_methods[0]
    assert "choose_file" in stage_methods[1]
    assert "set_state" in stage_methods[2]
    assert {"start_diagnosis", "finish_simulation"} <= stage_methods[3].keys()
    assert "show_result" not in stage_methods[3]
    assert "show_result" in stage_methods[4]
    assert "self.show_result()" in ast.unparse(stage_methods[4]["finish_simulation"])
    assert {"start_failure", "complete_simulation", "reset"} <= stage_methods[5].keys()
    introduced_methods = (
        set(),
        {"choose_file"},
        {"set_state"},
        {"start_diagnosis", "finish_simulation"},
        {"show_result"},
        {"start_failure", "complete_simulation", "reset"},
    )
    all_later_methods = set().union(*introduced_methods)
    expected_methods = set()
    for index, stage in enumerate(stage_methods):
        expected_methods.update(introduced_methods[index])
        assert expected_methods <= stage.keys()
        assert not (stage.keys() & (all_later_methods - expected_methods))
    assert "result_label" not in ast.unparse(stage_methods[3]["finish_simulation"])
    assert "self.complete_simulation(None)" in ast.unparse(stage_methods[5]["finish_simulation"])
    assert "self.show_result()" in ast.unparse(stage_methods[5]["complete_simulation"])

    for tree in programs[2:]:
        states = next(
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "UiState"
        )
        assert all(
            isinstance(item, ast.Assign)
            and isinstance(item.value, ast.Constant)
            and isinstance(item.value.value, str)
            for item in states.body
        )


def test_guided_diagnosis_visible_stage_contract_matches_ast_changes(project_root):
    """The learner-visible change list is the sole contract for every AST delta."""
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    sections = re.findall(
        r"<h3>步骤 [1-6]：.*?</h3>.*?<pre><code(?: [^>]*)?>(.*?)</code></pre>",
        text,
        flags=re.DOTALL,
    )
    contract_tags = re.findall(r'<div class="stage-contract"([^>]*)>', text)
    contract_blocks = re.findall(r'<div class="stage-contract"[^>]*>(.*?)</div>', text, flags=re.DOTALL)
    assert len(sections) == len(contract_tags) == len(contract_blocks) == 6
    assert all(not tag.strip() for tag in contract_tags), "阶段契约的值必须对学员可见，不能藏在 data-* 属性中"

    labels = {
        "新增导入": "added-imports",
        "新增方法": "added-methods",
        "修改方法": "modified-methods",
        "新增属性": "added-attributes",
        "新增状态": "added-states",
        "修改状态": "modified-states",
        "新增启动语句": "added-bootstrap",
        "修改启动语句": "modified-bootstrap",
    }

    def visible_contract(block):
        row_pairs = re.findall(r"<dt>([^<]+)</dt>\s*<dd>(.*?)</dd>", block, flags=re.DOTALL)
        assert len(row_pairs) == len(labels)
        rows = dict(row_pairs)
        assert rows.keys() == labels.keys()
        contract = {}
        for label, key in labels.items():
            values = {unescape(value) for value in re.findall(r"<code>([^<]+)</code>", rows[label])}
            plain_text = unescape(re.sub(r"<[^>]+>", "", rows[label])).strip()
            assert values or plain_text == "无"
            contract[key] = values
        return contract

    def class_node(tree):
        return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DiagnosisWindow")

    def imports(tree):
        return {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }

    def methods(node):
        return {item.name: item for item in node.body if isinstance(item, ast.FunctionDef)}

    def attributes(node):
        return {
            target.attr
            for item in ast.walk(node)
            if isinstance(item, ast.Assign)
            for target in item.targets
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"
        }

    def states(tree):
        enum = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "UiState")
        return {
            item.targets[0].id: item.value.value
            for item in enum.body
            if isinstance(item, ast.Assign)
            and isinstance(item.targets[0], ast.Name)
            and isinstance(item.value, ast.Constant)
            and isinstance(item.value.value, str)
        }

    def bootstrap(tree):
        statements = {}
        for item in tree.body:
            if isinstance(item, (ast.Import, ast.ImportFrom, ast.ClassDef)):
                continue
            if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
                key = item.targets[0].id
            elif isinstance(item, ast.Expr) and isinstance(item.value, ast.Call):
                key = ast.unparse(item.value.func)
            elif isinstance(item, ast.Raise) and isinstance(item.exc, ast.Call):
                key = ast.unparse(item.exc.func)
            else:
                raise AssertionError(f"未识别的模块级启动语句: {ast.dump(item, include_attributes=False)}")
            assert key not in statements
            statements[key] = item
        return statements

    prior_imports: set[str] = set()
    prior_methods: dict[str, ast.FunctionDef] = {}
    prior_attributes: set[str] = set()
    prior_states: dict[str, str] = {}
    prior_bootstrap: dict[str, ast.stmt] = {}
    for source, block in zip(sections, contract_blocks, strict=True):
        tree = ast.parse(unescape(source))
        contract = visible_contract(block)
        current_imports = imports(tree)
        current_methods = methods(class_node(tree))
        current_attributes = attributes(class_node(tree))
        current_states = states(tree) if any(node.name == "UiState" for node in tree.body if isinstance(node, ast.ClassDef)) else {}
        current_bootstrap = bootstrap(tree)

        assert current_imports - prior_imports == contract["added-imports"]
        assert current_methods.keys() - prior_methods.keys() == contract["added-methods"]
        assert current_attributes - prior_attributes == contract["added-attributes"]
        assert current_states.keys() - prior_states.keys() == contract["added-states"]
        assert current_bootstrap.keys() - prior_bootstrap.keys() == contract["added-bootstrap"]
        assert prior_imports <= current_imports
        assert prior_methods.keys() <= current_methods.keys()
        assert prior_attributes <= current_attributes
        assert prior_states.keys() <= current_states.keys()
        assert prior_bootstrap.keys() <= current_bootstrap.keys()
        assert [key for key in current_bootstrap if key in prior_bootstrap] == list(prior_bootstrap)

        actual_modified_methods = {
            name
            for name in prior_methods.keys() & current_methods.keys()
            if ast.dump(prior_methods[name], include_attributes=False) != ast.dump(current_methods[name], include_attributes=False)
        }
        assert actual_modified_methods == contract["modified-methods"]
        actual_modified_states = {
            name for name in prior_states.keys() & current_states.keys() if prior_states[name] != current_states[name]
        }
        assert actual_modified_states == contract["modified-states"]
        actual_modified_bootstrap = {
            name
            for name in prior_bootstrap.keys() & current_bootstrap.keys()
            if ast.dump(prior_bootstrap[name], include_attributes=False)
            != ast.dump(current_bootstrap[name], include_attributes=False)
        }
        assert actual_modified_bootstrap == contract["modified-bootstrap"]

        prior_imports = current_imports
        prior_methods = current_methods
        prior_attributes = current_attributes
        prior_states = current_states
        prior_bootstrap = current_bootstrap

    final_tree = ast.parse(unescape(sections[-1]))
    stage_five_methods = methods(class_node(ast.parse(unescape(sections[4]))))
    final_methods = methods(class_node(final_tree))
    assert ast.dump(final_methods["start_diagnosis"], include_attributes=False) == ast.dump(stage_five_methods["start_diagnosis"], include_attributes=False)
    assert ast.dump(final_methods["choose_file"], include_attributes=False) == ast.dump(stage_five_methods["choose_file"], include_attributes=False)
    assert states(final_tree)["SUCCESS"] == states(ast.parse(unescape(sections[4])))["SUCCESS"]
    assert "start_simulation" not in final_methods
    assert len(final_methods["finish_simulation"].body) == 1
    assert ast.unparse(final_methods["finish_simulation"].body[0]) == "self.complete_simulation(None)"
    assert not any(isinstance(node, ast.Try) for node in ast.walk(final_methods["finish_simulation"]))
    assert any(isinstance(node, ast.Try) for node in ast.walk(final_methods["complete_simulation"]))
    final_contract_text = unescape(re.sub(r"<[^>]+>", "", contract_blocks[-1]))
    assert "finish_simulation() 只负责把成功路径委托给 complete_simulation(None)" in final_contract_text
    assert "complete_simulation() 负责 try/except/finally" in final_contract_text


def test_thread_pool_mapping_preserves_service_result_and_affinity_roles(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")

    assert "class DemoDiagnosisService" in text
    assert "self.service.diagnose(self.filename)" in text
    assert "<code>DemoDiagnosisService</code></td><td><code>DiagnosisService</code>" in text
    assert "<code>self.signals.result.emit(result)</code></td><td><code>SingleDiagnosisOutcome</code> / <code>DiagnosisResult</code>" in text
    assert "QRunnable 不是 QObject" in text
    assert "没有 QObject thread affinity" in text
    assert "WorkerSignals 在 GUI 主线程创建" in text
    assert "不会因被 runnable 持有而自动迁移" in text


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


def test_staged_practices_close_each_prerequisite_learning_loop(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    exercise_html = text.partition('id="exercises"')[2].partition("</section>")[0]
    practices = re.findall(
        r'<article class="practice-card"([^>]*)>(.*?)</article>',
        exercise_html,
        flags=re.DOTALL,
    )
    required_prerequisites = {
        "widgets",
        "layouts",
        "signals-slots",
        "dialogs",
        "stacked-pages",
        "qss",
        "threading",
        "sdk",
        "flows",
    }

    assert len(practices) >= len(required_prerequisites)
    covered_prerequisites = set()
    levels = set()
    for attributes, body in practices:
        prerequisite = re.search(r'data-prerequisite="([^"]+)"', attributes)
        level = re.search(r'data-level="([^"]+)"', attributes)
        assert prerequisite and level
        covered_prerequisites.add(prerequisite.group(1))
        levels.add(level.group(1))
        assert f'href="#{prerequisite.group(1)}"' in body
        assert '<details class="practice-answer"' in body
        plain_text = unescape(re.sub(r"<[^>]+>", " ", body))
        for marker in ("前置课程", "可见结果", "限制条件", "提示", "完整答案", "自我验证"):
            assert marker in plain_text, f"{prerequisite.group(1)} is missing {marker}"

    assert covered_prerequisites == required_prerequisites
    assert levels == {"foundation", "project"}


def test_practice_python_answers_are_complete_and_executable(project_root, tmp_path):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    audit = _PythonExampleAudit()
    audit.feed(text)
    practice_names = (
        "practice-widgets-clear",
        "practice-layouts-bottom",
        "practice-signals-reset",
        "practice-dialog-cancel",
        "practice-stacked-history",
        "practice-qss-success",
        "practice-thread-finish",
        "practice-sdk-summary",
    )

    assert set(practice_names) <= audit.examples.keys()
    for name in practice_names:
        compile(audit.examples[name], f"<{name}>", "exec")

    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 is unavailable; all practice answers were still compiled")

    executable_examples = {
        name: audit.examples[name]
        for name in practice_names[:6]
    }
    runner = f'''\
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

examples = json.loads({json.dumps(json.dumps(executable_examples))})
app = QApplication.instance() or QApplication([])

def load(name):
    namespace = {{"__name__": f"answer_{{name}}"}}
    exec(compile(examples[name], f"<{{name}}>", "exec"), namespace)
    return namespace

widgets = load("practice-widgets-clear")
form = widgets["ProfileForm"]()
assert form.layout().indexOf(form.clear_button) >= 0
form.name_input.setText("Alice")
form.role_box.setCurrentIndex(1)
form.result_output.setPlainText("submitted")
form.clear_button.click()
assert form.name_input.text() == ""
assert form.role_box.currentIndex() == 0
assert form.result_output.toPlainText() == ""

layouts = load("practice-layouts-bottom")
bottom = layouts["BottomButtonWindow"]()
assert bottom.root_layout.itemAt(1).spacerItem() is not None
button_row = bottom.root_layout.itemAt(2).layout()
assert button_row.indexOf(bottom.cancel_button) >= 0
assert button_row.indexOf(bottom.save_button) >= 0

signals = load("practice-signals-reset")
counter = signals["ResetCounter"]()
assert counter.layout().indexOf(counter.reset_button) >= 0
for _ in range(3):
    counter.add_button.click()
assert counter.value_label.text() == "3"
counter.reset_button.click()
assert counter.value_label.text() == "0"
counter.add_button.click()
assert counter.value_label.text() == "1"

dialogs = load("practice-dialog-cancel")
responses = iter((("image.png", "Images"), ("", "")))
messages = []
class FakeFileDialog:
    @staticmethod
    def getOpenFileName(*_args):
        return next(responses)
class FakeMessageBox:
    @staticmethod
    def information(_parent, title, message):
        messages.append((title, message))
dialogs["QFileDialog"] = FakeFileDialog
dialogs["QMessageBox"] = FakeMessageBox
chooser = dialogs["ImageChooser"]()
assert chooser.layout().indexOf(chooser.choose_button) >= 0
chooser.choose_button.click()
assert chooser.path_label.text() == "image.png"
chooser.choose_button.click()
assert chooser.path_label.text() == "image.png"
assert messages == [("已选择", "image.png")]

pages = load("practice-stacked-history")
page_window = pages["HistoryPageWindow"]()
assert page_window.navigation.indexOf(page_window.history_button) >= 0
page_window.history_button.click()
assert page_window.pages.currentIndex() == 2
page_window.overview_button.click()
assert page_window.pages.currentIndex() == 0

qss = load("practice-qss-success")
status_window = qss["SuccessStatusWindow"]()
assert status_window.layout().indexOf(status_window.success_button) >= 0
status_window.success_button.click()
assert status_window.status_label.text() == "已完成"
assert status_window.status_label.property("severity") == "success"
print("practice answers execute OK")
'''
    runner_path = tmp_path / "run-practice-answers.py"
    runner_path.write_text(runner, encoding="utf-8")
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(
        [sys.executable, str(runner_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert "practice answers execute OK" in completed.stdout


def test_final_quiz_feedback_mapping_is_complete_and_consistent(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    audit = _EducationPageAudit()
    audit.feed(text)
    quiz_html = text.partition('id="quiz"')[2].partition("</section>")[0]
    questions = re.findall(
        r'<fieldset class="quiz-question"([^>]*)>(.*?)</fieldset>',
        quiz_html,
        flags=re.DOTALL,
    )

    assert len(questions) >= 12
    assert "const quizAnswers = new Map" in text
    assert "答案解释" in quiz_html
    assert 'aria-live="polite"' in quiz_html
    for index, (attributes, body) in enumerate(questions, start=1):
        answer = re.search(r'data-answer="([^"]+)"', attributes)
        review = re.search(r'data-review-section="([^"]+)"', attributes)
        assert answer and review
        radio_names = set(re.findall(r'type="radio" name="([^"]+)"', body))
        option_values = set(re.findall(r'type="radio" name="[^"]+" value="([^"]+)"', body))
        review_link = re.search(r'class="review-link" href="#([^"]+)"', body)
        explanation = re.search(
            r'class="answer-explanation"[^>]*>(.*?)</p>', body, flags=re.DOTALL
        )
        assert radio_names == {f"q{index}"}
        assert answer.group(1) in option_values
        assert review_link and review_link.group(1) == review.group(1)
        assert review.group(1) in audit.ids
        assert explanation and unescape(re.sub(r"<[^>]+>", "", explanation.group(1))).strip()


def test_glossary_terms_are_cross_linked_in_both_directions(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    before_glossary, _, glossary_and_after = text.partition('<section class="chapter" id="glossary"')
    glossary = glossary_and_after.partition("</section>")[0]
    terms = {
        "binding": "pyside-intro",
        "widget": "widgets",
        "parent-child": "main-window-basics",
        "layout": "layouts",
        "event": "event-loop",
        "event-loop": "event-loop",
        "signal": "signals-slots",
        "slot": "signals-slots",
        "callback": "signals-slots",
        "main-thread": "threading",
        "worker": "threading",
        "thread-pool": "threading",
        "modal-dialog": "dialogs",
        "qss": "qss",
        "sdk": "sdk",
        "service": "architecture",
        "dependency-injection": "architecture",
        "persistence": "hardening",
        "bundle": "sdk",
        "immutable-snapshot": "flows",
    }

    for slug, lesson_id in terms.items():
        assert f'class="term-link" href="#term-{slug}"' in before_glossary
        assert f'id="term-{slug}"' in glossary
        assert f'class="glossary-backlink" href="#{lesson_id}"' in glossary


def test_accessible_responsive_no_js_and_print_contract(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    static_note = "禁用 JavaScript 时仍可阅读全部核心课程；进度、搜索和自测反馈不可用。"

    assert static_note in text
    assert '<noscript>' in text
    assert ':focus-visible' in text
    assert '@media (max-width: 480px)' in text
    assert '@media print' in text
    assert 'details:not([open]) > *:not(summary)' in text
    assert 'overflow-x: auto' in text
    assert '<fieldset class="quiz-question"' in text
    assert '<legend>' in text
    assert '.visually-hidden {' in text
    assert '<label class="visually-hidden" for="fileSearch">' in text
    assert '<label class="visually-hidden" for="sourceSearch">' in text
    assert '.chapter, [id^="term-"] { scroll-margin-top:' in text
    assert "同六个问题阅读" in text
    assert "同七个问题阅读" not in text
    print_css = text.partition("@media print")[2].partition("@media (prefers-reduced-motion")[0]
    hidden_selector = print_css.partition("{ display: none !important; }")[0]
    assert ".source-browser" in hidden_selector
    assert "#sourceFileNav" in hidden_selector
    assert ".source-detail" not in hidden_selector
    for broken_text in ("鍩虹", "椤圭洰", "杩涢樁", "杩炴帴"):
        assert broken_text not in text


def test_course_runtime_tolerates_blocked_storage_and_legacy_theme(project_root, tmp_path):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    audit = _EducationPageAudit()
    audit.feed(text)
    assert len(audit.scripts) == 2
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable; static storage contracts were still checked")

    harness = f"""
const vm = require("node:vm");
const sourceData = {json.dumps(audit.scripts[0])};
const interaction = {json.dumps(audit.scripts[1])};

class ClassList {{
  constructor() {{ this.values = new Set(); }}
  contains(value) {{ return this.values.has(value); }}
  remove(value) {{ this.values.delete(value); }}
  toggle(value, force) {{
    if (force === undefined) force = !this.values.has(value);
    if (force) this.values.add(value); else this.values.delete(value);
    return force;
  }}
}}

class FakeElement {{
  constructor(id = "") {{
    this.id = id;
    this.dataset = {{}};
    this.style = {{}};
    this.classList = new ClassList();
    this.children = [];
    this.listeners = {{}};
    this.attributes = {{}};
    this._textContent = "";
    this.innerText = "";
    this.value = "";
    this.href = "";
    this.hash = "";
    this.checked = false;
    this.inert = false;
    this.focused = false;
  }}
  addEventListener(type, callback) {{ this.listeners[type] = callback; }}
  dispatch(type, event = {{}}) {{
    const callback = this.listeners[type];
    if (callback) callback({{ preventDefault() {{}}, key: "", ...event }});
  }}
  click() {{ this.dispatch("click"); }}
  focus(options) {{ this.focused = true; this.focusOptions = options; }}
  get textContent() {{
    return this._textContent + this.children.map(item =>
      typeof item === "string" ? item : item.textContent
    ).join("");
  }}
  set textContent(value) {{ this._textContent = String(value); this.children = []; }}
  append(...items) {{ this.children.push(...items); }}
  appendChild(item) {{ this.children.push(item); return item; }}
  replaceChildren(...items) {{ this.children = [...items]; }}
  setAttribute(name, value) {{ this.attributes[name] = String(value); }}
  getAttribute(name) {{ return name === "href" ? this.href : this.attributes[name]; }}
  getBoundingClientRect() {{ return {{ top: 200 }}; }}
  scrollIntoView() {{}}
  querySelector(selector) {{
    if (selector === ".lesson-meta") return this.lessonMeta || null;
    if (selector === ".answer-explanation") return this.explanation || null;
    if (selector === ".review-link") return this.reviewLink || null;
    if (selector.startsWith('input[value="')) return this.correctInput || null;
    return null;
  }}
  querySelectorAll(selector) {{
    if (selector === ".quiz-question") return this.quizQuestions || [];
    return [];
  }}
}}

function runScenario(storageValues, blocked, preferredDark, mobile = true) {{
  const elements = new Map();
  const byId = id => {{
    if (!elements.has(id)) elements.set(id, new FakeElement(id));
    return elements.get(id);
  }};
  const lessons = ["pyside-intro", "first-window", "threading"].map((id, index) => {{
    const lesson = byId(id);
    lesson.dataset.title = `Lesson ${{index + 1}}`;
    lesson.lessonMeta = new FakeElement();
    return lesson;
  }});
  const themeButtons = [new FakeElement(), new FakeElement()];
  const tocLink = new FakeElement();
  tocLink.href = "#first-window";
  tocLink.hash = "#first-window";
  const quizQuestions = Array.from({{ length: 12 }}, (_, index) => {{
    const question = new FakeElement();
    question.dataset.answer = "b";
    question.dataset.reviewSection = "event-loop";
    question.explanation = new FakeElement();
    question.explanation.textContent = `explanation ${{index + 1}}`;
    question.reviewLink = new FakeElement();
    question.reviewLink.href = "#event-loop";
    question.correctInput = {{ parentElement: {{ textContent: "correct answer" }} }};
    return question;
  }});
  const quiz = byId("quizForm");
  quiz.quizQuestions = quizQuestions;
  quiz.elements = Object.fromEntries(
    quizQuestions.map((_, index) => [`q${{index + 1}}`, {{ value: "" }}])
  );
  const writes = [];
  const documentListeners = {{}};
  const document = {{
    documentElement: byId("root"),
    getElementById: byId,
    createElement: () => new FakeElement(),
    createTextNode: text => ({{ textContent: text }}),
    addEventListener(type, callback) {{ documentListeners[type] = callback; }},
    dispatch(type, event = {{}}) {{
      const callback = documentListeners[type];
      if (callback) callback({{ key: "", ...event }});
    }},
    querySelectorAll(selector) {{
      if (selector === ".theme-toggle") return themeButtons;
      if (selector === "#toc a") return [tocLink];
      if (selector === ".chapter") return lessons;
      if (selector === ".lesson") return lessons;
      if (selector === ".copy" || selector === ".file-item" || selector === ".source-file-button") return [];
      return [];
    }},
  }};
  document.documentElement.scrollHeight = 1000;
  const localStorage = {{
    getItem(key) {{ if (blocked) throw new Error("blocked read"); return storageValues[key] ?? null; }},
    setItem(key, value) {{ if (blocked) throw new Error("blocked write"); writes.push([key, value]); }},
  }};
  const context = {{
    console,
    document,
    localStorage,
    navigator: {{ clipboard: {{ writeText: async () => {{}} }} }},
    setTimeout: callback => callback(),
    matchMedia: query => ({{
      matches: query.includes("max-width") ? mobile : preferredDark,
      addEventListener: () => {{}},
    }}),
    innerHeight: 800,
    scrollY: 0,
    addEventListener: () => {{}},
  }};
  context.window = context;
  vm.createContext(context);
  vm.runInContext(sourceData, context);
  vm.runInContext(interaction, context);
  return {{
    context,
    document,
    lessons,
    themeButtons,
    tocLink,
    quiz,
    writes,
    menuButton: byId("menuButton"),
    sidebar: byId("sidebar"),
  }};
}}

const blocked = runScenario({{}}, true, false);
if (blocked.document.documentElement.dataset.theme !== "light") {{
  throw new Error("blocked storage stopped theme fallback");
}}
if (!blocked.lessons.every(lesson => lesson.lessonMeta.children.length === 1)) {{
  throw new Error("lesson controls were not initialized");
}}
blocked.themeButtons[0].click();
if (blocked.document.documentElement.dataset.theme !== "dark") {{
  throw new Error("blocked theme write stopped later UI updates");
}}
const blockedCheckbox = blocked.lessons[0].lessonMeta.children[0].children[0];
blockedCheckbox.checked = true;
blockedCheckbox.dispatch("change");
if (blocked.document.getElementById("completionTotal").textContent !== "已完成 1 / 3 节") {{
  throw new Error("blocked progress write stopped completion updates");
}}

Object.entries(blocked.quiz.elements).forEach(([name, input], index) => {{
  input.value = index < 6 ? "b" : "a";
}});
blocked.quiz.dispatch("submit");
const quizResult = blocked.document.getElementById("quizResult");
if (!quizResult.children[0].textContent.startsWith("6 / 12")) {{
  throw new Error("mixed quiz answers did not produce the expected score");
}}
const missedList = quizResult.children[1];
if (!missedList || missedList.children.length !== 6) {{
  throw new Error("quiz did not render one feedback row per missed answer");
}}
missedList.children.forEach(row => {{
  const explanation = row.children.find(item => typeof item === "string");
  const reviewLink = row.children.find(item => typeof item !== "string" && item.href);
  if (!row.children[0].textContent.includes("正确答案") || !explanation?.includes("explanation")) {{
    throw new Error("missed-answer feedback omitted answer text or explanation");
  }}
  if (reviewLink?.href !== "#event-loop" || reviewLink.dataset.reviewSection !== "event-loop") {{
    throw new Error("missed-answer feedback omitted its direct review link");
  }}
}});
if (!quizResult.focused) throw new Error("quiz feedback did not receive focus");
blocked.quiz.dispatch("reset");
if (quizResult.textContent !== "完成后点击“提交答案”。" || quizResult.children.length !== 0) {{
  throw new Error("quiz reset did not restore the initial result state");
}}

if (!blocked.sidebar.inert || blocked.sidebar.attributes["aria-hidden"] !== "true") {{
  throw new Error("closed mobile sidebar remained in the accessibility tree");
}}
blocked.menuButton.click();
if (blocked.sidebar.inert || !blocked.sidebar.classList.contains("open")) {{
  throw new Error("opening the mobile sidebar did not restore interaction");
}}
if (blocked.menuButton.attributes["aria-expanded"] !== "true"
    || blocked.menuButton.attributes["aria-label"] !== "关闭课程目录") {{
  throw new Error("opening the mobile sidebar did not synchronize its button state");
}}
blocked.tocLink.click();
if (blocked.sidebar.classList.contains("open") || !blocked.sidebar.inert) {{
  throw new Error("TOC navigation did not make the closed sidebar inert");
}}
if (blocked.menuButton.attributes["aria-expanded"] !== "false"
    || blocked.menuButton.attributes["aria-label"] !== "打开课程目录") {{
  throw new Error("TOC navigation did not restore the menu button state");
}}
if (!blocked.document.getElementById("first-window").focused) {{
  throw new Error("TOC navigation left focus inside the hidden sidebar");
}}

blocked.menuButton.click();
blocked.document.dispatch("keydown", {{ key: "Escape" }});
if (!blocked.sidebar.inert || !blocked.menuButton.focused
    || blocked.menuButton.attributes["aria-label"] !== "打开课程目录") {{
  throw new Error("Escape did not close the sidebar and restore focus/state");
}}

const restored = runScenario({{
  "pd-educate-theme": "dark",
  "pd-educate-progress": JSON.stringify({{
    completed: ["pyside-intro", "removed-lesson"],
    lastActive: "removed-lesson",
  }}),
}}, false, false);
if (restored.document.documentElement.dataset.theme !== "dark") {{
  throw new Error("legacy bare theme was not restored");
}}
if (restored.document.getElementById("continueLearning").href !== "#pyside-intro") {{
  throw new Error("unknown last-active id was not rejected");
}}
const firstCheckbox = restored.lessons[0].lessonMeta.children[0].children[0];
const secondCheckbox = restored.lessons[1].lessonMeta.children[0].children[0];
if (!firstCheckbox.checked || secondCheckbox.checked) {{
  throw new Error("unknown completion id affected controls");
}}
console.log("runtime storage regression OK");
"""
    harness_path = tmp_path / "education-runtime.js"
    harness_path.write_text(harness, encoding="utf-8")
    completed = subprocess.run(
        [node, str(harness_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "runtime storage regression OK" in completed.stdout


def test_current_installation_guides_are_conda_first(project_root):
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    api = (project_root / "docs" / "API.md").read_text(encoding="utf-8")
    education = (project_root / "docs" / "educate" / "index.html").read_text(
        encoding="utf-8"
    )

    canonical_commands = (
        "conda create -n pd-diagnosis python=3.10 -y",
        "conda activate pd-diagnosis",
        "python -m pip install --upgrade pip",
        'python -m pip install -e ".[gui,dev]"',
    )
    for guide in (readme, api, education):
        for command in canonical_commands:
            assert command in guide

    assert "不要安装到 `base` 环境" in readme
    assert "Conda 负责创建和隔离 Python 环境" in readme
    assert "pip 只把当前项目及依赖安装进已经激活的 Conda 环境" in readme
    assert "不要同时激活 Conda 环境和 `.venv`" in readme
    assert "python -m venv .venv" not in readme
    assert "py -3.11 -m venv .venv" not in education
    assert "python -m pip install PySide6" not in education
    assert "Python 3.11.9" not in education
    assert "重建虚拟环境" not in education

    assert "不要把开发依赖安装到 Conda `base`" in api
    assert "不要同时激活 Conda 环境和 `.venv`" in api
    assert "Conda 负责隔离 Python 环境" in api
    assert "`python -m pip` 负责把当前源码及可选依赖安装进" in api

    assert "不要安装到 <code>base</code>" in education
    assert "不要同时激活 Conda 环境和 <code>.venv</code>" in education
    assert "Conda 负责环境隔离，pip 只负责把项目装进当前环境" in education

    assert "python -m pip install partial-discharge-diagnosis" in api
    assert 'python -m pip install -e ".[gui,train,dev]"' in readme
