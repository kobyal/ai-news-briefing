#!/usr/bin/env python3
"""Run the Social News Agent (Grok live X search + Reddit)."""
import os
import subprocess
import sys
from pathlib import Path

_here = Path(__file__).parent
for _candidate in [_here / ".env", _here.parent / "perplexity-news-agent" / ".env"]:
    if _candidate.exists():
        from dotenv import load_dotenv
        load_dotenv(_candidate)
        print(f"  Loaded .env from {_candidate}")
        break

from social_news_agent import run_pipeline

if __name__ == "__main__":
    result = run_pipeline()
    path = result.get("saved_to", "")
    if path and sys.platform == "darwin":
        subprocess.run(["open", path])
