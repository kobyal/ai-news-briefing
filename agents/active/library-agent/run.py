#!/usr/bin/env python3
"""Run the Library Agent — one reviewed long-form talk per day into /library."""
import sys
from pathlib import Path

# Bootstrap repo root so shared/ imports resolve at any depth.
sys.path.insert(0, str(next((_p for _p in Path(__file__).resolve().parents if (_p / "shared" / "__init__.py").exists()), Path(__file__).resolve().parents[1])))
sys.path.insert(0, str(Path(__file__).parent))

from library_agent import main

if __name__ == "__main__":
    sys.exit(main())
