#!/usr/bin/env python3
"""janitor_gate.py — the verification gate for code deletions.

Run standalone to check repo health, or with --manifest to additionally verify
that a specific set of deletions didn't break anything:

    python3 scripts/janitor_gate.py --json /tmp/gate.json
    python3 scripts/janitor_gate.py --manifest private/janitor/manifest.json

Gates (each independent; all must pass):

  compile    py_compile every tracked .py                        — syntax
  pyflakes   NEW "undefined name" findings vs. a baseline        — the one that
             actually catches in-file dead-code removal, because a helper used
             only inside a function body imports fine and NameErrors at runtime
  imports    import shared/* + every main-guarded module         — module-level
             breakage. Script-style modules (build_search_index, agent run.py)
             are NOT imported — importing them runs the pipeline; they are
             reported as skipped, never silently dropped
  refs       grep every deleted filename/symbol across the repo  — catches the
             dynamic references static analysis can't see: shell scripts,
             launchd plists, JSON config, `getattr`, prompt strings
  web        cd web && npm run build                             — deleted
             components/utils still referenced by pages
  pipeline   exercise real post-publication pipeline code paths  — run_all
             registry, TL;DR binding audit, search-index rebuild

The grep sweep deliberately reaches OUTSIDE git: local-cycle.sh is gitignored
but is the actual daily runner, and the launchd plists live in ~/Library. A
deletion that only breaks the gitignored runner is still a broken pipeline.

Why there is no true end-to-end dry run: publish_data.py has no output-dir
override and re-running it mutates the published briefing (same-day union,
TTS, claude -p TL;DR regen). The strongest cheap proof is the combination
above; the real end-to-end proof is the next morning's pipeline run, which is
why code_janitor.py records every merge so the next day can revert it.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

_root = next((p for p in Path(__file__).resolve().parents
              if (p / "shared" / "__init__.py").exists()), None)
if _root:
    sys.path.insert(0, str(_root))
ROOT = _root or Path(__file__).resolve().parent.parent

# Vendored/third-party trees that are not ours to police.
_EXCLUDE_PARTS = {".claude", "node_modules", "__pycache__", ".next", "venv", ".venv"}

# Extra non-git locations that reference repo code by name. local-cycle.sh is
# gitignored on purpose (personal runner) but drives the entire daily pipeline.
_EXTRA_REF_FILES = [
    ROOT / "local-cycle.sh",
    Path.home() / "Library/LaunchAgents/com.kobyalmog.ai-briefing-daily.plist",
    Path.home() / "Library/LaunchAgents/com.kobyalmog.ai-briefing-healthcheck.plist",
    Path.home() / "Library/LaunchAgents/com.kobyalmog.ai-briefing-janitor.plist",
]
_EXTRA_REF_DIRS = [ROOT / "private"]
# `janitor` is skipped to break a self-poisoning loop: the janitor writes its run
# record (every candidate path and symbol it considered) into private/janitor/,
# which is inside this very corpus. Left in, yesterday's report counts as a
# reference to today's candidates and the detector goes permanently blind.
_EXTRA_REF_DIR_SKIP = {"logs", "temp", "output", "__pycache__", "janitor"}


def _sh(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except FileNotFoundError as e:
        return 127, str(e)


def tracked_files(exts: tuple[str, ...] | None = None) -> list[Path]:
    """Git-tracked files, minus vendored trees. Deleted-but-unstaged files are
    filtered out so the gate reflects the working tree, not the index."""
    code, out = _sh(["git", "ls-files"])
    if code != 0:
        return []
    res = []
    for line in out.splitlines():
        p = ROOT / line
        if _EXCLUDE_PARTS & set(Path(line).parts):
            continue
        if exts and p.suffix not in exts:
            continue
        if p.is_file():
            res.append(p)
    return res


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


# ── gate: compile ────────────────────────────────────────────────────────────
def gate_compile() -> dict:
    failures = []
    # cfile must be a regular file (py_compile refuses /dev/null), and must not
    # land next to the source — a stray __pycache__ would dirty the worktree.
    with tempfile.TemporaryDirectory() as tmp:
        for i, p in enumerate(tracked_files((".py",))):
            try:
                py_compile.compile(str(p), cfile=str(Path(tmp) / f"{i}.pyc"),
                                   doraise=True)
            except py_compile.PyCompileError as e:
                failures.append({"file": _rel(p), "error": str(e).strip()[:400]})
    return {"ok": not failures, "failures": failures,
            "detail": f"{len(failures)} file(s) failed to compile"}


# ── gate: pyflakes ───────────────────────────────────────────────────────────
_FATAL_PYFLAKES = ("undefined name", "referenced before assignment",
                   "undefined local")


def _pyflakes_findings(python_bin: str) -> tuple[list[str], str]:
    """Return (fatal findings, note). Fatal = undefined names only; unused
    imports are noise here (the janitor's whole job is to create fewer of them)."""
    files = [str(p) for p in tracked_files((".py",))]
    if not files:
        return [], "no python files"
    code, out = _sh([python_bin, "-m", "pyflakes", *files], timeout=300)
    if code == 127 or "No module named pyflakes" in out:
        return [], "pyflakes unavailable — gate skipped"
    fatal = [ln.strip() for ln in out.splitlines()
             if any(k in ln.lower() for k in _FATAL_PYFLAKES)]
    return fatal, ""


def gate_pyflakes(python_bin: str, baseline: list[str] | None) -> dict:
    fatal, note = _pyflakes_findings(python_bin)
    if note:
        return {"ok": True, "skipped": True, "detail": note}
    if baseline is None:
        return {"ok": not fatal, "new_findings": fatal, "all_findings": fatal,
                "detail": f"{len(fatal)} undefined-name finding(s) (no baseline)"}
    new = sorted(set(fatal) - set(baseline))
    return {"ok": not new, "new_findings": new, "all_findings": fatal,
            "detail": f"{len(new)} new undefined-name finding(s) "
                      f"({len(baseline)} pre-existing, ignored)"}


# ── gate: imports ────────────────────────────────────────────────────────────
def _module_name(p: Path) -> str | None:
    rel = p.relative_to(ROOT)
    if rel.suffix != ".py" or rel.name == "__init__.py":
        return None
    return ".".join(rel.with_suffix("").parts)


_PATH_SNIPPET = """
import importlib.util, sys
sys.argv = ["janitor-gate"]
spec = importlib.util.spec_from_file_location("_gate_probe", {path!r})
mod = importlib.util.module_from_spec(spec)
sys.modules["_gate_probe"] = mod
spec.loader.exec_module(mod)
"""

_DOTTED_SNIPPET = """
import importlib, sys
sys.argv = ["janitor-gate"]
importlib.import_module({dotted!r})
"""


def _probe_cmd(p: Path) -> tuple[list[str], Path]:
    """How to import this file, and from where.

    A module inside a package (its dir has __init__.py) MUST be imported by
    dotted name from the package's parent — `shared/article_reader.py` does
    `from . import article_cache`, which is an ImportError under a path-based
    load. A standalone script is loaded by path with its own dir as cwd, which
    is how run_all.py invokes agents."""
    if (p.parent / "__init__.py").exists():
        parts, d = [p.stem], p.parent
        while (d / "__init__.py").exists():
            parts.insert(0, d.name)
            d = d.parent
        return ["-c", _DOTTED_SNIPPET.format(dotted=".".join(parts))], d
    return ["-c", _PATH_SNIPPET.format(path=str(p))], p.parent


def gate_imports(python_bin: str, baseline: list[str] | None = None) -> dict:
    """Import every main-guarded module and everything in shared/.

    Script-style modules execute their work at module level — importing
    build_search_index.py hits S3, importing an agent's run.py runs the agent.
    Those are reported under `not_importable`, never silently dropped.

    Each module is imported by FILE PATH with its own directory as cwd and on
    sys.path, because that is how run_all.py invokes agents (cwd=script.parent);
    importing `agents.active.tavily-news-agent.run` from the repo root fails on
    the agent's own `from tavily_news_agent import ...` even though the module
    is perfectly healthy.

    Pre-existing failures (an optional dep the environment lacks) are passed in
    as `baseline` and only NEW failures are fatal — a gate that starts red can
    never go green, and would block every future sweep."""
    probes, not_importable = [], []
    for p in tracked_files((".py",)):
        if _module_name(p) is None:
            continue
        rel = _rel(p)
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if rel.startswith("shared/") or "if __name__ ==" in src:
            probes.append(p)
        else:
            not_importable.append(rel)

    failures, known = [], set(baseline or [])
    new_failures = []
    # One subprocess per module: a module that hard-exits or hangs must not take
    # the whole gate down with it, and import side effects must not accumulate.
    for p in probes:
        cmd_tail, cwd = _probe_cmd(p)
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(
            [str(cwd), str(ROOT), os.environ.get("PYTHONPATH", "")])}
        try:
            r = subprocess.run([python_bin, *cmd_tail],
                               cwd=str(cwd), capture_output=True, text=True,
                               timeout=120, env=env)
            code, out = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            code, out = 124, "import timed out after 120s"
        if code != 0:
            rel_p = _rel(p)
            failures.append({"module": rel_p, "error": out.strip()[-600:]})
            if rel_p not in known:
                new_failures.append(rel_p)

    fatal = new_failures if baseline is not None else [f["module"] for f in failures]
    return {"ok": not fatal, "failures": failures, "new_failures": new_failures,
            "imported": len(probes), "not_importable": sorted(not_importable),
            "detail": f"{len(fatal)} new / {len(failures)} total import failure(s) "
                      f"of {len(probes)} probed; {len(not_importable)} script-style "
                      "module(s) not importable"}


