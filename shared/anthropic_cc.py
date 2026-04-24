"""Shared subscription path for Anthropic calls via Claude Code CLI.

Used when MERGER_VIA_CLAUDE_CODE=1 is set. Shells out to `claude -p` with
OAuth keychain credentials (Claude Max subscription) — never reads
ANTHROPIC_API_KEY, never bills pay-per-token.

Mirrors the API path's max_tokens=32000 semantics by extracting ONLY the
first assistant message's text, ignoring any auto-continuation. Downstream
JSON-repair handles truncation the same way the API path does.
"""
import json
import os
import subprocess
import time


def is_enabled() -> bool:
    return os.environ.get("MERGER_VIA_CLAUDE_CODE") == "1"


def _cc_model() -> str:
    return os.environ.get("MERGER_CC_MODEL", "claude-opus-4-7")


def _cc_effort() -> str:
    return os.environ.get("MERGER_CC_EFFORT", "low")


def agent(
    input_text: str,
    *,
    instructions: str | None = None,
    json_mode: bool = False,
    label: str = "",
    usage_log: list | None = None,
) -> str:
    """One-shot Claude call via `claude -p` (subscription).

    Appends a usage entry to `usage_log` if provided (same structure as the
    API-path entries: step, model, input_tokens, output_tokens, cost_usd).
    """
    system_prompt = instructions or "You are a helpful assistant. Return only the requested output."
    if json_mode:
        system_prompt = system_prompt + (
            "\nRespond with ONLY a valid JSON object. No markdown fences, no explanation."
        )

    cmd = [
        "claude", "-p",
        "--model", _cc_model(),
        "--output-format", "stream-json",
        "--verbose",
        "--system-prompt", system_prompt,
        "--tools", "",
        "--no-session-persistence",
        "--disable-slash-commands",
        "--effort", _cc_effort(),
    ]

    t0 = time.time()
    try:
        r = subprocess.run(cmd, input=input_text, capture_output=True,
                           text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"[{label}] claude -p timed out after 1800s")
    if r.returncode != 0:
        raise RuntimeError(f"[{label}] claude -p failed (rc={r.returncode}): {r.stderr[:500]}")

    assistant_texts: list[str] = []
    result_event: dict | None = None
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "assistant":
            msg = obj.get("message", {}) or {}
            blocks = [b.get("text", "") for b in (msg.get("content") or []) if b.get("type") == "text"]
            if blocks:
                assistant_texts.append("".join(blocks))
        elif obj.get("type") == "result":
            result_event = obj

    text = assistant_texts[0] if assistant_texts else ""
    elapsed = time.time() - t0
    usage = (result_event or {}).get("usage", {}) or {}
    in_tok = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0)
    stop = (result_event or {}).get("stop_reason", "unknown")
    n_msgs = len(assistant_texts)
    print(f"    ✓  {label:<22} {elapsed:5.1f}s   model={_cc_model()} (sub)  in={in_tok} out={out_tok}  stop={stop}  msgs={n_msgs}")
    if n_msgs > 1:
        print(f"    ⚠  [{label}] Claude Code auto-continued — using first turn only")

    if usage_log is not None:
        usage_log.append({
            "step": label,
            "model": _cc_model(),
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": 0.0,
            "via": "subscription",
        })

    if json_mode and text:
        stripped = text.strip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            print(f"    ⚠  [{label}] Expected JSON but got: {repr(stripped[:80])}")

    return text
