#!/usr/bin/env python3
"""Run all agents: source agents in parallel, then Merger.

The 5 source agents are fully independent and run simultaneously.
Total wall-clock time ≈ slowest single agent (~4 min) instead of sum (~12 min).

Usage:
    python run_all.py                 # all 5 agents in parallel + Merger
    python run_all.py --skip-adk      # skip ADK
    python run_all.py --skip-px       # skip Perplexity
    python run_all.py --skip-rss      # skip RSS
    python run_all.py --skip-tavily   # skip Tavily
    python run_all.py --skip-social   # skip Social
    python run_all.py --merge-only    # only run Merger on latest existing outputs
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def _run(script: Path, label: str) -> bool:
    """Run a single script, streaming output live (used for the Merger)."""
    print(f"\n{'='*60}")
    print(f"  Running: {label}")
    print(f"  Script:  {script}")
    print("=" * 60)
    result = subprocess.run(
        [sys.executable, str(script)], cwd=script.parent,
        stderr=subprocess.PIPE, text=True,
    )
    if result.returncode != 0:
        print(f"\n[ERROR] {label} failed (exit {result.returncode})")
        if result.stderr:
            print(f"STDERR:\n{result.stderr[-2000:]}")
        return False
    return True


def _run_parallel(agents: list[tuple[Path, str]]) -> dict[str, bool]:
    """Launch agents simultaneously, capture each output, print when done."""
    if not agents:
        return {}

    print(f"\n{'='*60}")
    print(f"  Launching {len(agents)} source agents in parallel...")
    print("=" * 60)

    # Start all agents at once
    procs = []
    for script, label in agents:
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=script.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        procs.append((label, proc))
        print(f"  ▶  {label}  (pid {proc.pid})")

    print()
    t0 = time.time()
    TIMEOUT = int(os.environ.get("AGENT_TIMEOUT", "480"))  # 8 min default

    # Wait for each in order, print captured output as they finish
    results = {}
    for label, proc in procs:
        try:
            stdout, _ = proc.communicate(timeout=TIMEOUT)
            ok = proc.returncode == 0
            status = "✓" if ok else "✗ FAILED"
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, _ = proc.communicate()
            ok = False
            status = f"✗ TIMEOUT (>{TIMEOUT}s)"
        elapsed = time.time() - t0
        results[label] = ok
        print(f"\n{'='*60}")
        print(f"  {status}  {label}  (+{elapsed:.0f}s wall clock)")
        print("=" * 60)
        print(stdout, end="")

    return results


def main():
    parser = argparse.ArgumentParser(description="Run AI news agent pipelines")
    parser.add_argument("--skip-adk",    action="store_true", help="Skip the ADK pipeline")
    parser.add_argument("--skip-px",     action="store_true", help="Skip the Perplexity pipeline")
    parser.add_argument("--skip-rss",    action="store_true", help="Skip the RSS pipeline")
    parser.add_argument("--skip-tavily", action="store_true", help="Skip the Tavily pipeline")
    parser.add_argument("--skip-social", action="store_true", help="Skip the Social pipeline")
    parser.add_argument("--merge-only",  action="store_true", help="Only run the Merger")
    args = parser.parse_args()

    root = Path(__file__).parent

    if args.merge_only:
        _run(root / "merger-agent" / "run.py", "Merger Agent")
        return

    # Build list of independent agents to run in parallel
    agents = []
    if not args.skip_adk:
        agents.append((root / "adk-news-agent"          / "run.py", "ADK News Agent"))
    if not args.skip_px:
        agents.append((root / "perplexity-news-agent"   / "run.py", "Perplexity News Agent"))
    if not args.skip_rss:
        agents.append((root / "rss-news-agent"          / "run.py", "RSS News Agent"))
    if not args.skip_tavily:
        agents.append((root / "tavily-news-agent"       / "run.py", "Tavily News Agent"))
    if not args.skip_social:
        agents.append((root / "social-news-agent"       / "run.py", "Social News Agent"))
    agents.append((root / "article-reader-agent"        / "run.py", "Article Reader Agent"))
    agents.append((root / "exa-news-agent"              / "run.py", "Exa News Agent"))
    agents.append((root / "newsapi-agent"               / "run.py", "NewsAPI Agent"))
    agents.append((root / "youtube-news-agent"          / "run.py", "YouTube News Agent"))
    agents.append((root / "github-trending-agent"       / "run.py", "GitHub Trending Agent"))
    agents.append((root / "xai-twitter-agent"           / "run.py", "xAI Twitter Agent"))

    results = _run_parallel(agents)

    failed = [label for label, ok in results.items() if not ok]
    if failed:
        print(f"\n[WARNING] Failed: {', '.join(failed)} — continuing with available outputs")

    _run(root / "merger-agent" / "run.py", "Merger Agent")


if __name__ == "__main__":
    main()