# ── gate: refs ───────────────────────────────────────────────────────────────
def _ref_corpus(deleted_paths: set[str]) -> list[Path]:
    corpus = [p for p in tracked_files() if _rel(p) not in deleted_paths
              and p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif",
                                           ".mp3", ".ico", ".webp", ".woff",
                                           ".woff2", ".pdf"}]
    for f in _EXTRA_REF_FILES:
        if f.is_file():
            corpus.append(f)
    for d in _EXTRA_REF_DIRS:
        if not d.is_dir():
            continue
        for f in d.rglob("*"):
            if not f.is_file() or f.stat().st_size > 2_000_000:
                continue
            if _EXTRA_REF_DIR_SKIP & set(f.relative_to(d).parts):
                continue
            if f.suffix.lower() in {".py", ".sh", ".md", ".json", ".jsonl",
                                    ".plist", ".txt", ".yml", ".yaml", ".mjs"}:
                corpus.append(f)
    return corpus


def gate_refs(manifest: dict | None) -> dict:
    """Every deleted file stem and removed symbol must appear nowhere else."""
    if not manifest:
        return {"ok": True, "skipped": True, "detail": "no manifest — nothing to check"}

    deleted_paths = {d["path"] for d in manifest.get("deleted_files", [])}
    needles: list[tuple[str, str]] = []
    for d in manifest.get("deleted_files", []):
        stem = Path(d["path"]).stem
        if stem and stem not in {"__init__", "index"}:
            needles.append((stem, f"deleted file {d['path']}"))
    for s in manifest.get("deleted_symbols", []):
        needles.append((s["symbol"], f"removed symbol from {s['path']}"))

    if not needles:
        return {"ok": True, "detail": "manifest recorded no deletions"}

    corpus = _ref_corpus(deleted_paths)
    hits = []
    for needle, origin in needles:
        for f in corpus:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if needle not in text:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if needle in line:
                    hits.append({"needle": needle, "origin": origin,
                                 "file": _rel(f), "line": i,
                                 "text": line.strip()[:200]})
                    break
    return {"ok": not hits, "hits": hits,
            "detail": f"{len(hits)} surviving reference(s) to deleted code",
            "checked": len(needles), "corpus_size": len(corpus)}


