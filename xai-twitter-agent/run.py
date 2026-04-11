#!/usr/bin/env python3
"""Run the xAI Twitter Agent."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from xai_twitter_agent.pipeline import run_pipeline

if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
