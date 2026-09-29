#!/usr/bin/env python3
"""Run the events agent. See events_agent/pipeline.py for the flags."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from events_agent.pipeline import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
