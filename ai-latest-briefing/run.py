#!/usr/bin/env python3
"""Run the AI Latest Briefing (Google ADK + Gemini) pipeline."""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from ai_latest_briefing import run_pipeline

if __name__ == "__main__":
    run_pipeline()
