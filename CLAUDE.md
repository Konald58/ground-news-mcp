# CLAUDE.md — Project Override

<!-- Replace this file with project-specific rules. Inherits global ~/.../CLAUDE.md -->

## Project
<!-- Describe what this project does and why it exists -->

## Stack
- Python 3.12+
- ruff (format + lint)
- pytest

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run
```bash
python -m project_name.main
```

## Test
```bash
pytest
```

## Lint
```bash
ruff check . && ruff format .
```
