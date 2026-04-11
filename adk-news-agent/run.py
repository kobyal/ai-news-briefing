#!/usr/bin/env python3
"""Run the AI Latest Briefing (Google ADK + Gemini) pipeline."""
import sys
from pathlib import Path

# Add repo root to path for shared module
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from adk_news_agent import run_pipeline

if __name__ == "__main__":
    run_pipeline()
