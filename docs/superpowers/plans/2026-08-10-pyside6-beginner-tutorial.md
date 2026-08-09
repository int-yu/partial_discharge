# PySide6 Beginner Tutorial Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `docs/educate/index.html` into an extremely detailed, beginner-friendly PySide6 course that progresses from a minimal window to this repository's real SDK and desktop architecture.

**Architecture:** Keep one offline HTML document with two layers: a linear beginner curriculum and a searchable source-reference browser. Static HTML contains all essential lessons, while two inline scripts retain local course data and progressively enhance theme, progress, source search, copy buttons, and quizzes.

**Tech Stack:** Semantic HTML5, modern CSS, vanilla JavaScript, Python standard-library HTML parsing tests, pytest, Node.js syntax checking, PySide6 example source compiled with Python `compile()`.

## Global Constraints

- The learner already understands Python classes, `self`, type hints, packages, imports, and exceptions; do not add a Python-basics course.
- Start at PySide6 fundamentals and introduce one GUI concept at a time.
- Keep `docs/educate/index.html` as a single offline file with no CDN, remote font, external script, stylesheet, image, or build step.
- Do not change application source, model artifacts, data sets, SDK behavior, or public APIs.
- Preserve Chinese language metadata, semantic landmarks, responsive layout, dark theme, printing, keyboard operation, source search, and current project-implementation accuracy.
- Mark course content as `基础必学`, `项目必学`, or `进阶选学`.
- Each foundation lesson must include goals, setup, complete code, expected result, execution order, line-by-line explanation, key syntax, object relationships, one modification, common error, exercise, answer, and completion check.
- Use only safe DOM construction (`textContent` or static HTML) for data-driven content.
- If `localStorage` is unavailable, all static tutorial content must remain readable and interactive initialization must continue.

---

## File Structure

- Modify `docs/educate/index.html`: course content, lesson components, source-reference metadata, styles, progress behavior, quiz behavior, and all offline assets.
- Modify `tests/test_education_page.py`: structural, curriculum, offline, example-syntax, and JavaScript contracts.
- Reference `docs/superpowers/specs/2026-08-10-pyside6-beginner-tutorial-design.md`: approved scope and acceptance requirements; do not modify during implementation unless an actual contradiction is discovered.

No new runtime file is created because the approved deliverable is a portable single HTML document.

---

### Task 1: Lock the beginner curriculum contract and page shell

**Files:**
- Modify: `tests/test_education_page.py`
- Modify: `docs/educate/index.html:1-842`

**Interfaces:**
- Consumes: existing `_EducationPageAudit`, semantic landmarks, two-inline-script structure, `#toc` navigation.
- Produces: stable section IDs and reusable lesson CSS classes used by all later tasks.

- [ ] **Step 1: Write the failing curriculum and offline-resource tests**

Add these constants and assertions to `tests/test_education_page.py`:

```python
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


def test_beginner_curriculum_and_offline_contract(project_root):
    page = project_root / "docs" / "educate" / "index.html"
    text = page.read_text(encoding="utf-8")
    audit = _EducationPageAudit()
    audit.feed(text)

    assert BEGINNER_SECTION_IDS <= audit.ids
    assert {"基础必学", "项目必学", "进阶选学"} <= set(audit.text_parts)
    assert "data-level=\"foundation\"" in text
    assert "data-level=\"project\"" in text
    assert "data-level=\"advanced\"" in text
    assert "http://" not in text
    assert "https://" not in text
```

Extend `_EducationPageAudit.__init__` with `self.text_parts: list[str] = []`, and append stripped non-empty data in `handle_data` while preserving the existing script collection behavior.

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```powershell
python -m pytest tests/test_education_page.py::test_beginner_curriculum_and_offline_contract -v
```

Expected: FAIL because the new PySide6 section IDs and level markers do not yet exist.

- [ ] **Step 3: Add the curriculum navigation, section shell, and reusable styles**

In `docs/educate/index.html`:

