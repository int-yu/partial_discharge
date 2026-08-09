# Project Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden installation, model loading, inference, persistence, PySide6 task handling, testing, and release automation without changing the current training or test datasets.

**Architecture:** Keep `DiagnosisEngine` as the stable UI-independent SDK boundary and `DiagnosisService` as the persistence-aware application boundary. Add strict artifact validation and installed-resource discovery below the engine, isolate persistence failures from inference results, move immutable task context across Qt threads, and keep release checks executable from a clean virtual environment.

**Tech Stack:** Python 3.10–3.12, NumPy, PyTorch, SQLite, PySide6 6, Matplotlib, setuptools, pytest, Ruff, mypy, GitHub Actions.

## Global Constraints

- Do not modify, rename, delete, deduplicate, or repartition any file under `data/train` or `data/test`.
- Preserve the existing stable imports from `pd_diagnosis.__init__`.
- Preserve the current `legacy-v1` feature formulas and golden probabilities.
- The desktop application remains Windows-first, Chinese, keyboard/mouse operated, and usable at 1024×720.
- All behavior changes follow red-green-refactor TDD; configuration-only changes are validated by project-configuration tests.
- Model loading must never enable pickle and must reject bundle files that escape the selected bundle directory.

---

### Task 1: Installed Default Model and Friendly Launcher

**Files:**
- Create: `src/pd_diagnosis/launcher.py`
- Modify: `src/pd_diagnosis/paths.py`
- Modify: `src/pd_diagnosis/__main__.py`
- Modify: `pyproject.toml`
- Test: `tests/test_paths.py`
- Test: `tests/test_launcher.py`

**Interfaces:**
- Produces: `installed_model_path() -> Path` and `default_model_path() -> Path`.
- Produces: `pd_diagnosis.launcher.main(argv: Sequence[str] | None = None) -> int`.
- Consumes: `PD_DIAGNOSIS_MODEL`, repository-local `models/default`, and setuptools-installed `share/partial-discharge-diagnosis/models/default`.

- [x] **Step 1: Write failing installed-model path tests**

```python
def test_default_model_path_falls_back_to_installed_data(monkeypatch, tmp_path):
    installed = tmp_path / "share" / "partial-discharge-diagnosis" / "models" / "default"
    installed.mkdir(parents=True)
    (installed / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PD_DIAGNOSIS_MODEL", raising=False)
    monkeypatch.setattr(paths, "installed_model_path", lambda: installed)
    assert paths.default_model_path() == installed
```

- [x] **Step 2: Run `python -m pytest tests/test_paths.py -v` and verify failure because `installed_model_path` does not exist**
- [x] **Step 3: Implement environment → repository → installed-data precedence using `sysconfig.get_path("data")`**
- [x] **Step 4: Add setuptools `data-files` entries for manifest, weights, and scaler**
- [x] **Step 5: Write and fail a launcher test that simulates a missing `PySide6` import and expects an actionable Chinese error plus exit code 2**
- [x] **Step 6: Implement the lazy launcher and point `pd-diagnosis` plus `__main__.py` to it**
- [x] **Step 7: Run path/launcher/public API tests and commit**

### Task 2: Strict Model Bundle Contract

**Files:**
- Create: `src/pd_diagnosis/artifacts.py`
- Modify: `src/pd_diagnosis/bundle.py`
- Modify: `src/pd_diagnosis/migration.py`
- Modify: `src/pd_diagnosis/experimental/training.py`
- Modify: `models/default/manifest.json`
- Test: `tests/test_bundle.py`

**Interfaces:**
- Produces: `sha256_file(path: Path) -> str`.
- Produces: `resolve_bundle_artifact(root: Path, relative_name: object, field: str) -> Path`.
- Extends: `ModelBundle.confidence_warning_threshold: float`.

- [x] **Step 1: Add failing tests for missing hashes, unsupported architecture, path traversal, empty/duplicate classes, non-positive scaler scale, and malformed required fields**
- [x] **Step 2: Run each new test and confirm it fails for the intended missing validation**
- [x] **Step 3: Implement strict manifest key/type validation and require `classification-mlp-v1`**
- [x] **Step 4: Resolve artifacts and verify `artifact.is_relative_to(root)` after `.resolve()`**
- [x] **Step 5: Require non-empty SHA-256 strings, non-empty unique class names, continuous IDs, finite means, and strictly positive scales**
- [x] **Step 6: Add optional manifest threshold validation in `[0.0, 1.0]`, defaulting to `0.6` for schema version 1 compatibility**
- [x] **Step 7: Replace private `_sha256` imports with `artifacts.sha256_file` and update bundle writers**
- [x] **Step 8: Run bundle, migration, engine, and golden tests and commit**

