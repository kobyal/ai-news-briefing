#!/usr/bin/env python3
"""Run the Tavily + AWS Bedrock News Agent."""
import os
import subprocess
import sys
from pathlib import Path

# Load .env — check local first, then sibling perplexity-news-agent
_here = Path(__file__).parent
for _candidate in [_here / ".env", _here.parent / "perplexity-news-agent" / ".env"]:
    if _candidate.exists():
        from dotenv import load_dotenv
        load_dotenv(_candidate)
        print(f"  Loaded .env from {_candidate}")
        break

from tavily_news_agent import run_pipeline

if __name__ == "__main__":
    result = run_pipeline()
    html_path = result.get("saved_to", "")
    if html_path and sys.platform == "darwin":
        subprocess.run(["open", html_path])
