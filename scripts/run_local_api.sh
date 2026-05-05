#!/usr/bin/env sh
set -eu

uv sync --all-groups
uv run uvicorn app.main:create_app --factory --reload