### Task 3: Inference and Input Failure Boundaries

**Files:**
- Modify: `src/pd_diagnosis/features.py`
- Modify: `src/pd_diagnosis/signal_io.py`
- Modify: `src/pd_diagnosis/engine.py`
- Modify: `src/pd_diagnosis/types.py`
- Test: `tests/test_signal_io.py`
- Test: `tests/test_engine.py`
- Test: `tests/test_types.py`

**Interfaces:**
- `validate_signal` returns an owned float32 snapshot.
- `DiagnosisEngine.diagnose` rejects non-finite features, normalized inputs, logits, and probabilities.
- `BatchDiagnosisItem` enforces exactly one of `result` or `error`.

- [x] **Step 1: Write a failing `OSError` wrapping test for `read_txt_signal`**
- [x] **Step 2: Implement `except OSError as exc: raise InvalidSignalError(...) from exc`**
- [x] **Step 3: Write a failing signal-snapshot test that mutates the caller array after validation**
- [x] **Step 4: Make `validate_signal` return `np.array(..., copy=True)` without changing golden features**
- [x] **Step 5: Write failing engine tests using monkeypatched features/model outputs containing NaN or infinity**
- [x] **Step 6: Add finite checks with `DiagnosisError` messages at preprocessing and inference boundaries**
- [x] **Step 7: Write failing tests for invalid `BatchDiagnosisItem` states and implement `__post_init__`**
- [x] **Step 8: Replace hard-coded warning threshold and input size with bundle threshold and `len(FEATURE_NAMES)`**
- [x] **Step 9: Run all core SDK tests and commit**

### Task 4: Persistence Semantics, Schema, and Logging

**Files:**
- Create: `src/pd_diagnosis/logging_config.py`
- Modify: `src/pd_diagnosis/errors.py`
- Modify: `src/pd_diagnosis/paths.py`
- Modify: `src/pd_diagnosis/service.py`
- Modify: `src/pd_diagnosis/storage.py`
- Modify: `src/pd_diagnosis/ui/app.py`
- Modify: `src/pd_diagnosis/ui/workers.py`
- Test: `tests/test_service.py`
- Test: `tests/test_storage.py`
- Test: `tests/test_logging_config.py`

**Interfaces:**
- Produces: `configure_logging(log_path: Path | None = None) -> Path`.
- Produces: `PersistenceWarning` text appended to `DiagnosisResult.warnings` when inference succeeds but history persistence fails.
- Storage retains schema version 1 compatibility and uses SQLite UPSERT instead of REPLACE.

- [x] **Step 1: Write a failing service test where `save_result` raises and the diagnosis result is still returned with a persistence warning**
- [x] **Step 2: Write a failing service test where saving an error fails but the original `DiagnosisError` remains the raised exception**
- [x] **Step 3: Implement narrow persistence exception handling, `dataclasses.replace`, and structured logger calls**
- [x] **Step 4: Write failing storage tests proving an UPSERT updates without delete semantics and schema metadata contains exactly one version row**
- [x] **Step 5: Replace `INSERT OR REPLACE` with `ON CONFLICT(run_id) DO UPDATE` and harden schema version storage**
- [x] **Step 6: Write a failing rotating-log initialization test using a temporary path**
- [x] **Step 7: Implement application log setup, log startup context, and preserve worker tracebacks with `logger.exception`**
- [x] **Step 8: Run service/storage/logging tests and commit**

### Task 5: Immutable Qt Task Results and Controlled Concurrency

**Files:**
- Modify: `src/pd_diagnosis/ui/workers.py`
- Modify: `src/pd_diagnosis/ui/main_window.py`
- Test: `tests/test_workers.py`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**
- Produces: `SingleDiagnosisOutcome(path: str, samples: np.ndarray, result: DiagnosisResult)`.
- `SingleDiagnosisTask` reads the selected file exactly once and emits an outcome that binds samples and result to the same path.
- `MainWindow` uses a local `QThreadPool` with `maxThreadCount(1)`.

- [x] **Step 1: Write a failing direct worker test asserting one read, one persisted result, and an emitted immutable outcome**
- [x] **Step 2: Implement `SingleDiagnosisOutcome` and diagnose a constructed `Signal` from the worker snapshot**
- [x] **Step 3: Write a failing UI test that changes `single_path` before rendering and asserts the outcome path/samples remain authoritative**
- [x] **Step 4: Update `_show_single_result` to consume the outcome and remove its second file read**
- [x] **Step 5: Disable path editing while a single task runs and restore it on `finished`**
- [x] **Step 6: Replace the global pool with a window-owned serialized pool to prevent simultaneous model access**
- [x] **Step 7: Run worker/UI/core tests and commit**

