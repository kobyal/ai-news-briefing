#!/usr/bin/env python3
"""Run the Merger Agent pipeline."""
import os
import subprocess
import sys
from pathlib import Path

# Load .env from this directory (or repo root)
def _load_env():
    for candidate in [Path(__file__).parent / ".env", Path(__file__).parent.parent / ".env"]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
            print(f"Loaded .env from {candidate}")
            return
    print("No .env found — using existing environment variables")

_load_env()

# Also check perplexity-news-agent/.env for the API key
_px_env = Path(__file__).parent.parent / "perplexity-news-agent" / ".env"
if _px_env.exists() and not os.environ.get("PERPLEXITY_API_KEY"):
    for line in _px_env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())
    print(f"Loaded API key from {_px_env}")

sys.path.insert(0, str(Path(__file__).parent))

from merger_agent import run_pipeline

if __name__ == "__main__":
    try:
        result = run_pipeline()
        path = result.get("saved_to", "")
        if path and sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
