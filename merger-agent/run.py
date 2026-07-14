#!/usr/bin/env python3
"""Run the Merger Agent pipeline."""
import os
import subprocess
import sys
from pathlib import Path

# Bootstrap repo root so shared/ imports resolve at any depth.
sys.path.insert(0, str(next((_p for _p in Path(__file__).resolve().parents if (_p / "shared" / "__init__.py").exists()), Path(__file__).resolve().parents[1])))
from shared.repo_root import repo_root, find_dir  # noqa: E402

# Load .env from this directory (or repo root)
def _load_env():
    for candidate in [Path(__file__).parent / ".env", repo_root() / ".env"]:
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

# Also check perplexity-news-agent/.env for the API key (wherever it lives)
_px_dir = find_dir("perplexity-news-agent")
_px_env = (_px_dir / ".env") if _px_dir else Path(__file__).with_name(".env.__absent__")
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
        if path and sys.platform == "darwin" and os.environ.get("AI_NEWS_NO_OPEN") != "1":
            subprocess.run(["open", path], check=False)
    except Exception as e:
        import traceback
        print(f"\nERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
