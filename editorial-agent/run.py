#!/usr/bin/env python3
"""Editorial agent — run with: python editorial-agent/run.py [--date YYYY-MM-DD]"""

import argparse
import sys
import traceback
from pathlib import Path

# Allow imports from repo root (shared/) and this agent's package
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from editorial_agent import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="AI Briefing editorial synthesis agent")
    parser.add_argument("--date", default=None, help="Date to synthesize (YYYY-MM-DD, default: today)")
    args = parser.parse_args()

    try:
        result = run_pipeline(date=args.date)
        print(f"\nDone → {result.get('canonical')}")
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
