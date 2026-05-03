"""JSON parser for the RSS News Agent.

Handles edge cases the LLM tends to produce: markdown fences, Hebrew gershayim
colliding with JSON quote chars, Python repr-style dicts.

(Per-agent HTML rendering used to live here too. It was deleted on 2026-05-03 —
nothing read it. The merger writes the only user-facing HTML.)
"""
import ast
import json
import re


def _parse(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        value = re.sub(r"^```(?:json)?\s*", "", value.strip())
        value = re.sub(r"\s*```$", "", value.strip())
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
        try:
            return ast.literal_eval(value)
        except Exception:
            pass
        try:
            fixed = re.sub(r'([\u0590-\u05FF])"([\u0590-\u05FF])', r'\1\u05f4\2', value)
            return json.loads(fixed)
        except Exception:
            pass
        try:
            fixed = re.sub(r'(?<=: ")(.+?)(?="(?:\s*[,}]))', lambda m: m.group(0).replace('"', '\\"'), value)
            return json.loads(fixed)
        except Exception:
            pass
    return {}
