"""One-line-per-run JSONL run-log helper, shared by the 3 side-data scripts
(fetch_hot_tools.py, fetch_podcasts.py, build_search_index.py).

Each run appends a single JSON record; send_email.py's monitoring panel
tail-reads the last line of the file. Centralized here so all callers
share the same `date`/`fetched_at` defaults + same exception swallowing.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def append_run_log(log_path: Path, record: dict) -> None:
    """Append `record` to `log_path` as one JSON line. `date` and `fetched_at`
    are filled in if missing. Best-effort: prints + swallows any error so a
    log-write failure never crashes the caller."""
    try:
        now = datetime.now(timezone.utc)
        record = {
            "date":       record.get("date") or now.date().isoformat(),
            "fetched_at": record.get("fetched_at") or now.isoformat(timespec="seconds"),
            **record,
        }
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        print(f"   ✓ logged to {log_path.name}")
    except Exception as e:
        print(f"   ⚠ run-log write failed for {log_path.name}: {e}")