# ── gate: web build ──────────────────────────────────────────────────────────
def gate_web() -> dict:
    web = ROOT / "web"
    if not (web / "package.json").exists():
        return {"ok": True, "skipped": True, "detail": "no web/ project"}
    code, out = _sh(["npm", "run", "build"], cwd=web, timeout=1800)
    return {"ok": code == 0, "detail": "next build ok" if code == 0
            else "next build FAILED", "output": out[-4000:] if code else ""}


# ── gate: pipeline ───────────────────────────────────────────────────────────
def gate_pipeline(python_bin: str) -> dict:
    """Exercise real pipeline code paths without mutating published data.

    search-index rebuild genuinely runs and writes, so its output file is
    snapshotted and restored — the gate must never leave a data byproduct
    behind for the next commit to pick up."""
    steps, ok = [], True

    for label, cmd, timeout in [
        ("run_all registry", [python_bin, "run_all.py", "--list"], 120),
        ("tldr binding audit", [python_bin, "scripts/audit_tldr_binding.py"], 300),
    ]:
        script = ROOT / cmd[1]
        if not script.exists():
            steps.append({"step": label, "ok": True, "skipped": "script absent"})
            continue
        code, out = _sh(cmd, timeout=timeout)
        steps.append({"step": label, "ok": code == 0, "output": out[-1500:]})
        ok = ok and code == 0

    idx = ROOT / "docs/data/search-index.json"
    bsi = ROOT / "scripts/build_search_index.py"
    if bsi.exists():
        snapshot = idx.read_bytes() if idx.exists() else None
        env = {**os.environ, "SKIP_S3_UPLOAD": "1"}
        try:
            r = subprocess.run([python_bin, "scripts/build_search_index.py"],
                               cwd=str(ROOT), capture_output=True, text=True,
                               timeout=900, env=env)
            code, out = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            code, out = 124, "timed out"
        finally:
            if snapshot is not None:
                idx.write_bytes(snapshot)
            elif idx.exists():
                idx.unlink()
        steps.append({"step": "search-index rebuild", "ok": code == 0,
                      "output": out[-1500:]})
        ok = ok and code == 0

    return {"ok": ok, "steps": steps,
            "detail": f"{sum(1 for s in steps if not s['ok'])} pipeline step(s) failed"}