- Rewrite the hero promise so it says the course begins with PySide6, not SDK architecture.
- Split `#toc` into `PySide6 基础`, `连接真实项目`, and `进阶与参考` groups.
- Add the exact section IDs from `BEGINNER_SECTION_IDS`.
- Move the existing SDK and source material after the foundation sections.
- Add CSS components `.level-badge`, `.lesson-goals`, `.expected-ui`, `.execution-steps`, `.line-explanation`, `.syntax-zoom`, `.object-map`, `.experiment`, `.mistake`, `.lesson-check`, `.lesson-nav`, and `.advanced-note`.
- Give every new section one of `data-level="foundation"`, `data-level="project"`, or `data-level="advanced"`.
- Add visible labels with the exact Chinese strings `基础必学`, `项目必学`, and `进阶选学`.

Use this section header pattern:

```html
<section class="chapter lesson" id="pyside-intro" data-title="认识 PySide6" data-level="foundation">
  <div class="lesson-meta">
    <span class="level-badge foundation">基础必学</span>
    <span>第 1 课</span>
  </div>
  <h2>PySide6、Qt 和你的 Python 程序是什么关系？</h2>
  <div class="lesson-goals" aria-label="本节学习目标">
    <strong>本节只学三件事</strong>
    <ol>
      <li>说清 Qt 与 PySide6 的关系。</li>
      <li>知道 QWidget 是界面对象的基础类型。</li>
      <li>知道下一课为什么要先创建 QApplication。</li>
    </ol>
  </div>
</section>
```

- [ ] **Step 4: Run structural tests**

Run:

```powershell
python -m pytest tests/test_education_page.py -v
```

Expected: all education-page tests PASS, including unique IDs, valid fragments, two scripts, and new curriculum IDs.

- [ ] **Step 5: Commit the page shell**

```powershell
git add docs/educate/index.html tests/test_education_page.py
git commit -m "docs: establish beginner PySide6 course shell"
```

---

### Task 2: Teach the first window and Qt event loop line by line

**Files:**
- Modify: `tests/test_education_page.py`
- Modify: `docs/educate/index.html` sections `#pyside-intro`, `#first-window`, `#event-loop`

**Interfaces:**
- Consumes: lesson components and IDs from Task 1.
- Produces: the canonical `data-python-example` markup and line-explanation format reused by later lessons.

- [ ] **Step 1: Add Python example extraction and lesson-template tests**

Add a second parser that collects code text from elements carrying `data-python-example`:

```python
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
```

Add:

```python
def test_foundation_examples_are_complete_python(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    audit = _PythonExampleAudit()
    audit.feed(text)
    required = {"first-window", "event-loop-timer"}
    assert required <= audit.examples.keys()
    for name in required:
        compile(audit.examples[name], f"<{name}>", "exec")


def test_first_lessons_use_full_teaching_template(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
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
        assert marker in text
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_education_page.py::test_foundation_examples_are_complete_python tests/test_education_page.py::test_first_lessons_use_full_teaching_template -v
```

Expected: FAIL because complete examples and template labels are absent.

- [ ] **Step 3: Write the PySide6 relationship and installation lesson**

Explain PySide6 as Python bindings for Qt, distinguish Python objects from underlying Qt behavior, and show these exact verification commands:

```powershell
python --version
python -m pip show PySide6
python -c "import PySide6; print(PySide6.__version__)"
```

For each command, state expected output shape and give fixes for `No module named PySide6`, wrong virtual environment, and unsupported Python versions.

- [ ] **Step 4: Add the complete first-window example and line table**

Use an unhighlighted, compilable code node:

```html
<pre><code data-python-example="first-window">import sys

from PySide6.QtWidgets import QApplication, QLabel

app = QApplication(sys.argv)
label = QLabel("你好，PySide6！")
label.resize(320, 120)
label.show()
exit_code = app.exec()
raise SystemExit(exit_code)</code></pre>
```

Explain all nine executable/import lines in a `.line-explanation` table. Explicitly explain `sys.argv`, why one `QApplication` exists, why `show()` and `exec()` are separate, what `exit_code` means, and why closing the window lets `exec()` return.

- [ ] **Step 5: Add the event-loop timer example and common mistakes**

Provide a complete `QTimer.singleShot` example named `event-loop-timer`. Contrast chronological Python execution with event-driven callbacks. Include wrong examples for missing `show()`, missing `exec()`, and constructing a widget before `QApplication`, each with symptom, reason, fixed code, and verification.

