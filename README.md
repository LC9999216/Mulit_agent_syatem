# Stock Research Multi-Agent

Minimal but auditable multi-agent stock research system built with FastAPI and LangGraph.

## MVP

- `POST /analyze/company`
- `GET /analysis/{request_id}`
- `GET /report/{request_id}`
- `/health`
- `/ready`

The default runtime uses deterministic demo data so the project can be exercised without external API keys. Real SEC and market data adapters are exposed through the runtime service container.

## Local Run

```powershell
uv venv .venv
uv sync --all-groups
.\.venv\Scripts\uvicorn.exe app.main:create_app --factory --reload
```

## Tests

```powershell
.\.venv\Scripts\pytest.exe
```
