[private]
default: _default

# PYTHONPATH covers all source directories (mirrors tox base environment)
export PYTHONPATH := justfile_directory() + ":" + justfile_directory() + "/src/:" + justfile_directory() + "/lib/"

# Avoid state written to file during tests
export UNIT_STATE_DB := ":memory:"

# Default to Juju 3; don't overwrite if already set in the environment
export TEST_JUJU3 := env("TEST_JUJU3", "1")

# List all available recipes
_default:
    @echo ""
    @just --list

# Run linting checks: ruff, codespell, mypy
lint:
    uv run --group lint ruff check .
    uv run --group lint ruff format --check --diff .
    uv run --group lint codespell .
    uv run --group lint mypy .

# Reformat source code in-place
reformat:
    uv run --group reformat ruff check --fix .
    uv run --group reformat ruff format .

# Run unit tests; extra args are forwarded to pytest
unit *ARGS:
    #!/bin/bash -xeu
    COVERAGE_FILE=.coverage-unit
    uv run --group unit pytest tests/unit \
        -v \
        --cov \
        --cov-report=term-missing \
        --cov-report=html \
        --cov-report=xml \
        {{ ARGS }}

# Run functional tests; extra args replace the default --keep-model
[working-directory("tests/functional")]
func *ARGS:
    #!/bin/bash -xeu
    COVERAGE_FILE=.coverage-func
    POSARGS="{{ ARGS }}"
    uv run --group func functest-run-suite ${POSARGS:---keep-model}
