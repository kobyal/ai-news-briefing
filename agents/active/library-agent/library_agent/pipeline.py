"""Library Agent — one reviewed long-form talk per run into /library ("talks").

Stages (each idempotent, so a run cut short by LIBRARY_TIME_BUDGET_S resumes):
  discover+rank → prep (fetch/asr/slides, skill venv) → write content.json
  → render (DOCX+PDF) → cleanup → index/state → manifest + publish.

Session layout mirrors the AWS Summit collection so scripts/build_library_manifest.py
reads both the same way: collections/talks/sessions/<yt-ID>/{meta,content,status}.json,
transcript*.txt, frames/, out/, and sessions/index.json.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from shared.repo_root import agent_dir, repo_root

from . import discover
from .writer import write_content

AGENT = agent_dir("library-agent")
SESSIONS = AGENT / "collections" / "talks" / "sessions"
STATE_PATH = AGENT / "state" / "state.json"
R2R_HOME = Path(os.environ.get("R2R_HOME", Path.home() / ".claude/skills/recording-to-review"))
R2R_PY = R2R_HOME / ".venv" / "bin" / "python"
R2R_LIB = R2R_HOME / "lib"

_usage_log: list[dict] = []


class BudgetExceeded(Exception):
    pass


class Budget:
    def __init__(self):
        self.t0 = time.time()
        self.limit = int(os.environ.get("LIBRARY_TIME_BUDGET_S", "1500"))
        self.marks: dict[str, int] = {}

    def check(self, next_stage: str):
        if time.time() - self.t0 > self.limit:
            raise BudgetExceeded(f"{self.limit}s budget spent before '{next_stage}'")

    def mark(self, stage: str, t_start: float):
        self.marks[stage] = round(time.time() - t_start)
        print(f"  ✓ {stage} {self.marks[stage]}s", flush=True)


def _load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _save_state(state: dict):
    state["runs"] = state.get("runs", [])[-20:]
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


# ── stages ──────────────────────────────────────────────────────────────────

def _pick(state: dict, args, budget: Budget) -> dict | None:
    """Which talk to produce: --url > an unfinished one from last run > ranking."""
    if args.url:
        vid = args.url.split("v=")[-1].split("&")[0].split("/")[-1]
        info = discover.video_info(vid)
        if not info:
            raise RuntimeError(f"yt-dlp returned no metadata for {args.url}")
        return info
    if state.get("in_progress") and not args.dry_run:
        ip = state["in_progress"]
        ip["attempts"] = ip.get("attempts", 0) + 1
        # A talk that keeps failing (dead video, writer refusal) must not block
        # the collection forever: three tries, then it is parked and ranking resumes.
        if ip["attempts"] > 3:
            print(f"  giving up on {ip['id']} after {ip['attempts'] - 1} failed attempts")
            state["rejected"][ip["id"]] = {"reason": "failed 3 runs", "title": ip["title"][:80]}
            state.pop("in_progress")
        else:
            print(f"  resuming {ip['id']} (attempt {ip['attempts']})")
            return ip

    t = time.time()
    skip = set(state["done"]) | set(state["rejected"])
    cands = discover.candidates(skip)
    ranked = discover.rank(cands, _usage_log)
    budget.mark("discover", t)
    print(f"\n  ranking ({len(cands)} candidates):")
    for i, r in enumerate(ranked[:10], 1):
        print(f"   {i:2}. {r.get('score', '?'):>4}  {r['id']}  {r['minutes']:3}m  {r['channel'][:22]:<22} {r['title'][:70]}")
        print(f"        {r.get('reason', '')[:110]}")
    state["runs"].append({"date": datetime.now().strftime("%Y-%m-%d"), "candidates": len(cands),
                          "ranked": [{k: r.get(k) for k in ("id", "score", "reason")} for r in ranked]})
    # Explicit low scorers are remembered so they aren't fetched and re-scored
    # daily; unscored and mid scorers stay eligible for a better day.
    for r in ranked:
        if isinstance(r.get("score"), (int, float)) and r["score"] < 5:
            state["rejected"][r["id"]] = {"reason": f"score {r['score']}", "title": r["title"][:80]}
    return ranked[0] if ranked else None


def _prep(session: Path, info: dict, budget: Budget):
    t = time.time()
    session.mkdir(parents=True, exist_ok=True)
    meta = session / "meta.json"
    if not meta.exists():
        meta.write_text(json.dumps({"source": info["url"], "kind": "youtube", **{
            k: info.get(k) for k in ("id", "title", "channel", "upload_date", "minutes", "description", "chapters")}},
            ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([str(R2R_PY), str(Path(__file__).with_name("prep.py")), str(R2R_LIB), str(session),
                    info["url"], "--lang", info.get("language") or "en"], check=True)
    budget.mark("prep", t)


def _render(session: Path, lang: str, budget: Budget) -> Path:
    t = time.time()
    content = session / "content.json"
    out = session / "out"
    pdf = out / f"{session.name}_{lang.upper()}.pdf"
    if not (pdf.exists() and pdf.stat().st_mtime > content.stat().st_mtime):
        subprocess.run([str(R2R_PY), str(R2R_LIB / "render.py"), str(content), str(out),
                        "--name", pdf.stem, "--slides", str(session / "frames" / "crop")], check=True)
    budget.mark("render", t)
    return pdf


def _cleanup(session: Path):
    # Keep frames/crop + contact sheets (a re-render or re-write needs them);
    # the video and the uncropped frames are ~1GB of dead weight per talk.
    for p in ("rec.mp4", "audio.wav", "frames/raw", "frames/kept"):
        target = session / p
        shutil.rmtree(target, ignore_errors=True) if target.is_dir() else target.unlink(missing_ok=True)


def _index(session: Path, info: dict, doc: dict, code: str, lang: str):
    """sessions/index.json entry in the summit shape + the talk-only fields."""
    path = SESSIONS / "index.json"
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    status = json.loads((session / "status.json").read_text(encoding="utf-8"))
    entry = {
        "slug": session.name, "title": info["title"], "ok": True,
        "asr": {"language": lang},
        "meta": {"source": info["url"], "description": info.get("description", ""),
                 "track": info["channel"],
                 "tags": ",".join(f"Topic:{t}" for t in doc.get("topics") or [])},
        "code": code, "channel": info["channel"], "speakers": doc.get("speakers", ""),
        "added": datetime.now().strftime("%Y-%m-%d"), "minutes": info["minutes"],
        "video_url": info["url"], "video_id": info["id"],
        "frames": status.get("frames"),
    }
    entries = [e for e in entries if e.get("slug") != session.name] + [entry]
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")


def _publish():
    scripts = repo_root() / "scripts"
    subprocess.run([sys.executable, str(scripts / "build_library_manifest.py")], check=True)
    subprocess.run([sys.executable, str(scripts / "publish_library.py"), "--collection", "talks"], check=True)


# ── entry ───────────────────────────────────────────────────────────────────

def run_pipeline(args) -> int:
    print("=" * 60 + f"\n Library Agent  {datetime.now():%Y-%m-%d %H:%M}  lang={args.lang}\n" + "=" * 60)
    budget = Budget()
    state = _load_state()
    produced = 0
    try:
        for _ in range(args.max):
            budget.check("pick")
            info = _pick(state, args, budget)
            _save_state(state)
            if not info:
                print("  nothing to add today")
                break
            if args.dry_run:
                print(f"\n  would produce: {info['id']}  {info['title']}")
                break
            state["in_progress"] = info
            _save_state(state)
            session = SESSIONS / f"yt-{info['id']}"
            print(f"\n▶ {info['title']}  ({info['channel']}, {info['minutes']}m) → {session.name}")

            budget.check("prep")
            _prep(session, info, budget)
            budget.check("write")
            t = time.time()
            content = session / "content.json"
            doc = (json.loads(content.read_text(encoding="utf-8")) if content.exists()
                   else write_content(session, info, args.lang, _usage_log))
            budget.mark("write", t)
            budget.check("render")
            pdf = _render(session, args.lang, budget)
            _cleanup(session)

            code = f"TALK-{state['next_code']:03d}"
            _index(session, info, doc, code, args.lang)
            state["next_code"] += 1
            state["done"][info["id"]] = {"slug": session.name, "code": code,
                                         "date": datetime.now().strftime("%Y-%m-%d"), "title": info["title"][:80]}
            state.pop("in_progress", None)
            _save_state(state)
            produced += 1
            print(f"  ✓ {pdf.relative_to(repo_root())}")
            args.url = None  # a forced URL is one talk; further iterations rank
    except BudgetExceeded as e:
        # in_progress stays in state → next run resumes this talk, no discovery.
        print(f"\n⏱ stopped: {e} — resumable")

    if produced and not args.no_publish:
        _publish()

    if _usage_log:
        out_dir = AGENT / "output"
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"usage_{datetime.now():%H%M%S}.json").write_text(json.dumps({
            "agent": "library", "api": "Anthropic",
            "total_input_tokens": sum(u["input_tokens"] for u in _usage_log),
            "total_output_tokens": sum(u["output_tokens"] for u in _usage_log),
            "total_cost_usd": round(sum(u.get("cost_usd", 0) for u in _usage_log), 4),
            "calls": _usage_log, "stages_s": budget.marks}, indent=2), encoding="utf-8")
    print(f"\n Done: {produced} talk(s) · stages {budget.marks} · {time.time() - budget.t0:.0f}s total")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="discover + rank only, no download")
    ap.add_argument("--url", help="force this YouTube talk instead of ranking")
    ap.add_argument("--lang", choices=["he", "en"], default="he", help="document language")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--max", type=int, default=1, help="talks to add this run")
    args = ap.parse_args(argv)
    try:
        return run_pipeline(args)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 1
