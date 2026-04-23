"""Track fallback events across all agents so the daily email can surface them.

Each agent calls ``track(agent, from_key, to_key, reason)`` whenever a rotation
or backup path fires (primary key exhausted, service down, etc.).

Events are appended as one JSON line per rotation to ``/tmp/_fallbacks.jsonl``
— same runner shares /tmp across workflow steps, so ``send_email.py`` reads
the file later in the same job. Append with O_APPEND is atomic for short lines
on Linux, so we don't need a lock even when multiple agent processes run.
"""
import json
import os
import time

_LOG_PATH = os.environ.get("FALLBACK_LOG_PATH", "/tmp/_fallbacks.jsonl")


def track(agent: str, from_key: str, to_key: str, reason: str = "") -> None:
    """Record one fallback event. Safe to call from any thread/process."""
    event = {
        "ts": time.time(),
        "agent": agent,
        "from": from_key,
        "to": to_key,
        "reason": reason[:120],
    }
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass  # tracking must never break the caller


def read_events() -> list[dict]:
    """Read all fallback events from this run."""
    if not os.path.exists(_LOG_PATH):
        return []
    events = []
    try:
        with open(_LOG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    return events


def reset() -> None:
    """Clear the log. Call at the start of a pipeline run."""
    try:
        if os.path.exists(_LOG_PATH):
            os.remove(_LOG_PATH)
    except Exception:
        pass