- [ ] **Step 6: Add exercises, answers, and checks**

Exercises must ask the learner to change title text, window size, and timer callback text. Answers contain complete programs inside `<details>`. Completion checks ask the learner to explain the four-object relation `Python process → QApplication → QLabel → event loop`.

- [ ] **Step 7: Run tests and commit**

```powershell
python -m pytest tests/test_education_page.py -v
git add docs/educate/index.html tests/test_education_page.py
git commit -m "docs: teach first PySide6 window step by step"
```

Expected: education-page tests PASS and both Python examples compile.

---

### Task 3: Teach widgets, layouts, and signals/slots through runnable examples

**Files:**
- Modify: `tests/test_education_page.py`
- Modify: `docs/educate/index.html` sections `#widgets`, `#layouts`, `#signals-slots`

**Interfaces:**
- Consumes: `data-python-example`, lesson template, line tables, mistake cards.
- Produces: examples `widgets-form`, `nested-layouts`, and `signals-slots`.

- [ ] **Step 1: Extend the required example test**

Change the required example set to:

```python
required = {
    "first-window",
    "event-loop-timer",
    "widgets-form",
    "nested-layouts",
    "signals-slots",
}
```

Run the test and expect FAIL with the three missing example names.

- [ ] **Step 2: Write the widgets lesson**

Build one complete form using `QLabel`, `QLineEdit`, `QComboBox`, `QPushButton`, and `QTextEdit`. Explain constructor arguments, instance references, getters such as `text()`/`currentText()`, setters such as `setText()`, read-only output, and why controls must remain reachable through `self` inside a class.

The expected-result card must describe every visible row and what changes after clicking the button.

- [ ] **Step 3: Write the layout lesson**

Build `nested-layouts` with a `QVBoxLayout` containing a `QFormLayout` and a `QHBoxLayout`. Explain geometry ownership, insertion order, stretch factors, margins, spacing, nesting, and why one widget cannot belong to two layouts. Include a text wireframe showing the expected arrangement.

- [ ] **Step 4: Write the signals-and-slots lesson**

Build a class-based counter using `clicked.connect`, `@Slot()`, and a label update. Explain the difference between `connect(self.increment)` and `connect(self.increment())`, signal emission, function object storage, callback timing, and automatic argument delivery. Add a separate small comparison for `lambda checked, value=value: ...` without making it the main beginner pattern.

- [ ] **Step 5: Add targeted mistakes and exercises**

Cover premature slot invocation, repeated `connect`, lost object references, and adding one widget to multiple layouts. Exercises: add a reset button, show entered text, and change layout spacing. Each answer is a complete compilable program.

- [ ] **Step 6: Verify and commit**

```powershell
python -m pytest tests/test_education_page.py -v
git add docs/educate/index.html tests/test_education_page.py
git commit -m "docs: explain widgets layouts and signals in depth"
```

Expected: all required Python examples compile and education tests PASS.

---

### Task 4: Teach QMainWindow, dialogs, page navigation, and QSS

**Files:**
- Modify: `tests/test_education_page.py`
- Modify: `docs/educate/index.html` sections `#main-window-basics`, `#dialogs`, `#stacked-pages`, `#qss`

**Interfaces:**
- Consumes: class-based widget and signal knowledge from Task 3.
- Produces: examples `main-window`, `file-dialog`, `stacked-pages`, and `qss-states`.

- [ ] **Step 1: Add the four example names to the compile test and verify failure**

Add `"main-window"`, `"file-dialog"`, `"stacked-pages"`, and `"qss-states"` to `required`, run the focused test, and expect FAIL listing missing examples.

- [ ] **Step 2: Write the QMainWindow lesson**

Create a complete window with central widget, vertical layout, menu action, toolbar action, and status message. Explain why `QMainWindow` owns special regions, why layouts go on a central `QWidget`, action reuse, `statusBar()` lazy access, and application/window/widget ownership.

- [ ] **Step 3: Write the dialog lesson**

