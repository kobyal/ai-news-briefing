#!/usr/bin/env python3
"""Run the GitHub Trending Agent."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from github_trending_agent.pipeline import run_pipeline

if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
