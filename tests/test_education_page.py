from __future__ import annotations

import ast
import shutil
import subprocess
from html import unescape
from html.parser import HTMLParser
import re

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


def test_service_source_lesson_matches_persistence_isolation_contract(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    service_lesson = text.partition('path:"src/pd_diagnosis/service.py"')[2].partition(
        'path:"src/pd_diagnosis/storage.py"'
    )[0]

    assert service_lesson
    assert "数据库写入异常目前会传播" not in text
    for marker in (
        "PERSISTENCE_EXCEPTIONS",
        "warnings=(*result.warnings, PERSISTENCE_WARNING_TEXT)",
        "保存成功结果失败时仍返回诊断结果",
        "记录诊断错误失败时仍抛出原始诊断异常",
    ):
        assert marker in service_lesson
    assert "保存成功结果失败时会返回附加 warning 的结果" in text
    assert "保存诊断错误本身失败时仍继续抛出原始 <code>DiagnosisError</code>" in text


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