### Task 6: UI Settings, Locale, Accessibility, and Dynamic Model Information

**Files:**
- Create: `src/pd_diagnosis/ui/formatting.py`
- Modify: `src/pd_diagnosis/ui/main_window.py`
- Modify: `src/pd_diagnosis/ui/charts.py`
- Modify: `src/pd_diagnosis/ui/theme.py`
- Test: `tests/test_ui_formatting.py`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**
- Produces: `display_time(value: str, locale: QLocale | None = None) -> str` with UTC-to-local conversion.
- MainWindow optionally consumes injected `QSettings` for deterministic tests.

- [x] **Step 1: Write failing formatting tests for UTC ISO timestamps and invalid fallback text**
- [x] **Step 2: Implement timezone conversion and locale-aware short date/time output**
- [x] **Step 3: Write failing UI tests for persisted theme, key accessible names, and dynamic feature schema/sampling rate text**
- [x] **Step 4: Inject/load/save QSettings for theme, geometry, and splitter state**
- [x] **Step 5: Add accessible names/descriptions for navigation, paths, tables, probability/PRPD/waveform canvases, and result labels**
- [x] **Step 6: Remove hard-coded `legacy-v1` and `1 MHz` settings text in favor of bundle values**
- [x] **Step 7: Remove the global QSS pixel font override so the application point-size font can respect DPI and large-font settings**
- [x] **Step 8: Run UI tests in offscreen mode and commit**

### Task 7: History Pagination and Background Export

**Files:**
- Create: `src/pd_diagnosis/ui/history_export.py`
- Modify: `src/pd_diagnosis/ui/workers.py`
- Modify: `src/pd_diagnosis/ui/main_window.py`
- Test: `tests/test_history_export.py`
- Test: `tests/test_workers.py`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**
- Produces: `export_history_csv(records: Iterable[HistoryRecord], path: Path) -> int`.
- Produces: `HistoryExportTask` progress/error/finished signals.
- History UI pages through repository results using fixed `PAGE_SIZE = 100` and offset.

- [x] **Step 1: Write failing CSV tests for UTF-8 BOM, field order, quoting, and exported row count**
- [x] **Step 2: Extract and implement pure CSV export**
- [x] **Step 3: Write failing worker tests for progress, errors, and completion**
- [x] **Step 4: Implement background export and keep all QWidget updates in the GUI thread**
- [x] **Step 5: Write failing UI tests for next/previous page boundaries**
- [x] **Step 6: Add paging controls and query-reset behavior using `limit=100, offset=...`**
- [x] **Step 7: Run history/storage/UI tests and commit**

### Task 8: Project Quality and CI Contract

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `src/pd_diagnosis/py.typed`
- Create: `tests/test_project_config.py`
- Modify: `pyproject.toml`
- Modify: `README.md`

**Interfaces:**
- CI installs `.[gui,dev]`, runs Ruff, mypy, and pytest on Windows with Python 3.10, 3.11, and 3.12.
- Packaging includes `py.typed` and model data files.

- [x] **Step 1: Write failing project-config tests for CI matrix, package data, project URL, and tool configuration**
- [x] **Step 2: Add Ruff and mypy to dev dependencies with compatible version ranges**
- [x] **Step 3: Add conservative Ruff rules and mypy configuration that checks the package without requiring strict third-party stubs**
- [x] **Step 4: Add Windows CI with `QT_QPA_PLATFORM=offscreen` and `MPLBACKEND=QtAgg`**
- [x] **Step 5: Add repository URL metadata and `py.typed`; do not select a license without explicit owner approval**
- [x] **Step 6: Document clean virtual-environment installation, model resolution precedence, logs, and test commands**
- [x] **Step 7: Run config tests, full tests, available local quality checks, and commit**

### Task 9: Installed Artifact and Regression Verification

**Files:**
- Modify: `tests/test_public_api.py`
- Modify: `docs/API.md`
- Modify: `docs/MODEL_BUNDLE.md`
- Modify: `docs/educate/index.html`

**Interfaces:**
- Verifies wheel/install behavior without changing SDK import names.

- [ ] **Step 1: Add a subprocess test proving public SDK import still avoids PySide6**
- [ ] **Step 2: Build wheel and sdist in an isolated output directory**
- [ ] **Step 3: Inspect the wheel and verify all three default model files and `py.typed` are present**
- [ ] **Step 4: Install the wheel into a temporary virtual environment and launch from outside the repository**
- [ ] **Step 5: Run full pytest, Ruff, mypy, and JavaScript/HTML checks for the education page**
- [ ] **Step 6: Update API, bundle, and educational documentation to match final behavior**
- [ ] **Step 7: Review `git diff`, confirm no dataset changes, and create the final implementation commit**
