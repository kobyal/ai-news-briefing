#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from linkedin_agent.pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline()
