#!/usr/bin/env python3
"""code_janitor.py — daily dead-code sweep, run after publication.

    python3 scripts/code_janitor.py               # detect, delete, verify, PR
    python3 scripts/code_janitor.py --dry-run     # report only, touch nothing
    python3 scripts/code_janitor.py --no-web      # skip the (slow) next build

Shape of a run:

  1. preflight   clean worktree, on main, today's briefing exists
  2. baseline    run the gate BEFORE deleting anything. A repo that is already
                 red must not have that breakage attributed to the janitor —
                 the run aborts instead
  3. detect      unreferenced files (grep), in-file dead code (vulture),
                 unused web files/exports (knip)
  4. adjudicate  one claude -p call ranks every candidate SAFE / RISKY / KEEP.
                 The LLM only *judges* — it never edits. Every edit below is
                 deterministic (git rm, or ast-based excision), so a bad
                 judgment can delete the wrong thing but can never mangle a file
  5. apply       one commit per candidate, on a dated branch, never on main
  6. verify      the gate again, now with a deletion manifest
  7. repair      on failure, attribute the failing gate to the commits it names
                 and revert just those, then re-verify. Only if that still fails
                 does the whole branch get thrown away
  8. land        push, open a PR, and (unless JANITOR_AUTOMERGE=0) squash-merge
                 it once the gate is green

Env knobs:
  JANITOR_AUTOMERGE=0     open the PR but leave it for review
  JANITOR_MAX_DELETIONS   cap applied deletions per run (default 12)
  JANITOR_MAX_CANDIDATES  cap candidates sent for adjudication (default 40)

Deliberate limits, so a bad day stays small and reviewable: the caps above, and
symbol removal restricted to top-level functions, classes, and single-alias
imports. Anything outside that is reported for you, never auto-applied.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

_root = next((p for p in Path(__file__).resolve().parents
              if (p / "shared" / "__init__.py").exists()), None)
if _root:
    sys.path.insert(0, str(_root))
ROOT = _root or Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "scripts"))
import janitor_gate as G  # noqa: E402

STATE = ROOT / "private" / "janitor"
VENV = STATE / "venv"
MAX_DELETIONS = int(os.environ.get("JANITOR_MAX_DELETIONS", "12"))
MAX_CANDIDATES = int(os.environ.get("JANITOR_MAX_CANDIDATES", "40"))
AUTOMERGE = os.environ.get("JANITOR_AUTOMERGE", "1") == "1"

# Convention-loaded or externally-invoked — never candidates for deletion, no
# matter what static analysis says. Next.js resolves routes by filename; the
# top-level entrypoints are invoked by name from the gitignored runner.
NEVER_DELETE_NAMES = {"page.tsx", "layout.tsx", "route.ts", "not-found.tsx",
                      "error.tsx", "loading.tsx", "sitemap.ts", "robots.ts",
                      "middleware.ts", "__init__.py", "conftest.py"}
NEVER_DELETE_PATHS = {"run_all.py", "publish_data.py", "send_email.py",
                      "scripts/code_janitor.py", "scripts/janitor_gate.py"}
NEVER_DELETE_PREFIXES = ("shared/", "web/public/", "docs/data/", "infra/")

# Toolchain config is loaded by FILENAME by the tool that owns it, so nothing in
# the repo ever references it and every static analyser calls it unreferenced.
# This is the dangerous class: delete web/postcss.config.mjs and `next build`
# still exits 0 — Tailwind just silently stops emitting styles. The gate cannot
# catch that, so the janitor must never propose it.
NEVER_DELETE_RE = re.compile(
    r"(^|/)(\.[^/]+|[^/]*\.config\.[cm]?[jt]s|[^/]*\.config\.json|tsconfig[^/]*\.json"
    r"|package(-lock)?\.json|requirements[^/]*\.txt|Makefile|Dockerfile[^/]*)$")

log_lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg, flush=True)
    log_lines.append(msg)


def sh(cmd: list[str], cwd: Path | None = None, timeout: int = 600,
       check: bool = False) -> tuple[int, str]:
    code, out = G._sh(cmd, cwd=cwd, timeout=timeout)
    if check and code != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed ({code}):\n{out[-2000:]}")
    return code, out


def rel(p: Path) -> str:
    return G._rel(p)


# ── preflight ────────────────────────────────────────────────────────────────
def preflight(force: bool) -> str:
    code, out = sh(["git", "status", "--porcelain"])
    dirty = [ln for ln in out.splitlines() if ln.strip()]
    # Data byproducts are expected to be dirty after a pipeline run; code is not.
    code_dirty = [ln for ln in dirty
                  if not re.search(r"(docs/data/|\.mp3$|\.json$|\.jsonl$|cache/)", ln)]
    if code_dirty and not force:
        raise SystemExit("preflight: uncommitted CODE changes — refusing to run.\n  "
                         + "\n  ".join(code_dirty[:10]))

    _, branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch.strip()
    if branch != "main" and not force:
        raise SystemExit(f"preflight: on branch {branch!r}, expected main")

    today = date.today().isoformat()
    if not (ROOT / "docs" / "data" / f"{today}.json").exists() and not force:
        raise SystemExit(f"preflight: docs/data/{today}.json missing — "
                         "publication hasn't run yet today")

    _, sha = sh(["git", "rev-parse", "HEAD"])
    return sha.strip()


def python_bin() -> str:
    # Same pin as local-cycle.sh: pip and python3 resolve to different Homebrew
    # interpreters here, and only 3.11 has the per-agent deps installed.
    for cand in ("python3.11", "python3"):
        found = shutil.which(cand)
        if found:
            return found
    return sys.executable


def ensure_venv(py: str) -> str:
    """Self-contained venv for the detectors, so the janitor never mutates the
    interpreter the pipeline runs on."""
    vpy = VENV / "bin" / "python"
    if not vpy.exists():
        STATE.mkdir(parents=True, exist_ok=True)
        sh([py, "-m", "venv", str(VENV)], timeout=300, check=True)
    code, out = sh([str(vpy), "-c", "import vulture, pyflakes"])
    if code != 0:
        log("  installing detectors (vulture, pyflakes) into private/janitor/venv")
        sh([str(vpy), "-m", "pip", "install", "-q", "vulture", "pyflakes"],
           timeout=600, check=True)
    return str(vpy)


# ── detect: unreferenced whole files ─────────────────────────────────────────
def _protected(path: str, name: str) -> bool:
    return (name in NEVER_DELETE_NAMES or path in NEVER_DELETE_PATHS
            or path.startswith(NEVER_DELETE_PREFIXES)
            or bool(NEVER_DELETE_RE.search(path)))


def detect_unreferenced_files() -> list[dict]:
    exts = (".py", ".ts", ".tsx", ".mjs", ".js", ".sh")
    files = [p for p in G.tracked_files(exts) if not _protected(rel(p), p.name)]
    corpus = G._ref_corpus(set())
    corpus_text = {}
    for f in corpus:
        try:
            corpus_text[rel(f)] = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass

    out = []
    for p in files:
        stem, r = p.stem, rel(p)
        if len(stem) < 4:
            continue
        refs = [k for k, text in corpus_text.items() if k != r and stem in text]
        if refs:
            continue
        try:
            loc = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            loc = 0
        _, last = sh(["git", "log", "-1", "--format=%ad|%s", "--date=short", "--", r])
        out.append({"kind": "file", "path": r, "loc": loc,
                    "last_commit": last.strip()[:160],
                    "why": f"no other file in the repo mentions {stem!r}"})
    return out


# ── detect: in-file dead code (vulture) ──────────────────────────────────────
_VULTURE_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+): unused (?P<kind>\w+) '(?P<name>[^']+)' \((?P<conf>\d+)% confidence")


def detect_vulture(vpy: str, min_conf: int = 90) -> list[dict]:
    files = [str(p) for p in G.tracked_files((".py",))]
    if not files:
        return []
    code, out = sh([vpy, "-m", "vulture", "--min-confidence", str(min_conf), *files],
                   timeout=600)
    if code not in (0, 1, 3):
        log(f"  vulture exited {code} — skipping in-file detection\n{out[-500:]}")
        return []
    res = []
    for line in out.splitlines():
        m = _VULTURE_RE.match(line.strip())
        if not m:
            continue
        kind, name = m.group("kind"), m.group("name")
        if kind not in ("function", "class", "import", "method"):
            continue
        try:
            fpath = rel(Path(m.group("file")).resolve())
        except OSError:
            continue
        if fpath.startswith(NEVER_DELETE_PREFIXES) or fpath in NEVER_DELETE_PATHS:
            # shared/ is the reuse surface: a helper with no caller today is
            # exactly what the next agent is supposed to import. Report, never cut.
            continue
        res.append({"kind": "symbol", "path": fpath, "symbol": name,
                    "symbol_kind": kind, "line": int(m.group("line")),
                    "confidence": int(m.group("conf")),
                    "why": f"vulture: unused {kind} at {m.group('conf')}% confidence"})
    return res


# ── detect: web (knip) ───────────────────────────────────────────────────────
def detect_knip() -> list[dict]:
    web = ROOT / "web"
    if not (web / "package.json").exists():
        return []
    code, out = sh(["npx", "--yes", "knip", "--reporter", "json", "--no-progress"],
                   cwd=web, timeout=900)
    start = out.find("{")
    if start < 0:
        log("  knip produced no JSON — skipping web detection")
        return []
    try:
        data = json.loads(out[start:])
    except json.JSONDecodeError:
        log("  knip JSON unparseable — skipping web detection")
        return []

    res = []
    for entry in data.get("files", []) or []:
        p = f"web/{entry}" if not str(entry).startswith("web/") else str(entry)
        if _protected(p, Path(p).name):
            continue
        res.append({"kind": "file", "path": p, "loc": 0, "last_commit": "",
                    "why": "knip: file not reachable from any entrypoint"})
    for issue in data.get("issues", []) or []:
        fpath = issue.get("file", "")
        p = f"web/{fpath}" if fpath and not fpath.startswith("web/") else fpath
        if not p or _protected(p, Path(p).name):
            continue
        for ex in (issue.get("exports") or []):
            name = ex.get("name") if isinstance(ex, dict) else ex
            if name:
                res.append({"kind": "export", "path": p, "symbol": name,
                            "why": "knip: exported but never imported"})
    return res


# ── adjudicate ───────────────────────────────────────────────────────────────
ADJUDICATE_SYSTEM = """You review dead-code candidates for a Python + Next.js news
pipeline before an automated janitor deletes them. You do not edit code; you only
judge. Your judgment is the ONLY thing standing between a static-analysis false
positive and a broken production pipeline.

