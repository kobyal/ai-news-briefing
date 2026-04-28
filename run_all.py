#!/usr/bin/env python3
"""Run all agents: source agents in parallel, then Merger.

Usage:
    python run_all.py                 # all agents + Merger
    python run_all.py --merge-only    # only Merger (reuses latest outputs)
    python run_all.py --skip xai rss  # skip specific agents
    python run_all.py --only adk tavily merger  # run ONLY these agents
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# ── Agent registry: name → (script path relative to root, cost tier) ──────
AGENTS = {
    # Core source agents
    "adk":        ("adk-news-agent/run.py",          "paid",  "Google Gemini API"),
    "perplexity": ("perplexity-news-agent/run.py",   "paid",  "Perplexity API"),
    "rss":        ("rss-news-agent/run.py",           "paid",  "Anthropic (haiku)"),
    "tavily":     ("tavily-news-agent/run.py",        "paid",  "Tavily + Anthropic (haiku)"),
    # Supplemental agents
    "article":    ("article-reader-agent/run.py",     "cheap", "Jina (free tier)"),
    "exa":        ("exa-news-agent/run.py",           "cheap", "Exa (free tier)"),
    "newsapi":    ("newsapi-agent/run.py",            "free",  "NewsAPI (free tier)"),
    "youtube":    ("youtube-news-agent/run.py",       "free",  "YouTube Data API (free quota)"),
    "github":     ("github-trending-agent/run.py",    "free",  "GitHub API (free)"),
    "xai":        ("xai-twitter-agent/run.py",        "paid",  "xAI Grok-4 (~$0.35/run) — disabled"),
    "twitter":    ("twitter-agent/run.py",             "free",  "X GraphQL direct (no API key)"),
    # Merger (always runs last)
    "merger":     ("merger-agent/run.py",             "paid",  "Anthropic Claude"),
}

AGENT_DISPLAY = {
    "adk": "ADK News Agent", "perplexity": "Perplexity News Agent",
    "rss": "RSS News Agent", "tavily": "Tavily News Agent",
    "article": "Article Reader Agent",
    "exa": "Exa News Agent", "newsapi": "NewsAPI Agent",
    "youtube": "YouTube News Agent", "github": "GitHub Trending Agent",
    "xai": "xAI Twitter Agent", "twitter": "Twitter Agent", "merger": "Merger Agent",
}


def _run(script: Path, label: str) -> bool:
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
    if not agents:
        return {}

    print(f"\n{'='*60}")
    print(f"  Launching {len(agents)} agents in parallel...")
    print("=" * 60)

    procs = []
    for script, label in agents:
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=script.parent,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        procs.append((label, proc))
        print(f"  ▶  {label}  (pid {proc.pid})")

    print()
    t0 = time.time()
    TIMEOUT = int(os.environ.get("AGENT_TIMEOUT", "1200"))

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
    parser.add_argument("--merge-only", action="store_true", help="Only run the Merger")
    parser.add_argument("--skip", nargs="*", default=[], metavar="AGENT",
                        help=f"Skip these agents. Choices: {', '.join(AGENTS.keys())}")
    parser.add_argument("--only", nargs="*", default=[], metavar="AGENT",
                        help="Run ONLY these agents (+ merger). Choices: same as --skip")
    parser.add_argument("--free-only", action="store_true",
                        help="Run only free/cheap agents (skip all paid APIs)")
    parser.add_argument("--list", action="store_true", help="List all agents and their cost tiers")
    args = parser.parse_args()

    root = Path(__file__).parent

    if args.list:
        print(f"\n{'Agent':<14} {'Tier':<6} {'API Cost'}")
        print("-" * 50)
        for name, (_, tier, api) in AGENTS.items():
            icon = {"free": "🟢", "cheap": "🟡", "paid": "🔴"}[tier]
            print(f"  {icon} {name:<12} {tier:<6} {api}")
        return

    if args.merge_only:
        _run(root / "merger-agent" / "run.py", "Merger Agent")
        return

    skip = set(args.skip)

    # Determine which agents to run
    if args.only:
        enabled = set(args.only)
        enabled.discard("merger")  # merger runs separately
    elif args.free_only:
        enabled = {name for name, (_, tier, _) in AGENTS.items() if tier in ("free", "cheap")}
        enabled.add("merger")  # merger always runs
    else:
        enabled = set(AGENTS.keys())

    enabled -= skip
    enabled.discard("merger")  # merger runs after all others

    # Build parallel list (everything except merger)
    agents = []
    for name in AGENTS:
        if name == "merger":
            continue
        if name in enabled:
            script = root / AGENTS[name][0]
            agents.append((script, AGENT_DISPLAY[name]))

    if agents:
        skipped = set(AGENTS.keys()) - enabled - {"merger"}
        if skipped:
            print(f"\n  Skipping: {', '.join(sorted(skipped))}")

        results = _run_parallel(agents)
        failed = [label for label, ok in results.items() if not ok]
        if failed:
            print(f"\n[WARNING] Failed: {', '.join(failed)} — continuing with available outputs")

    # Merger always runs (unless explicitly skipped)
    if "merger" not in skip:
        _run(root / "merger-agent" / "run.py", "Merger Agent")


if __name__ == "__main__":
    main()
