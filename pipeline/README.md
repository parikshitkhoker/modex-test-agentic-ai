# MoDeX ADK → BigQuery Pipeline Demo

Small agent pipeline showing how a **Google ADK** agent writes shared memory to **BigQuery** (the MoDeX memory bus).

## Architecture

```
User prompt
    │
    ▼
Google ADK agent (Gemini)
    │
    ├── tools: log_decision, load_context (via MoDeX MCP)
    │
    ▼
MoDeX API → BigQuery (immutable event log)
    │
    ▼
Fivetran sync (~5 min) → sheet mirror → next session load_context
```

## Why these choices

| Choice | Decision |
|--------|----------|
| Agent framework | **Google ADK** — team is on Gemini; native GCP integration |
| Memory bus | **BigQuery** — append-only event log, queryable, Fivetran-ready |
| Sync SLA | **~5 minutes** via Fivetran to shared context pack |

## Flow

1. **Session start** — `load_context` hydrates prior decisions from BigQuery-backed memory.
2. **Agent run** — ADK agent processes the task using Gemini.
3. **Major choices** — `log_decision` appends adopted/rejected decisions to the bus.
4. **Session end** — `compress_context` dedupes raw logs into `modex.context.v1` JSON.
5. **Cross-session** — Fivetran syncs BigQuery rows; teammates get the same context on next `load_context`.

## Layout

```
pipeline/
  README.md          ← this file
  agent.py           ← minimal ADK agent stub
  requirements.txt   ← google-adk + mcp client deps
```

## Run locally (stub)

```bash
cd pipeline
pip install -r requirements.txt
python agent.py
```

Set `MODEX_API_URL` and `MODEX_API_KEY` to point at the hosted MoDeX bus (see repo root `modex_mcp/remote_client.py`).
