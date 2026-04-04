#!/usr/bin/env python3
"""Run all agents in sequence: ADK → Perplexity → RSS → Tavily → Merger.

Usage:
    python run_all.py                # run all (ADK + Perplexity + RSS + Tavily + Merger)
    python run_all.py --skip-adk     # skip ADK (use existing output)
    python run_all.py --skip-px      # skip Perplexity
    python run_all.py --skip-rss     # skip RSS
    python run_all.py --skip-tavily  # skip Tavily
    python run_all.py --merge-only   # only run the merger on latest existing outputs
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def _run(script: Path, label: str) -> bool:
    print(f"\n{'='*60}")
    print(f"  Running: {label}")
    print(f"  Script:  {script}")
    print("=" * 60)
    result = subprocess.run([sys.executable, str(script)], cwd=script.parent)
    if result.returncode != 0:
        print(f"\n[ERROR] {label} failed (exit {result.returncode})")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Run AI news agent pipelines")
    parser.add_argument("--skip-adk",    action="store_true", help="Skip the ADK pipeline")
    parser.add_argument("--skip-px",     action="store_true", help="Skip the Perplexity pipeline")
    parser.add_argument("--skip-rss",    action="store_true", help="Skip the RSS pipeline")
    parser.add_argument("--skip-tavily", action="store_true", help="Skip the Tavily pipeline")
    parser.add_argument("--merge-only",  action="store_true", help="Only run the merger")
    args = parser.parse_args()

    root = Path(__file__).parent

    if args.merge_only:
        _run(root / "merger-agent" / "run.py", "Merger Agent")
        return

    if not args.skip_adk:
        ok = _run(root / "adk-news-agent" / "run.py", "AI Latest Briefing (Google ADK)")
        if not ok:
            print("ADK pipeline failed. Continuing with other sources...")

    if not args.skip_px:
        ok = _run(root / "perplexity-news-agent" / "run.py", "Perplexity News Agent")
        if not ok:
            print("Perplexity pipeline failed. Continuing with existing data...")

    if not args.skip_rss:
        _run(root / "rss-news-agent" / "run.py", "RSS News Agent")

    if not args.skip_tavily:
        _run(root / "tavily-news-agent" / "run.py", "Tavily News Agent")

    _run(root / "merger-agent" / "run.py", "Merger Agent")


if __name__ == "__main__":
    main()
