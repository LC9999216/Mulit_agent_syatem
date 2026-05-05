#!/usr/bin/env sh
set -eu

uv sync --all-groups
uv run python -m app.workers.worker_main
