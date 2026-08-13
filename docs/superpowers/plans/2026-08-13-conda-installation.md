# Conda-first Installation Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all current installation instructions use a dedicated Conda environment as the default setup.

**Architecture:** Treat `README.md` as the quick-start authority, `docs/API.md` as the SDK/developer reference, and the offline education page as the beginner explanation. A single pytest contract keeps their commands and environment guidance aligned.

**Tech Stack:** Markdown, standalone HTML, pytest, PowerShell/Conda commands.

## Global Constraints

- Use environment name `pd-diagnosis` and Python `3.10` in the canonical commands.
- Never recommend installing project dependencies into Conda `base`.
- Use `python -m pip` only after `conda activate pd-diagnosis`.
- Do not change `pyproject.toml`, dependency ranges, application code, model files, or data.

---

### Task 1: Enforce and implement the Conda-first documentation contract

**Files:**
- Modify: `README.md`
- Modify: `docs/API.md`
- Modify: `docs/educate/index.html`
- Test: `tests/test_education_page.py`

**Interfaces:**
- Consumes: the existing `.[gui,dev]` editable-install extra and `python -m pd_diagnosis` entry point.
- Produces: one consistent Conda-first setup shown in all three documentation surfaces.

- [ ] **Step 1: Add a failing consistency test**

Assert that all three documents contain the canonical create/activate/install commands, that README explains `base` and Conda/pip responsibilities, and that the old `python -m venv` default is absent from current instructions.

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `python -m pytest tests/test_education_page.py -q --basetemp .pytest-tmp/conda-red`

Expected: failure because README and the education page still teach `.venv`.

- [ ] **Step 3: Update all installation instructions**

Use the exact canonical sequence:

```powershell
conda create -n pd-diagnosis python=3.10 -y
conda activate pd-diagnosis
python -m pip install --upgrade pip
python -m pip install -e ".[gui,dev]"
python -m pd_diagnosis
```

Keep the SDK-only PyPI command and describe `.[train]` as optional.

- [ ] **Step 4: Update education source metadata**

Recalculate README/API declared line counts and replace their installation snippets and explanations in `SOURCE_FILES`.

- [ ] **Step 5: Verify GREEN and project quality**

Run the education tests, full pytest suite, Ruff, mypy, and `git diff --check`.

- [ ] **Step 6: Commit and publish**

Stage only the specification, plan, three documentation files, and documentation test. Commit tersely and push `codex/pyside6-beginner-tutorial` to `origin`.
