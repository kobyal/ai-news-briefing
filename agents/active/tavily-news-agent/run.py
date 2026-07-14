#!/usr/bin/env python3
"""Run the Tavily + Perplexity News Agent."""
import os
import subprocess
import sys
from pathlib import Path

# Bootstrap repo root so shared/ imports resolve at any depth.
sys.path.insert(0, str(next((_p for _p in Path(__file__).resolve().parents if (_p / "shared" / "__init__.py").exists()), Path(__file__).resolve().parents[1])))
from shared.repo_root import find_dir  # noqa: E402

# Load .env — check local first, then sibling perplexity-news-agent (wherever it lives)
_here = Path(__file__).parent
_px = find_dir("perplexity-news-agent")
for _candidate in [_here / ".env"] + ([_px / ".env"] if _px else []):
    if _candidate.exists():
        from dotenv import load_dotenv
        load_dotenv(_candidate)
        print(f"  Loaded .env from {_candidate}")
        break

from tavily_news_agent import run_pipeline

if __name__ == "__main__":
    result = run_pipeline()
    html_path = result.get("saved_to", "")
    if html_path and sys.platform == "darwin" and os.environ.get("AI_NEWS_NO_OPEN") != "1":
        subprocess.run(["open", html_path])
