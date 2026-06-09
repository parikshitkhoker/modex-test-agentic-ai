"""MoDeX remote MCP client — Face 1 with zero local credentials.

This is the install-anywhere half of MoDeX. It is a normal stdio MCP server that
Cursor / Antigravity / Windsurf launch like any other, but instead of touching
BigQuery it forwards every tool call to the hosted MoDeX API on Cloud Run. The
server holds the GCP credentials; this client only needs two env vars:

    MODEX_API_URL   e.g. https://agentic-data-platform-xxxxx.run.app
    MODEX_API_KEY   your personal key (the server maps it to your developer_id)

Optional:
    MODEX_AGENT_TOOL    label for the IDE (default: "cursor")
    MODEX_DEVELOPER_ID  hint only; the server stamps the real id from the key

Dependencies: only the `mcp` package + the Python standard library. A teammate
can copy just this single file, run `pip install mcp`, point their IDE at it,
and they are part of the shared memory — no repo, no service-account key.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

API_URL = os.getenv("MODEX_API_URL", "").rstrip("/")
API_KEY = os.getenv("MODEX_API_KEY", "")
AGENT_TOOL = os.getenv("MODEX_AGENT_TOOL", "cursor")

server = Server("modex-memory")


def _text(payload: dict[str, Any]) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]


def _request(method: str, path: str, *, params: dict | None = None,
             body: dict | None = None) -> dict[str, Any]:
    if not API_URL:
        return {"status": "error", "message": "MODEX_API_URL env var is not set."}
    if not API_KEY:
        return {"status": "error", "message": "MODEX_API_KEY env var is not set."}

    url = f"{API_URL}{path}"
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean, doseq=True)

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:500]
        return {"status": "error", "http_status": exc.code, "message": detail}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": f"{type(exc).__name__}: {exc}"}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="load_context",
            description=(
                "PRIMARY: Hydrate a NEW coding-agent session with the team's shared "
                "decision memory from the hosted MoDeX bus. Returns a curated, "
                "provenance-stamped CONTEXT PACK (adopted decisions, REJECTED "
                "approaches, open questions, gotchas). Call at session start."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_repo": {"type": "string"},
                    "limit": {"type": "integer", "default": 40},
                    "include_rag": {"type": "boolean", "default": False},
                },
                "required": ["project_repo"],
            },
        ),
        Tool(
            name="append_codebase_log",
            description=(
                "PRIMARY: Append one immutable event to shared MoDeX memory "
                "(session_start, user_prompt, tool_call, file_edit, decision, "
                "error, session_end). Your developer_id is set automatically."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_repo": {"type": "string"},
                    "event_type": {
                        "type": "string",
                        "enum": [
                            "session_start",
                            "user_prompt",
                            "tool_call",
                            "file_edit",
                            "decision",
                            "error",
                            "session_end",
                            "context_compressed",
                        ],
                    },
                    "summary": {"type": "string"},
                    "session_id": {"type": "string"},
                    "file_path": {"type": "string"},
                    "commit_sha": {"type": "string"},
                    "payload": {"type": "object"},
                    "parent_event_id": {"type": "string"},
                    "agent_tool": {"type": "string"},
                },
                "required": ["project_repo", "event_type", "summary"],
            },
        ),
        Tool(
            name="log_decision",
            description="Log one engineering decision into shared MoDeX memory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_repo": {"type": "string"},
                    "decision": {"type": "string"},
                    "context": {"type": "string"},
                    "session_id": {"type": "string"},
                    "file_path": {"type": "string"},
                    "agent_tool": {"type": "string"},
                },
                "required": ["project_repo", "decision"],
            },
        ),
        Tool(
            name="save_session_memory",
            description="End-of-session wrapper — writes session_end + decisions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_repo": {"type": "string"},
                    "summary": {"type": "string"},
                    "decisions": {"type": "array", "items": {"type": "string"}},
                    "files_touched": {"type": "array", "items": {"type": "string"}},
                    "rejected_approaches": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "session_id": {"type": "string"},
                    "agent_tool": {"type": "string"},
                },
                "required": ["project_repo", "summary"],
            },
        ),
        Tool(
            name="load_context_from_logs",
            description="Replay recent raw codebase log events for a repo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_repo": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                    "session_id": {"type": "string"},
                },
                "required": ["project_repo"],
            },
        ),
        Tool(
            name="compress_context",
            description=(
                "Compress raw logs into structured JSON (modex.context.v1) and save. "
                "Deterministic dedupe — not LLM summarization. Syncs via Fivetran."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_repo": {"type": "string"},
                    "session_id": {"type": "string"},
                    "event_limit": {"type": "integer", "default": 300},
                    "agent_tool": {"type": "string"},
                },
                "required": ["project_repo"],
            },
        ),
        Tool(
            name="load_session_history",
            description="Recent log events for the developer behind this API key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_repo": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        ),
        Tool(
            name="get_memory_catalog",
            description="List repos with shared MoDeX memory activity.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    args = arguments or {}
    tool = args.get("agent_tool") or AGENT_TOOL

    if name == "load_context":
        result = _request(
            "GET",
            "/api/v1/memory/context",
            params={
                "project_repo": args.get("project_repo"),
                "limit": args.get("limit", 40),
                "include_rag": str(bool(args.get("include_rag", False))).lower(),
            },
        )
    elif name == "append_codebase_log":
        result = _request(
            "POST",
            "/api/v1/memory/append",
            body={
                "agent_tool": tool,
                "project_repo": args.get("project_repo"),
                "event_type": args.get("event_type"),
                "summary": args.get("summary"),
                "session_id": args.get("session_id"),
                "file_path": args.get("file_path"),
                "commit_sha": args.get("commit_sha"),
                "payload": args.get("payload"),
                "parent_event_id": args.get("parent_event_id"),
            },
        )
    elif name == "log_decision":
        result = _request(
            "POST",
            "/api/v1/memory/decision",
            body={
                "agent_tool": tool,
                "project_repo": args.get("project_repo"),
                "decision": args.get("decision"),
                "context": args.get("context", ""),
                "session_id": args.get("session_id"),
                "file_path": args.get("file_path"),
            },
        )
    elif name == "save_session_memory":
        result = _request(
            "POST",
            "/api/v1/memory/session_end",
            body={
                "agent_tool": tool,
                "project_repo": args.get("project_repo"),
                "summary": args.get("summary"),
                "decisions": args.get("decisions"),
                "files_touched": args.get("files_touched"),
                "rejected_approaches": args.get("rejected_approaches"),
                "session_id": args.get("session_id"),
            },
        )
    elif name == "compress_context":
        result = _request(
            "POST",
            "/api/v1/memory/compress",
            body={
                "agent_tool": tool,
                "project_repo": args.get("project_repo"),
                "session_id": args.get("session_id"),
                "event_limit": args.get("event_limit", 300),
            },
        )
    elif name == "load_context_from_logs":
        result = _request(
            "GET",
            "/api/v1/memory/timeline",
            params={
                "project_repo": args.get("project_repo"),
                "limit": args.get("limit", 50),
                "session_id": args.get("session_id"),
            },
        )
    elif name == "load_session_history":
        result = _request(
            "GET",
            "/api/v1/memory/history",
            params={
                "project_repo": args.get("project_repo"),
                "limit": args.get("limit", 50),
            },
        )
    elif name == "get_memory_catalog":
        result = _request("GET", "/api/v1/memory/catalog")
    else:
        result = {"status": "error", "message": f"Unknown tool: {name}"}
    return _text(result)


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def cli() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    cli()