Use `QFileDialog.getOpenFileName` and `QMessageBox.information`. Explain the returned `(path, selected_filter)` tuple, cancellation as an empty path, filter syntax, parent argument, modal behavior, and why a retained parent prevents unexpected lifetime issues.

- [ ] **Step 4: Write the stacked-page lesson**

Create two navigation buttons and a `QStackedWidget`. Explain index order, `setCurrentIndex`, page object ownership, and how this maps to the real project's sidebar without yet introducing SDK calls.

- [ ] **Step 5: Write the QSS lesson**

Demonstrate type selectors, `#objectName`, pseudo states, and dynamic-property selectors. Show `setObjectName`, `setProperty`, and the repolish step when a dynamic property changes. Explain that QSS changes presentation, not business behavior.

- [ ] **Step 6: Add mistakes, exercises, verify, and commit**

Include direct-layout-on-`QMainWindow`, ignored dialog cancellation, incorrect stacked index, and color-only status communication. Run:

```powershell
python -m pytest tests/test_education_page.py -v
git add docs/educate/index.html tests/test_education_page.py
git commit -m "docs: teach practical PySide6 window patterns"
```

Expected: education tests PASS and four new examples compile.

---

### Task 5: Build the guided diagnosis UI and teach background work

**Files:**
- Modify: `tests/test_education_page.py`
- Modify: `docs/educate/index.html` sections `#mini-project`, `#threading`

**Interfaces:**
- Consumes: widgets, layouts, signals, QMainWindow, dialogs, stacked pages, and QSS lessons.
- Produces: examples `diagnosis-ui` and `thread-pool`; conceptual bridge to the repository's `MainWindow` and workers.

- [ ] **Step 1: Add mini-project contract tests**

Add the two example names to the compile set and assert these six stage labels appear:

```python
for stage in (
    "步骤 1：窗口骨架",
    "步骤 2：文件选择",
    "步骤 3：输入状态",
    "步骤 4：模拟诊断",
    "步骤 5：结果卡片",
    "步骤 6：错误恢复",
):
    assert stage in text
```

Run the focused tests and expect failure.

- [ ] **Step 2: Write the six-stage guided mini-project**

Each stage shows the full current program, highlights only the newly added lines in the explanation, states the visible difference from the previous stage, and includes one checkpoint. The final `diagnosis-ui` example must run without this repository or a model by using `QTimer.singleShot` to simulate a diagnosis result.

- [ ] **Step 3: Explain UI state as an explicit state machine**

Document `idle → file selected → running → success/error → idle`. For each state list enabled controls, visible message, and allowed next actions. Explain why buttons are disabled during work and why success and failure must share a final cleanup path.

- [ ] **Step 4: Write the thread-pool lesson**

Provide a complete example using `QObject` signals, `QRunnable`, `QThreadPool.globalInstance()`, `result`, `error`, and `finished`. The worker may simulate work with a short operation but must never update a QWidget. Explain object thread affinity, queued signal delivery, exception-to-string conversion, and main-thread cleanup.

- [ ] **Step 5: Add failure cases and map them to the real project**

Cover synchronous sleep in a slot, QWidget access inside `run()`, missing error signal, duplicate task starts, and buttons never restored after failure. End with a mapping table from tutorial names to `SingleDiagnosisTask`, `WorkerSignals`, `DiagnosisService`, and the real result slots.

- [ ] **Step 6: Verify and commit**

```powershell
python -m pytest tests/test_education_page.py -v
git add docs/educate/index.html tests/test_education_page.py
git commit -m "docs: add guided diagnosis UI and threading course"
```

Expected: examples compile, stage assertions pass, and all education tests PASS.

---

### Task 6: Rebuild the SDK and project bridge around prior PySide6 knowledge

**Files:**
- Modify: `docs/educate/index.html` sections `#sdk`, `#project-map`, `#architecture`, `#folders`, `#flows`, `#run`, `#hardening`
- Modify: `tests/test_education_page.py`

**Interfaces:**
- Consumes: completed PySide6 course and current repository source names.
- Produces: beginner-readable SDK usage and two accurate project call chains.

- [ ] **Step 1: Add bridge-content tests**

Assert the page contains the exact beginner bridge labels:

