#!/usr/bin/env python3
"""Run the Article Reader Agent."""
import sys
from pathlib import Path

# Add repo root for shared module
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from article_reader_agent.pipeline import run_pipeline

if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
