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
import re
import subprocess
import time


class UsagePolicyRefusal(RuntimeError):
    """`claude -p` blocked the request under Anthropic's Usage Policy (AUP).

    Raised instead of a generic RuntimeError so callers can catch it
    distinctly and *quarantine the offending source item(s) and retry*
    rather than failing the whole agent. Observed 2026-06-07: a
    security-exploit news item ("violative cyber content") made the
    BriefingWriter refuse, which crashed rss + tavily and ultimately the
    merger — taking down the entire daily run.
    """


# Headline/summary terms that commonly trip Anthropic's AUP classifier when fed
# into the briefing writer. The AUP covers more than "cyber": security-exploit
# content AND biological / chemical / weapons content (observed 2026-06-07: a
# "fed every coronavirus genome into an AI model → cleared human trials" story
# triggered a refusal). Used by agent_quarantine() as a FAST first pass to drop
# the likely offender — NOT to filter news in general (these stories are
# legitimate; we just can't let one sink the whole batch on the subscription
# path). When this heuristic misses, agent_quarantine falls back to a
# content-agnostic progressive drop.
_RISK_RE = re.compile(
    r"\b("
    # cyber / security-exploit
    r"rce|remote code execution|exploit|0-?day|zero-?day|cve-\d|malware|"
    r"ransomware|backdoor|payload|botnet|rootkit|keylogger|privilege escalation|"
    r"arbitrary code|deserialization|sql injection|buffer overflow|"
    r"proof[- ]of[- ]concept|poc exploit|weaponiz|jailbreak|"
    # biological / chemical / weapons (CBRN)
    r"pathogen|virus genome|coronavirus|influenza|bioweapon|biological weapon|"
    r"nerve agent|chemical weapon|toxin|nuclear weapon|enrichment|gain[- ]of[- ]function"
    r")\b",
    re.IGNORECASE,
)


def looks_cyber_risky(text: str) -> bool:
    """Heuristic: does this text read like content (cyber-exploit or CBRN) that
    may trip Anthropic's AUP classifier? Name kept for back-compat; coverage is
    broader than cyber. Best-effort — agent_quarantine has a content-agnostic
    fallback for the cases this misses."""
    return bool(_RISK_RE.search(text or ""))


def is_enabled() -> bool:
    return os.environ.get("MERGER_VIA_CLAUDE_CODE") == "1"


def _cc_model() -> str:
    # Respect explicit override, then the model the active Claude Code session
    # is configured for (ANTHROPIC_MODEL is set to a Bedrock-prefixed id like
    # "eu.anthropic.claude-opus-4-8" under CLAUDE_CODE_USE_BEDROCK=1, and to a
    # plain id like "claude-opus-4-8" under Claude Max subscription). Fall back
    # to the subscription-style id.
    return (
        os.environ.get("MERGER_CC_MODEL")
        or os.environ.get("ANTHROPIC_MODEL")
        or "claude-opus-4-8"
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
    for attempt in range(4):  # up to 3 retries for transient/overload errors
        try:
            r = subprocess.run(cmd, input=input_text, capture_output=True,
                               text=True, timeout=1800, env=child_env)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"[{label}] claude -p timed out after 1800s")
        if r.returncode == 0:
            break
        # Check for 529 overloaded — always worth retrying with backoff
        is_529 = "529" in r.stdout or "Overloaded" in r.stdout
        if is_529 and attempt < 3:
            wait = 30 * (attempt + 1)  # 30s, 60s, 90s
            print(f"    ⚠  [{label}] API 529 overloaded, retrying in {wait}s (attempt {attempt+1}/3)...")
            time.sleep(wait)
            continue
        # Only retry silent failures (no output to diagnose)
        if r.stderr.strip() or r.stdout.strip():
            break
        last_err = RuntimeError(f"[{label}] claude -p failed silently (rc={r.returncode}), attempt {attempt+1}")
        if attempt == 0:
            time.sleep(5)
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
        _detail = "; ".join(err_events) or r.stderr[:300] or r.stdout[-300:]
        # Distinguish a Usage-Policy / AUP refusal from a generic failure so
        # callers can quarantine the offending input item and retry instead of
        # hard-failing the whole agent (2026-06-07 cyber-content incident).
        if re.search(r"usage policy|violat|cyber content|\baup\b", _detail, re.IGNORECASE):
            raise UsagePolicyRefusal(f"[{label}] claude -p blocked by Usage Policy: {_detail}")
        raise RuntimeError(f"[{label}] claude -p failed (rc={r.returncode}): {_detail}")

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


def agent_quarantine(
    articles: list,
    build_input,
    call,
    *,
    text_of=None,
    label: str = "",
    max_rounds: int = 3,
) -> str:
    """Run a briefing-writer call that's resilient to a Usage-Policy refusal.

    - `build_input(articles) -> input_text` builds the prompt from a list of
      source articles.
    - `call(input_text) -> str` performs the actual LLM call (pass the caller's
      own `_agent`, with model/instructions bound, so the API-key fallback path
      is preserved — not just the subscription path).

    On a UsagePolicyRefusal we drop the offending article(s) and retry, so one
    "violative" story (cyber-exploit OR biological/CBRN — 2026-06-07) can't sink
    the whole agent and, downstream, the whole daily run. Two strategies, in
    order, each round:
      1. KEYWORD pass — drop items matching looks_cyber_risky(text_of(item)).
      2. CONTENT-AGNOSTIC fallback — if the keyword pass finds nothing new (the
         AUP category isn't in our term list), drop the bottom ~third of the
         (priority-ordered) pool and retry. We lose a few low-priority articles
         but the agent degrades gracefully instead of hard-failing.
    Re-raises only if even a single remaining article is still refused.
    """
    if text_of is None:
        text_of = lambda a: f"{a.get('headline', '')} {a.get('summary', '')}"
    pool = list(articles)
    for round_i in range(max_rounds):
        try:
            return call(build_input(pool))
        except UsagePolicyRefusal:
            if len(pool) <= 1:
                raise  # a single article still refused — not a quarantine case
            risky_ids = {id(a) for a in pool if looks_cyber_risky(text_of(a))}
            if risky_ids and len(risky_ids) < len(pool):
                kept = [a for a in pool if id(a) not in risky_ids]
                how = f"quarantined {len(risky_ids)} flagged item(s)"
            else:
                # Keyword heuristic missed it (or flagged everything) — drop the
                # lowest-priority third and retry. Priority-ordered input means
                # the most important articles survive.
                cut = max(1, len(pool) // 3)
                kept = pool[: len(pool) - cut]
                how = f"dropped bottom {cut} (no keyword match)"
            print(f"    ⚠  [{label}] Usage-Policy refusal — {how}, "
                  f"retrying with {len(kept)} (round {round_i + 1}/{max_rounds})")
            pool = kept
    raise UsagePolicyRefusal(
        f"[{label}] still Usage-Policy blocked after {max_rounds} quarantine rounds"
    )
