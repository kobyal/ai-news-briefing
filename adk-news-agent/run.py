#!/usr/bin/env python3
"""Run the AI Latest Briefing (Google ADK + Gemini) pipeline."""
import os
import sys
from pathlib import Path

# Only pull in python-dotenv when a per-agent .env actually exists. In
# production (local-cycle.sh sources private/.env; CI uses repo secrets)
# env vars are already in os.environ, so dotenv is unused — and we don't
# want a missing python-dotenv install to crash the agent at import time.
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)


# Sentinel guards against an infinite retry loop when the backup key is
# also exhausted: the parent process sets _ADK_USING_BACKUP_KEY=1 before
# re-launching, the child sees it and skips the wrapper.
_RETRY_SENTINEL = "_ADK_USING_BACKUP_KEY"

# Substrings that indicate a Gemini quota / rate-limit failure (case-
# insensitive). google-genai raises google.api_core.exceptions.ResourceExhausted
# (HTTP 429) for daily-quota-hit; other forms surface as JSON {"error":...}
# strings inside RuntimeError. Matching by substring is crude but covers
# both paths without coupling to the SDK's exception hierarchy.
_QUOTA_MARKERS = (
    "resourceexhausted", "resource_exhausted", "resource exhausted",
    "rate_limit", "rate limit", "quota", "429",
    "exhausted", "rate-limit",
)


def _is_quota_error(exc: BaseException) -> bool:
    msg = (str(exc) or "").lower()
    return any(m in msg for m in _QUOTA_MARKERS)


def _run_with_fallback() -> None:
    """First attempt with GOOGLE_API_KEY; on Gemini quota error, re-launch
    this script as a fresh subprocess with GOOGLE_API_KEY = GOOGLE_API_KEY2
    so google-genai picks up a clean client. Re-running ADK from scratch is
    correct behaviour: a quota-exhausted primary takes the WHOLE chain down,
    so partial state isn't recoverable anyway."""
    from adk_news_agent import run_pipeline as _run_pipeline

    if os.environ.get(_RETRY_SENTINEL) == "1":
        # Already on backup key — don't loop, just run.
        _run_pipeline()
        return

    try:
        _run_pipeline()
    except Exception as exc:
        backup = (os.environ.get("GOOGLE_API_KEY2")
                  or os.environ.get("GOOGLE_API_KEY_2") or "").strip()
        if backup and _is_quota_error(exc):
            print(f"\n[ADK] Primary GOOGLE_API_KEY hit Gemini quota "
                  f"({type(exc).__name__}: {str(exc)[:100]}). "
                  f"Re-launching with GOOGLE_API_KEY2 in a fresh subprocess.",
                  file=sys.stderr)
            env = os.environ.copy()
            env["GOOGLE_API_KEY"] = backup
            env[_RETRY_SENTINEL] = "1"
            # Surface the rotation in the daily email's fallback panel.
            try:
                import sys as _sys
                _repo_root = Path(__file__).resolve().parent.parent
                if str(_repo_root) not in _sys.path:
                    _sys.path.insert(0, str(_repo_root))
                from shared.fallback_tracker import track
                track("adk-news-agent", "GOOGLE_API_KEY",
                      "GOOGLE_API_KEY2", f"primary quota: {type(exc).__name__}")
            except Exception:
                pass
            import subprocess
            r = subprocess.run([sys.executable, str(Path(__file__).resolve())], env=env)
            sys.exit(r.returncode)
        raise


if __name__ == "__main__":
    _run_with_fallback()
