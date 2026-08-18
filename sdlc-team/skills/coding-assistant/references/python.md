# Python conventions

> Verify against `pyproject.toml` before applying. Packaging and lint tooling in this
> ecosystem shifts frequently — confirm, do not assume.

## Detect first

```bash
grep -A5 -E '^\[(project|tool\.poetry|build-system)\]' pyproject.toml 2>/dev/null
grep -E 'requires-python|python =' pyproject.toml setup.cfg 2>/dev/null
ls -1 uv.lock poetry.lock Pipfile.lock requirements*.txt 2>/dev/null
```

The lockfile decides the workflow: `uv add`, `poetry add`, or `pip install -r`. Match the
declared `requires-python` — do not use syntax newer than the floor it supports.

## Style

- Follow the configured formatter (`ruff format`, `black`) and its line length. Do not
  reformat files you did not otherwise touch.
- `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_SNAKE` for
  constants.
- Type hints on public functions. Match the repo's existing level of annotation rather
  than annotating everything in a partially typed codebase.
- Prefer `pathlib.Path` over `os.path` in new code unless the repo is consistently `os.path`.

## Structure

- `src/` layout vs flat package: detect and match.
- Keep `__init__.py` thin — re-exports, not logic.
- Dataclasses or Pydantic models for structured data; check which the repo uses. Do not
  introduce Pydantic into a stdlib-dataclass codebase for one model.

## Errors

- Custom exceptions inheriting from a single package-level base.
- Never bare `except:`. Catch the narrowest applicable type.
- `raise ... from err` when re-raising, to preserve the chain.

## Testing

- `pytest` conventions: `test_*.py`, plain `assert`, fixtures over `setUp`.
- Parametrize instead of copy-pasting near-identical cases.
- Put shared fixtures in `conftest.py` at the right scope level.
- Mock at the boundary you own, not deep inside a third-party library.
