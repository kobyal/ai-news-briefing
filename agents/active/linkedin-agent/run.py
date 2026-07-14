#!/usr/bin/env python3
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(next((_p for _p in Path(__file__).resolve().parents if (_p / "shared" / "__init__.py").exists()), Path(__file__).resolve().parents[1])))
from shared.repo_root import repo_root  # noqa: E402

# Load private/.env so KOBYTEST_LI_AT etc. are available when running directly
_env_path = repo_root() / "private" / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            if _k.strip() and _k.strip() not in os.environ:
                os.environ[_k.strip()] = _v.strip()

from linkedin_agent.pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline()
