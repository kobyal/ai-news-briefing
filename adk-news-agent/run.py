#!/usr/bin/env python3
"""Run the AI Latest Briefing (Google ADK + Gemini) pipeline."""
from pathlib import Path

# Only pull in python-dotenv when a per-agent .env actually exists. In
# production (local-cycle.sh sources private/.env; CI uses repo secrets)
# env vars are already in os.environ, so dotenv is unused — and we don't
# want a missing python-dotenv install to crash the agent at import time.
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

from adk_news_agent import run_pipeline

if __name__ == "__main__":
    run_pipeline()
