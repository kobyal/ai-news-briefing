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
    # Respect explicit override, then the model the active Claude Code session
    # is configured for (ANTHROPIC_MODEL is set to a Bedrock-prefixed id like
    # "eu.anthropic.claude-opus-4-7" under CLAUDE_CODE_USE_BEDROCK=1, and to a
    # plain id like "claude-opus-4-7" under Claude Max subscription). Fall back
    # to the subscription-style id.
    return (
        os.environ.get("MERGER_CC_MODEL")
        or os.environ.get("ANTHROPIC_MODEL")
        or "claude-opus-4-7"
    )


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

    # Strip session-specific Claude Code env vars before spawning so the child
    # `claude -p` uses OAuth/subscription auth instead of being confused by
    # the parent session's context (which causes "credit balance too low").
    # Strip ALL CLAUDE_CODE_* prefixed vars (not just a fixed list) — new vars
    # added in future CC releases would otherwise cause silent auth failures.
    # CLAUDE_CODE_USE_BEDROCK / CLAUDE_CODE_USE_VERTEX are intentionally kept
    # so Bedrock/Vertex deployments still work in the child process.
    _STRIP_PREFIX = "CLAUDE_CODE_"
    _KEEP = {"CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"}
    _STRIP_EXACT = {"CLAUDECODE", "ANTHROPIC_API_KEY"}
    child_env = {
        k: v for k, v in os.environ.items()
        if k not in _STRIP_EXACT
        and (k not in _KEEP and not k.startswith(_STRIP_PREFIX) or k in _KEEP)
    }

    t0 = time.time()
    last_err: Exception | None = None
    for attempt in range(2):  # 1 retry on transient rc=1 with empty output
        try:
            r = subprocess.run(cmd, input=input_text, capture_output=True,
                               text=True, timeout=1800, env=child_env)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"[{label}] claude -p timed out after 1800s")
        if r.returncode == 0:
            break
        # Only retry when there's no useful error to surface (transient crash)
        if r.stderr.strip() or r.stdout.strip():
            break
        last_err = RuntimeError(f"[{label}] claude -p failed silently (rc={r.returncode}), attempt {attempt+1}")
        if attempt == 0:
            import time as _time; _time.sleep(5)
    if r.returncode != 0:
        # Find error/result events in stdout for diagnosis
        err_events = []
        for _line in r.stdout.splitlines():
            try:
                _obj = json.loads(_line)
                if _obj.get("type") in ("error", "result") or "error" in str(_obj.get("subtype", "")):
                    err_events.append(json.dumps(_obj)[:400])
            except Exception:
                pass
        raise RuntimeError(f"[{label}] claude -p failed (rc={r.returncode}): {'; '.join(err_events) or r.stderr[:300] or r.stdout[-300:]}")

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
        # ```json … ``` fenced responses are common for Claude Code and the
        # caller (qa_evaluator/llm.py, merger _agent) strips fences before
        # parsing — silence the noise. Only flag genuinely non-JSON output.
        if stripped.startswith("```"):
            inner = stripped[3:]
            if inner.startswith("json"):
                inner = inner[4:]
            inner = inner.lstrip("\n").rstrip()
            if inner.endswith("```"):
                inner = inner[:-3].rstrip()
            stripped_eff = inner
        else:
            stripped_eff = stripped
        if not (stripped_eff.startswith("{") or stripped_eff.startswith("[")):
            print(f"    ⚠  [{label}] Expected JSON but got: {repr(stripped[:80])}")

    return text