```python
for marker in (
    "先不用界面：直接调用 SDK",
    "把教程里的对象换成项目里的对象",
    "应用启动链",
    "单文件诊断链",
    "第一次阅读只追这一条线",
):
    assert marker in text
```

Run the test and expect FAIL for the new labels.

- [ ] **Step 2: Rewrite the SDK introduction as a runnable progression**

Keep the coffee-machine analogy, but first distinguish library, API, SDK, framework, and application with a single consistent example. Then show one complete SDK-only script, explain every line and expected printed fields, and state that the current sample model is an engineering interface demonstration until real-scene data is connected.

- [ ] **Step 3: Add the tutorial-to-project mapping**

Create a table mapping `QApplication`, tutorial `DiagnosisWindow`, `QThreadPool`, tutorial worker, result signal, and error signal to the actual files/classes. Explicitly state which earlier lesson to revisit for each project concept.

- [ ] **Step 4: Rewrite the startup and diagnosis chains**

For each chain, show:

- trigger;
- exact file and callable;
- input entering the step;
- output leaving the step;
- thread used;
- possible error;
- next step.

Keep current implementation details: lightweight launcher, dependency construction, private single-thread pool, immutable `SingleDiagnosisOutcome`, service persistence isolation, and UI updates on the GUI thread.

- [ ] **Step 5: Move advanced engineering details behind clear skip guidance**

Mark SQLite, bundle validation, immutable snapshots, artifact hashes, pagination, CSV export, and model internals as `进阶选学`. Each section starts with “初读只需要知道” and “暂时可以跳过”.

- [ ] **Step 6: Verify current source names and commit**

Use read-only searches to confirm all mentioned names:

```powershell
rg -n "class SingleDiagnosisTask|class SingleDiagnosisOutcome|class DiagnosisService|class DiagnosisEngine|def main" src/pd_diagnosis
python -m pytest tests/test_education_page.py -v
git add docs/educate/index.html tests/test_education_page.py
git commit -m "docs: bridge PySide6 lessons to the real project"
```

Expected: every referenced symbol exists and education tests PASS.

---

### Task 7: Enhance source reference metadata and resilient progress behavior

**Files:**
- Modify: `docs/educate/index.html` source data and final interaction script
- Modify: `tests/test_education_page.py`

**Interfaces:**
- Consumes: `window.SOURCE_FILES`, `renderSourceFile`, `renderSourceNav`, theme and scroll behavior.
- Produces: `level`, `prerequisites`, `firstRead`, `skipOnFirstPass` metadata; safe storage helpers; per-lesson completion controls.

- [ ] **Step 1: Add source-metadata and progress tests**

Assert the source data and script contain these contracts:

```python
for marker in (
    "prerequisites:",
    "firstRead:",
    "skipOnFirstPass:",
    "pd-educate-progress",
    "continueLearning",
    "lesson-complete",
):
    assert marker in text
```

Also extend the parser to collect external resource attributes and assert no `script[src]`, `link[href]`, `img[src]`, CSS `url(http`, or CSS `url(https` reference is present.

Run the focused test and expect FAIL.

- [ ] **Step 2: Add learning metadata to every source file record**

Each `SOURCE_FILES` entry receives:

```javascript
level: "项目必学",
prerequisites: "第 7 课：信号与槽；第 14 课：后台任务",
firstRead: "先看任务如何发出 result/error/finished，不需要记住所有信号名称。",
skipOnFirstPass: "批量进度和导出取消细节可以第二遍再看。",
```

Use content appropriate to each real file. Configuration, training, migration, model internals, and most tests are `进阶选学`; key UI, engine, service, and types files are `项目必学`.

- [ ] **Step 3: Render beginner guidance before source parts**

Update `renderSourceFile` to create text-only elements for level, prerequisites, first-read focus, and skip guidance. Extend source search indexing to include all four fields. Do not use `innerHTML`.

- [ ] **Step 4: Add resilient local progress persistence**

Add:

```javascript
function readStoredJson(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch (_) {
    return fallback;
  }
}

function writeStoredJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (_) {
    // The static course remains usable when storage is blocked.
  }
}
```