# ── driver ───────────────────────────────────────────────────────────────────
GATES = ("compile", "pyflakes", "imports", "refs", "web", "pipeline")


def collect_baseline(python_bin: str, tools_python: str | None = None) -> dict:
    """Snapshot the findings a healthy-but-imperfect repo already has, so a
    later gate run can tell "this deletion broke it" from "it was already
    like that"."""
    flakes, _ = _pyflakes_findings(tools_python or python_bin)
    imports = gate_imports(python_bin, baseline=None)
    return {"pyflakes": flakes,
            "imports": [f["module"] for f in imports["failures"]]}


def run_gate(python_bin: str, manifest: dict | None = None,
             baseline: dict | None = None, skip: set[str] = frozenset(),
             tools_python: str | None = None) -> dict:
    """`tools_python` runs the detectors (pyflakes) — the janitor keeps them in
    its own venv so it never mutates the interpreter the pipeline runs on."""
    results = {}
    if "compile" not in skip:
        results["compile"] = gate_compile()
    if "pyflakes" not in skip:
        results["pyflakes"] = gate_pyflakes(tools_python or python_bin,
                                            (baseline or {}).get("pyflakes")
                                            if baseline else None)
    if "imports" not in skip:
        results["imports"] = gate_imports(
            python_bin, (baseline or {}).get("imports") if baseline else None)
    if "refs" not in skip:
        results["refs"] = gate_refs(manifest)
    if "web" not in skip:
        results["web"] = gate_web()
    if "pipeline" not in skip:
        results["pipeline"] = gate_pipeline(python_bin)
    failed = sorted(k for k, v in results.items() if not v.get("ok"))
    return {"ok": not failed, "failed_gates": failed, "gates": results}


def main() -> int:
    ap = argparse.ArgumentParser(description="Verification gate for code deletions")
    ap.add_argument("--manifest", help="JSON manifest of deletions to verify")
    ap.add_argument("--baseline", help="JSON baseline from --write-baseline")
    ap.add_argument("--write-baseline", metavar="PATH",
                    help="record current findings as the baseline and exit")
    ap.add_argument("--json", help="write the full verdict here")
    ap.add_argument("--skip", nargs="*", default=[], choices=GATES,
                    help="gates to skip (e.g. --skip web pipeline)")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--tools-python", help="interpreter that has pyflakes")
    args = ap.parse_args()

    if args.write_baseline:
        base = collect_baseline(args.python, args.tools_python)
        Path(args.write_baseline).parent.mkdir(parents=True, exist_ok=True)
        Path(args.write_baseline).write_text(json.dumps(base, indent=2))
        print(f"baseline: {len(base['pyflakes'])} pyflakes finding(s), "
              f"{len(base['imports'])} import failure(s) → {args.write_baseline}")
        return 0

    manifest = json.loads(Path(args.manifest).read_text()) if args.manifest else None
    baseline = json.loads(Path(args.baseline).read_text()) if args.baseline else None

    verdict = run_gate(args.python, manifest, baseline, set(args.skip),
                       args.tools_python)

    for name, res in verdict["gates"].items():
        mark = "skip" if res.get("skipped") else ("ok  " if res["ok"] else "FAIL")
        print(f"  [{mark}] {name:9s} {res.get('detail', '')}")
    print(f"\n  gate: {'PASS' if verdict['ok'] else 'FAIL — ' + ', '.join(verdict['failed_gates'])}")

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(verdict, indent=2, ensure_ascii=False))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
