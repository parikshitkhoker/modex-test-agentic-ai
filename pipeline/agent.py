"""Minimal Google ADK agent stub for the MoDeX BigQuery memory demo.

Demonstrates the pipeline shape: Gemini via ADK → MoDeX MCP tools → BigQuery bus.
"""

from __future__ import annotations

import os

PROJECT_REPO = os.getenv(
    "MODEX_PROJECT_REPO",
    "github.com/parikshitkhoker/modex-test-agentic-ai",
)

# ADK agent wiring goes here. This stub documents the intended flow:
#   1. load_context(project_repo) at session start
#   2. run Gemini tool loop for the user task
#   3. log_decision(...) after each major engineering choice
#   4. compress_context(project_repo) at session end


def main() -> None:
    print(f"MoDeX ADK pipeline demo — repo: {PROJECT_REPO}")
    print("Wire google-adk Agent here; memory tools via modex_mcp/remote_client.py")


if __name__ == "__main__":
    main()
