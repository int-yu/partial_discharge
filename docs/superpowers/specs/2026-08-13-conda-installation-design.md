# Conda-first Installation Documentation Design

## Goal

Make Conda the default environment-management path for repository users while keeping pip as the package installer inside the activated Conda environment.

## User-facing contract

- Create a dedicated environment named `pd-diagnosis` with Python 3.10.
- Explicitly advise users not to install project dependencies into Conda `base`.
- Explain that Conda owns environment isolation while `python -m pip` installs this editable project and its extras into the active environment.
- Do not mix the Conda environment with the repository's `.venv` workflow.
- Use `.[gui,dev]` for normal GUI development and document `train` as an optional extra.
- Keep the normal PyPI SDK installation command for external SDK consumers.
- Preserve legacy environment files as historical references, clearly non-authoritative for the current project.

## Files

- `README.md`: replace the venv-first setup with the canonical Conda workflow and repeatable start commands.
- `docs/API.md`: add the Conda development setup while preserving the PyPI SDK command.
- `docs/educate/index.html`: teach Conda/pip responsibility boundaries, update troubleshooting and embedded source metadata.
- `tests/test_education_page.py`: enforce consistency between the three user-facing installation guides.

## Verification

- The documentation contract test must fail before the edits and pass afterward.
- Education-page tests, the full pytest suite, Ruff, mypy, and `git diff --check` must pass.
- Only documentation and its contract test may change; no dependency versions or production code change.