Classify each candidate:
  SAFE  — provably unreachable; deleting it cannot change behaviour
  RISKY — plausibly dead but reachable by a mechanism static analysis can't see
  KEEP  — actively used, or intentionally kept

Default to RISKY when unsure. A wrongly-kept file costs nothing; a wrongly-deleted
one breaks the daily briefing.

Mark RISKY or KEEP when the candidate could be reached by:
- dynamic dispatch: getattr, globals()/locals(), importlib, eval, dict-of-handlers
- a name that appears inside a STRING: LLM prompts, SQL, CLI args, JSON config,
  shell scripts, launchd plists, GitHub Actions workflows
- framework convention: Next.js route/layout files, pytest fixtures, __all__,
  serialization hooks, Pydantic/dataclass field validators
- a public/shared surface deliberately kept for reuse (this repo centralizes
  helpers in shared/ precisely so future agents can import them)
- a documented recovery or backfill procedure — one-off scripts named in a runbook
  are kept on purpose even though nothing imports them
- an entrypoint invoked only by a human, a cron/launchd job, or another repo

Mark SAFE for: superseded duplicates of logic that now lives in shared/, scripts
pinned to a past date that has passed, disabled agents, and imports of modules
whose only user was already deleted.

Return ONLY JSON:
{"verdicts":[{"id":<int>,"verdict":"SAFE|RISKY|KEEP","reason":"<= 25 words"}]}"""


def adjudicate(candidates: list[dict]) -> list[dict]:
    from shared import anthropic_cc

    # NOT anthropic_cc.is_enabled() — that gates on MERGER_VIA_CLAUDE_CODE, the
    # merger's opt-in flag, which says nothing about whether we can make a call.
    # Adjudication is the safety-critical step, so it runs at a higher effort
    # than the merger's default of "low".
    if not shutil.which("claude"):
        log("  claude -p unavailable — treating every candidate as RISKY")
        for c in candidates:
            c["verdict"], c["reason"] = "RISKY", "adjudicator unavailable"
        return candidates

    payload = []
    for i, c in enumerate(candidates):
        item = {"id": i, "kind": c["kind"], "path": c["path"], "why": c["why"]}
        if c.get("symbol"):
            item["symbol"] = c["symbol"]
            item["context"] = _symbol_context(c)
        else:
            item["loc"] = c.get("loc", 0)
            item["last_commit"] = c.get("last_commit", "")
            item["head"] = _file_head(c["path"])
        payload.append(item)

    os.environ.setdefault("MERGER_CC_EFFORT", "medium")
    raw = anthropic_cc.agent(
        json.dumps({"candidates": payload}, ensure_ascii=False),
        instructions=ADJUDICATE_SYSTEM, json_mode=True,
        label="code-janitor adjudication", soft_timeout=600,
    )
    from shared.json_repair import parse_json
    data = parse_json(raw) or {}
    verdicts = {v.get("id"): v for v in (data.get("verdicts") or [])
                if isinstance(v, dict)}
    for i, c in enumerate(candidates):
        v = verdicts.get(i) or {}
        c["verdict"] = str(v.get("verdict", "RISKY")).upper()
        c["reason"] = str(v.get("reason", "no verdict returned"))[:200]
        if c["verdict"] not in ("SAFE", "RISKY", "KEEP"):
            c["verdict"], c["reason"] = "RISKY", f"unparseable verdict: {c['reason']}"
    return candidates


def _file_head(path: str, n: int = 40) -> str:
    p = ROOT / path
    if not p.exists():
        return ""
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[:n]
    return "\n".join(lines)[:2500]


def _symbol_context(c: dict, span: int = 12) -> str:
    p = ROOT / c["path"]
    if not p.exists():
        return ""
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    i = max(0, c.get("line", 1) - 1)
    return "\n".join(lines[max(0, i - 2):i + span])[:2000]


# ── apply ────────────────────────────────────────────────────────────────────
def _import_alias_count(node: ast.AST) -> int:
    return len(getattr(node, "names", []) or [])


def excise_symbol(path: Path, symbol: str) -> tuple[bool, str]:
    """Remove a top-level function/class, or a single-alias import, by AST span.

    Deterministic: the span comes from the parsed tree, so the file is either
    edited exactly or left untouched. Multi-alias imports and nested symbols are
    refused — they need a human."""
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return False, f"unparseable: {e}"

    target = None
    for node in tree.body:  # top level only
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                target = node
                break
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.asname or a.name.split(".")[0] for a in node.names]
            if symbol in names:
                if _import_alias_count(node) != 1:
                    return False, "multi-alias import — needs manual edit"
                target = node
                break
    if target is None:
        return False, "symbol not found at top level"

    is_import = isinstance(target, (ast.Import, ast.ImportFrom))
    start = min([target.lineno] + [d.lineno for d in
                                   getattr(target, "decorator_list", [])])
    lines = src.splitlines(keepends=True)
    # Absorb the contiguous comment block immediately above — a function's
    # explanatory comment is dead the moment the function is.
    i = start - 2
    while i >= 0 and lines[i].lstrip().startswith("#"):
        i -= 1
    first = i + 1
    last = target.end_lineno  # 1-indexed, inclusive
    # A def owns the blank lines that separate it from what follows; an import
    # does not — eating them welds the import block onto the next statement.
    while not is_import and last < len(lines) and not lines[last].strip():
        last += 1

    new = "".join(lines[:first] + lines[last:])
    if new.strip() == src.strip():
        return False, "excision was a no-op"
    path.write_text(new, encoding="utf-8")
    return True, f"removed lines {first + 1}-{last}"


def apply_deletions(approved: list[dict]) -> tuple[list[dict], list[dict]]:
    """One commit per candidate, so repair can revert exactly one thing."""
    applied, refused = [], []
    for c in approved:
        p = ROOT / c["path"]
        if not p.exists():
            refused.append({**c, "refused": "path no longer exists"})
            continue

        if c["kind"] in ("file",):
            code, out = sh(["git", "rm", "-q", "--", c["path"]])
            if code != 0:
                refused.append({**c, "refused": out.strip()[:200]})
                continue
            msg = f"chore(janitor): delete unused {c['path']}"
        elif c["kind"] == "symbol" and p.suffix == ".py":
            ok, detail = excise_symbol(p, c["symbol"])
            if not ok:
                refused.append({**c, "refused": detail})
                continue
            sh(["git", "add", "--", c["path"]], check=True)
            call = "()" if c["symbol_kind"] in ("function", "method") else ""
            msg = (f"chore(janitor): drop unused {c['symbol_kind']} "
                   f"{c['symbol']}{call} from {c['path']}")
        else:
            # Unused TS/TSX exports: removing an export keyword safely needs a
            # TS-aware edit, which this janitor deliberately doesn't attempt.
            refused.append({**c, "refused": f"{c['kind']} removal not automated"})
            continue

        body = f"{c['why']}\n\nAdjudicated SAFE: {c['reason']}"
        code, out = sh(["git", "commit", "-q", "-m", msg, "-m", body])
        if code != 0:
            refused.append({**c, "refused": f"commit failed: {out.strip()[:200]}"})
            sh(["git", "reset", "-q", "HEAD"])
            continue
        _, sha = sh(["git", "rev-parse", "HEAD"])
        applied.append({**c, "sha": sha.strip(), "message": msg})
        log(f"    ✂ {msg}")
    return applied, refused


def build_manifest(applied: list[dict]) -> dict:
    return {
        "deleted_files": [{"path": c["path"], "sha": c["sha"]}
                          for c in applied if c["kind"] == "file"],
        "deleted_symbols": [{"path": c["path"], "symbol": c["symbol"], "sha": c["sha"]}
                            for c in applied if c["kind"] == "symbol"],
    }


# ── repair ───────────────────────────────────────────────────────────────────
def attribute_failure(verdict: dict, applied: list[dict]) -> list[dict]:
    """Map a red gate back to the commits it blames.

    Every gate reports the file or symbol at fault, so attribution is textual:
    a commit is culpable if its path or symbol appears anywhere in the failing
    gates' output. Unattributable failure → everything is culpable, because the
    alternative is guessing."""
    blob = json.dumps({k: v for k, v in verdict["gates"].items()
                       if not v.get("ok")}, ensure_ascii=False)
    culpable = [c for c in applied
                if c["path"] in blob or (c.get("symbol") and c["symbol"] in blob)]
    return culpable or list(applied)


def revert_commits(commits: list[dict]) -> None:
    for c in reversed(commits):  # newest first, so reverts apply cleanly
        code, out = sh(["git", "revert", "--no-edit", "--no-commit", c["sha"]])
        if code != 0:
            sh(["git", "revert", "--quit"])
            raise RuntimeError(f"revert of {c['sha'][:8]} failed: {out[-500:]}")
        sh(["git", "commit", "-q", "-m",
            f"Revert \"{c['message']}\"", "-m",
            "Reverted by code_janitor: verification gate failed after this deletion."])
        log(f"    ↩ reverted {c['message']}")


# ── land ─────────────────────────────────────────────────────────────────────
def land(branch: str, applied: list[dict], reverted: list[dict],
         verdict: dict, report: str) -> str:
    code, out = sh(["git", "push", "-u", "origin", branch], timeout=300)
    if code != 0:
        return f"push failed — branch kept locally only:\n{out[-500:]}"

    kept = [c for c in applied if c not in reverted]
    body = (f"Automated dead-code sweep.\n\n"
            f"**Deletions kept:** {len(kept)}  ·  **Reverted by the gate:** {len(reverted)}\n\n"
            + "\n".join(f"- `{c['path']}`"
                        + (f" — `{c['symbol']}`" if c.get("symbol") else "")
                        + f" — {c['reason']}" for c in kept)
            + f"\n\n### Verification gate\n\n```\n{report}\n```\n\n"
              "Revert this whole sweep with `git revert -m 1 <merge-sha>`.\n\n"
              "🤖 Generated with [Claude Code](https://claude.com/claude-code)")
    code, out = sh(["gh", "pr", "create", "--title",
                    f"chore(janitor): dead-code sweep {date.today().isoformat()}",
                    "--body", body, "--base", "main", "--head", branch], timeout=300)
    if code != 0:
        return f"gh pr create failed:\n{out[-500:]}"
    url = next((ln.strip() for ln in out.splitlines()
                if ln.strip().startswith("http")), out.strip())

    if not verdict["ok"]:
        return f"{url} (gate red — left open for review, NOT merged)"
    if not AUTOMERGE:
        return f"{url} (JANITOR_AUTOMERGE=0 — left open for review)"
    code, out = sh(["gh", "pr", "merge", branch, "--squash", "--delete-branch"],
                   timeout=300)
    if code != 0:
        return f"{url} (auto-merge failed, left open: {out.strip()[-300:]})"
    sh(["git", "checkout", "-q", "main"])
    sh(["git", "pull", "-q", "--ff-only"])
    return f"{url} (squash-merged)"


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="Daily dead-code sweep")
    ap.add_argument("--dry-run", action="store_true",
                    help="detect + adjudicate, delete nothing")
    ap.add_argument("--no-web", action="store_true", help="skip the next build gate")
    ap.add_argument("--no-pipeline", action="store_true", help="skip the pipeline gate")
    ap.add_argument("--force", action="store_true",
                    help="bypass preflight (dirty worktree / not main / no briefing)")
    ap.add_argument("--local-only", action="store_true",
                    help="delete + verify on the branch, but never push or open a PR")
    args = ap.parse_args()

    today = date.today().isoformat()
    STATE.mkdir(parents=True, exist_ok=True)
    skip = set()
    if args.no_web:
        skip.add("web")
    if args.no_pipeline:
        skip.add("pipeline")

    log(f"code_janitor · {today}")
    start_sha = preflight(args.force)
    py = python_bin()
    vpy = ensure_venv(py)
    log(f"  base {start_sha[:8]} · python {py}")

    log("\n[1/6] Baseline gate (before touching anything)")
    # Record what's already imperfect, THEN gate. Without this, a pre-existing
    # import failure (an optional dep this machine lacks) would keep the gate
    # permanently red and the janitor would abort every single day.
    baseline = G.collect_baseline(py, vpy)
    log(f"  baseline: {len(baseline['pyflakes'])} pyflakes finding(s), "
        f"{len(baseline['imports'])} pre-existing import failure(s)")
    for m in baseline["imports"]:
        log(f"    · known-bad import: {m}")
    base = G.run_gate(py, None, baseline, skip | {"refs"}, vpy)
    for name, res in base["gates"].items():
        log(f"  [{'skip' if res.get('skipped') else ('ok  ' if res['ok'] else 'FAIL')}] "
            f"{name:9s} {res.get('detail','')}")
    if not base["ok"]:
        log(f"\n  ABORT: repo is already failing {', '.join(base['failed_gates'])}. "
            "Fix that first — the janitor must not be blamed for it.")
        _save(today, {"status": "aborted_dirty_baseline", "baseline": base})
        return 2

    log("\n[2/6] Detecting dead code")
    candidates = detect_unreferenced_files() + detect_vulture(vpy) + detect_knip()
    log(f"  {len(candidates)} candidate(s)")
    if not candidates:
        log("\n  Nothing to do — repo is clean.")
        _save(today, {"status": "clean", "candidates": []})
        return 0
    capped = candidates[MAX_CANDIDATES:]
    candidates = candidates[:MAX_CANDIDATES]
    if capped:
        log(f"  capped at {MAX_CANDIDATES}; {len(capped)} deferred to tomorrow: "
            + ", ".join(c["path"] for c in capped[:8]))

    log("\n[3/6] Adjudicating")
    candidates = adjudicate(candidates)
    for c in candidates:
        log(f"  {c['verdict']:5s} {c['path']}"
            + (f"::{c['symbol']}" if c.get("symbol") else "")
            + f" — {c['reason']}")
    approved = [c for c in candidates if c["verdict"] == "SAFE"]
    deferred_cap = approved[MAX_DELETIONS:]
    approved = approved[:MAX_DELETIONS]
    if deferred_cap:
        log(f"  cap {MAX_DELETIONS}/run — {len(deferred_cap)} SAFE item(s) held for tomorrow: "
            + ", ".join(c["path"] for c in deferred_cap))

    if args.dry_run:
        log(f"\n  --dry-run: would delete {len(approved)} item(s), nothing changed.")
        _save(today, {"status": "dry_run", "candidates": candidates})
        return 0
    if not approved:
        log("\n  No SAFE candidates — nothing deleted.")
        _save(today, {"status": "nothing_safe", "candidates": candidates})
        return 0

    branch = f"chore/dead-code-{today}"
    sh(["git", "branch", "-D", branch])  # a re-run replaces the day's branch
    sh(["git", "checkout", "-q", "-b", branch], check=True)

    log(f"\n[4/6] Applying {len(approved)} deletion(s) on {branch}")
    applied, refused = apply_deletions(approved)
    for r in refused:
        log(f"    ⊘ skipped {r['path']} — {r['refused']}")
    if not applied:
        sh(["git", "checkout", "-q", "main"])
        sh(["git", "branch", "-D", branch])
        log("\n  Every deletion was refused — back on main, nothing changed.")
        _save(today, {"status": "all_refused", "candidates": candidates,
                      "refused": refused})
        return 0

    log("\n[5/6] Verification gate")
    manifest = build_manifest(applied)
    (STATE / f"manifest-{today}.json").write_text(json.dumps(manifest, indent=2))
    verdict = G.run_gate(py, manifest, baseline, skip, vpy)
    report = "\n".join(
        f"[{'skip' if r.get('skipped') else ('ok  ' if r['ok'] else 'FAIL')}] "
        f"{n:9s} {r.get('detail','')}" for n, r in verdict["gates"].items())
    log("  " + report.replace("\n", "\n  "))

    reverted: list[dict] = []
    if not verdict["ok"]:
        log(f"\n  Gate FAILED: {', '.join(verdict['failed_gates'])} — attempting repair")
        culpable = attribute_failure(verdict, applied)
        log(f"  attributing to {len(culpable)} of {len(applied)} deletion(s)")
        try:
            revert_commits(culpable)
            reverted = culpable
        except RuntimeError as e:
            log(f"  repair failed to revert cleanly ({e}) — discarding the whole branch")
            sh(["git", "reset", "-q", "--hard", start_sha])
            sh(["git", "checkout", "-q", "main"])
            sh(["git", "branch", "-D", branch])
            _save(today, {"status": "reverted_all", "candidates": candidates,
                          "applied": applied, "verdict": verdict})
            return 1

        verdict = G.run_gate(py, build_manifest([c for c in applied
                                                 if c not in reverted]),
                             baseline, skip, vpy)
        if not verdict["ok"]:
            log(f"  still failing {', '.join(verdict['failed_gates'])} after repair "
                "— discarding the whole branch")
            sh(["git", "reset", "-q", "--hard", start_sha])
            sh(["git", "checkout", "-q", "main"])
            sh(["git", "branch", "-D", branch])
            _save(today, {"status": "reverted_all", "candidates": candidates,
                          "applied": applied, "verdict": verdict})
            return 1
        log("  repair held — gate green with the culpable deletions reverted")

    log("\n[6/6] Landing")
    if args.local_only:
        result = f"--local-only: left on branch {branch}, not pushed"
    else:
        result = land(branch, applied, reverted, verdict, report)
    log(f"  {result}")

    kept = len(applied) - len(reverted)
    log(f"\nDone · {kept} deletion(s) kept, {len(reverted)} reverted, "
        f"{len(refused)} refused")
    _save(today, {"status": "landed", "branch": branch, "candidates": candidates,
                  "applied": applied, "reverted": reverted, "refused": refused,
                  "verdict": verdict, "pr": result, "base_sha": start_sha})
    return 0


def _save(today: str, payload: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    payload["date"] = today
    (STATE / f"run-{today}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (STATE / f"run-{today}.log").write_text("\n".join(log_lines), encoding="utf-8")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # a janitor crash must never leave a stray branch
        log(f"\nFATAL: {exc}")
        _, br = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        if br.strip().startswith("chore/dead-code-"):
            sh(["git", "reset", "-q", "--hard"])
            sh(["git", "checkout", "-q", "main"])
            log("  returned to main; the sweep branch was left for inspection")
        _save(date.today().isoformat(), {"status": "crashed", "error": str(exc)})
        sys.exit(3)
