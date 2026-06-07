"""JSON parser for the RSS News Agent.

Handles edge cases the LLM tends to produce: markdown fences, Hebrew gershayim
colliding with JSON quote chars, Python repr-style dicts.

(Per-agent HTML rendering used to live here too. It was deleted on 2026-05-03 —
nothing read it. The merger writes the only user-facing HTML.)
"""
import ast
import json
import re
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
from shared.json_repair import parse_json  # noqa: E402


def _parse(value):
    return parse_json(value)