Render one `.lesson-complete` checkbox per linear lesson, store completed section IDs under `pd-educate-progress`, update visible completion totals, remember the last active section, and set `#continueLearning` to it. Validate restored IDs against existing lesson IDs before using them.

- [ ] **Step 5: Make theme persistence use the safe helpers**

Replace direct `localStorage.getItem/setItem` calls so blocked storage cannot abort the script. Preserve system-theme fallback.

- [ ] **Step 6: Run JavaScript and education tests, then commit**

```powershell
python -m pytest tests/test_education_page.py -v
git add docs/educate/index.html tests/test_education_page.py
git commit -m "docs: add guided source reading and course progress"
```

Expected: both inline scripts pass Node syntax checking, source search still renders, and progress markers exist.

---

### Task 8: Finish exercises, feedback, accessibility, and full verification

**Files:**
- Modify: `docs/educate/index.html` sections `#exercises`, `#quiz`, `#glossary`, footer and print/mobile styles
- Modify: `tests/test_education_page.py`

**Interfaces:**
- Consumes: all course sections, example names, source metadata, progress state.
- Produces: final beginner learning loop and release-quality verification.

- [ ] **Step 1: Add final acceptance tests**

Require at least twelve quiz questions, answer explanations, lesson links, lesson navigation, and accessible progress status:

```python
def test_final_learning_feedback_contract(project_root):
    text = (project_root / "docs" / "educate" / "index.html").read_text(encoding="utf-8")
    assert text.count('class="quiz-question"') >= 12
    assert "答案解释" in text
    assert "lesson-nav" in text
    assert 'aria-live="polite"' in text
    assert "禁用 JavaScript 时仍可阅读" in text
```

Run the test and expect FAIL because the current quiz has five questions and no per-answer explanation.

- [ ] **Step 2: Replace broad exercises with staged practice**

Provide foundation exercises after widgets, layouts, signals, dialogs, pages, styling, and threading; project exercises after SDK and call-chain lessons. Each exercise states prerequisite lesson, expected visible result, constraints, hints, complete answer, and self-verification.

- [ ] **Step 3: Expand the quiz with explanatory feedback**

Create at least twelve questions covering application/event loop, parent ownership, layouts, signals/slots, QMainWindow central widget, dialog cancellation, stacked pages, QSS boundaries, GUI-thread rules, SDK entry, service responsibility, and model-feature compatibility. Store answer text and corresponding section ID; after submission, list each missed question with explanation and a direct review link.

- [ ] **Step 4: Expand and cross-link the glossary**

Add beginner definitions for binding, widget, parent/child, layout, event, event loop, signal, slot, callback, main thread, worker, thread pool, modal dialog, QSS, SDK, service, dependency injection, persistence, bundle, and immutable snapshot. Link first-use explanations to glossary anchors and glossary entries back to their lesson.

- [ ] **Step 5: Perform accessibility, responsive, no-JS, and print review**

Ensure interactive controls have labels, focus states remain visible, tables scroll on narrow screens, answer `<details>` remain printable, progress controls do not rely only on color, and a static note states `禁用 JavaScript 时仍可阅读全部核心课程；进度、搜索和自测反馈不可用。`

- [ ] **Step 6: Run the complete verification suite**

Run:

```powershell
python -m pytest tests/test_education_page.py -v
python -m pytest
ruff check .
mypy src/pd_diagnosis
git diff --check
```

Expected:

- education tests PASS;
- full project tests PASS;
- Ruff reports no errors;
- mypy reports no errors;
- `git diff --check` emits no output.

- [ ] **Step 7: Inspect the rendered document locally**

Open `docs/educate/index.html` in a browser and verify desktop and narrow widths, theme toggle, continue link, completion persistence, source search, copy buttons, answer disclosure, quiz review links, keyboard focus, and print preview. Confirm the first three lessons can be followed without opening project source files.

- [ ] **Step 8: Commit the completed tutorial**

```powershell
git add docs/educate/index.html tests/test_education_page.py
git commit -m "docs: complete beginner PySide6 project course"
```

Record exact verification counts in the final handoff rather than assuming the previous 70-test baseline remains unchanged.
