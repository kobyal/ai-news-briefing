#!/usr/bin/env python3
"""Generate NotebookLM video overviews for all docs/learn/ chapters.

For each chapter markdown file:
1. Create notebook
2. Add source
3. Wait for source processing
4. Generate video (with mind map for chapters 01, 02, 17, 21)
5. Wait for artifact completion
6. Download MP4 to docs/learn/_videos/<chapter>.mp4 (gitignored)
7. Capture share URL

Results JSON: docs/learn/_videos/results.json (committed; tracks URLs)

Usage:
  python3 scripts/generate_chapter_videos.py            # all chapters
  python3 scripts/generate_chapter_videos.py 05 06 07   # specific chapters by number prefix
  python3 scripts/generate_chapter_videos.py --resume   # skip chapters already in results.json

If a generate command fails (quota etc.), the script saves progress and exits
non-zero so the caller can re-run later.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEARN_DIR = ROOT / "docs" / "learn"
RESULTS_FILE = LEARN_DIR / "_videos" / "results.json"
VIDEO_DIR = LEARN_DIR / "_videos"

# Chapters that get an additional mind map artifact.
MIND_MAP_CHAPTERS = {"01", "02", "17", "21"}


_NETWORK_ERR_RE = re.compile(
    r"(nodename nor servname|Name or service|temporary failure in name resolution|"
    r"connection (?:reset|refused|aborted)|timed out|getaddrinfo|"
    r"ssl error|SSL_ERROR|networkidle|net::ERR|"
    # NotebookLM-specific server-side blips (RPC layer + 5xx + auth refresh)
    r"RPC \w+ failed|HTTP 5\d\d|status code 5\d\d|UNAVAILABLE|DEADLINE_EXCEEDED|"
    r"INTERNAL ERROR|service is currently unavailable|temporarily unavailable)",
    re.I,
)


def _run(cmd: list[str], *, timeout: int = 600, retries: int = 3) -> str:
    """Run notebooklm CLI, return stdout text. Raise on non-zero.

    Retries up to `retries` times on network errors with 10/30/90s backoff —
    a transient DNS blip should not propagate as a chapter failure.
    """
    print(f"  $ {' '.join(cmd)}")
    last_err = None
    for attempt in range(retries):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            return r.stdout
        err_text = (r.stderr.strip() or r.stdout.strip())[:500]
        last_err = err_text
        if _NETWORK_ERR_RE.search(err_text):
            backoff = (10, 30, 90)[min(attempt, 2)]
            print(f"    ⚠ network error (attempt {attempt+1}/{retries}); retrying in {backoff}s: {err_text[:100]}")
            time.sleep(backoff)
            continue
        # Non-network error — fail fast
        raise RuntimeError(f"command failed (rc={r.returncode}): {err_text}")
    raise RuntimeError(f"command failed after {retries} retries (last: {last_err})")


def _wait_for_artifact(notebook_id: str, artifact_id: str, *, timeout: int = 3600, interval: int = 30) -> None:
    """Poll artifact list manually until status is 'completed' or 'failed'.

    `notebooklm artifact wait` has been observed to hang even after the API
    returns status='completed'. This polling loop is more reliable.
    """
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        out = _run(
            ["notebooklm", "artifact", "list", "-n", notebook_id, "--json"],
            timeout=60,
        )
        try:
            data = json.loads(out[out.find("{"):]) if out.find("{") != -1 else {}
        except json.JSONDecodeError:
            data = {}
        artifacts = data.get("artifacts", []) if isinstance(data, dict) else data
        target = next((a for a in artifacts if a.get("id", "").startswith(artifact_id[:12])), None)
        status = (target or {}).get("status", "?")
        if status != last_status:
            print(f"    [wait] status={status}")
            last_status = status
        if status == "completed":
            return
        if status == "failed":
            raise RuntimeError(f"artifact {artifact_id} reported status=failed")
        time.sleep(interval)
    raise RuntimeError(f"artifact {artifact_id} did not complete within {timeout}s (last status={last_status})")


def _run_json(cmd: list[str], *, timeout: int = 600) -> dict:
    out = _run(cmd, timeout=timeout)
    # Find the first valid JSON object/array in the output
    start = -1
    for i, ch in enumerate(out):
        if ch in "{[":
            start = i
            break
    if start == -1:
        raise RuntimeError(f"no JSON in output:\n{out}")
    # Naive parse-from-start
    try:
        return json.loads(out[start:])
    except json.JSONDecodeError:
        # Try line-by-line
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("{") or line.startswith("["):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        raise


def _load_results() -> dict:
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text())
    return {}


def _save_results(results: dict) -> None:
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))


def _chapter_title(md_path: Path) -> str:
    """Extract human title from first # H1 in chapter file."""
    text = md_path.read_text()
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        return f"AI News Briefing — {m.group(1).strip()}"
    return f"AI News Briefing — {md_path.stem}"


def _video_instructions(md_path: Path) -> str:
    """Per-chapter instructions for the NotebookLM video host (Hebrew narration)."""
    return (
        "צור הסבר וידאו טכני בעברית למפתחי תוכנה ומהנדסים. "
        f"כסה את התוכן של '{md_path.name}' לעומק. "
        "הקהל כבר מכיר את הטרמינולוגיה הטכנית, "
        "אז דבר בעמקות ובמהות — הסבר מה כל דבר *הוא* ו*למה* הוא קיים, "
        "לא רק שהוא קיים. הזכר את שמות הקבצים והמיקומים בקוד שהמקור מציין, "
        "כדי שצופים יוכלו לנווט בקוד. "
        "שלב מונחים טכניים באנגלית כמקובל בעברית טכנית "
        "(למשל \"ה-Merger Agent\", \"agent\", \"pipeline\", \"prompt\"), "
        "אבל הסבר את המהות בעברית. "
        "הקלטת הוידאו צריכה להיות כולה בעברית."
    )


def process_chapter(md_path: Path, results: dict) -> None:
    chap_id = md_path.stem.split("-", 1)[0]  # "05" from "05-agent-adk.md"
    if chap_id in results and "video_url" in results[chap_id]:
        print(f"[{chap_id}] skip — already done ({results[chap_id]['video_url']})")
        return
    if chap_id in results and results[chap_id].get("skip"):
        print(f"[{chap_id}] skip — flagged skip ({results[chap_id].get('skip_reason', 'no reason')})")
        return

    title = _chapter_title(md_path)
    print(f"\n=== [{chap_id}] {title}")

    # Resume state: pick up partial progress if previous run failed mid-chapter.
    # Each step writes its IDs to results.json so re-runs don't duplicate notebooks.
    state = results.setdefault(chap_id, {})
    state["title"] = title

    try:
        # 1. Create notebook (skip if already created)
        if not state.get("notebook_id"):
            nb = _run_json(["notebooklm", "create", title, "--json"], timeout=60)["notebook"]
            state["notebook_id"] = nb["id"]
            _save_results(results)
        nb_id = state["notebook_id"]
        print(f"  notebook: {nb_id}")

        # 2. Add source (skip if already added)
        if not state.get("source_id"):
            src = _run_json(
                ["notebooklm", "source", "add", str(md_path), "--notebook", nb_id, "--json"],
                timeout=120,
            )["source"]
            state["source_id"] = src["id"]
            _save_results(results)
        src_id = state["source_id"]
        print(f"  source:   {src_id}")

        # 3. Wait for source
        _run(["notebooklm", "source", "wait", src_id, "-n", nb_id], timeout=300)
        print(f"  source ready")

        # 4. Generate video (skip if already submitted)
        if not state.get("video_task_id"):
            gen = _run_json(
                ["notebooklm", "generate", "video", "--notebook", nb_id, "--json", _video_instructions(md_path)],
                timeout=120,
            )
            state["video_task_id"] = gen["task_id"]
            _save_results(results)
        task_id = state["video_task_id"]
        print(f"  video task: {task_id}")

        # 5. Wait for video artifact (long-running — 20 min CLI cap, 30 min outer)
        _wait_for_artifact(nb_id, task_id, timeout=3600, interval=30)
        print(f"  video ready")

        # 6. Download MP4
        VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        out_path = VIDEO_DIR / f"{md_path.stem}.mp4"
        _run(
            ["notebooklm", "download", "video", str(out_path), "-n", nb_id, "-a", task_id],
            timeout=600,
        )
        size_mb = out_path.stat().st_size / 1024 / 1024 if out_path.exists() else 0
        print(f"  downloaded: {out_path.name} ({size_mb:.1f} MB)")

        result = {
            "title": title,
            "notebook_id": nb_id,
            "source_id": src_id,
            "video_task_id": task_id,
            "video_path": str(out_path.relative_to(ROOT)),
            "video_url": f"https://notebooklm.google.com/notebook/{nb_id}",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        # Save the success result FIRST — mind map is bonus, must not unmark video on failure
        results[chap_id] = result
        _save_results(results)
        print(f"  ✓ video saved to results.json")

        # 7. Mind map for selected chapters (synchronous response — no task_id)
        if chap_id in MIND_MAP_CHAPTERS:
            print(f"  + generating mind map for {chap_id}")
            try:
                mm = _run_json(
                    ["notebooklm", "generate", "mind-map", "--notebook", nb_id, "--json"],
                    timeout=300,
                )
                # Find the latest mind-map artifact and download it
                arts_out = _run(["notebooklm", "artifact", "list", "-n", nb_id, "--json"], timeout=60)
                arts_data = json.loads(arts_out[arts_out.find("{"):]) if arts_out.find("{") != -1 else {}
                arts = arts_data.get("artifacts", []) if isinstance(arts_data, dict) else arts_data
                mm_artifact = next(
                    (a for a in arts if a.get("type", "").lower() == "mind map" and a.get("status") == "completed"),
                    None,
                )
                if mm_artifact:
                    mm_path = VIDEO_DIR / f"{md_path.stem}-mindmap.json"
                    _run(
                        ["notebooklm", "download", "mind-map", str(mm_path), "-n", nb_id, "-a", mm_artifact["id"]],
                        timeout=300,
                    )
                    result["mind_map_artifact_id"] = mm_artifact["id"]
                    result["mind_map_path"] = str(mm_path.relative_to(ROOT))
                    _save_results(results)
                    print(f"  ✓ mind map downloaded: {mm_path.name}")
                else:
                    print(f"  ⚠ mind map generated but no completed artifact found")
            except Exception as e:
                print(f"  ⚠ mind map step failed (video kept): {e}")

    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        # Save partial progress
        results.setdefault(chap_id, {})["error"] = str(e)
        results[chap_id]["failed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _save_results(results)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("chapters", nargs="*", help="Chapter number prefixes (e.g. 05 06)")
    parser.add_argument("--resume", action="store_true", help="Skip chapters already in results.json")
    args = parser.parse_args()

    md_files = sorted(LEARN_DIR.glob("*.md"))
    md_files = [f for f in md_files if f.stem != "INDEX" and re.match(r"^\d+-", f.stem)]

    if args.chapters:
        wanted = set(args.chapters)
        md_files = [f for f in md_files if f.stem.split("-", 1)[0] in wanted]
        if not md_files:
            print(f"no chapters matched {wanted}")
            sys.exit(1)

    results = _load_results()

    failed = []
    for md in md_files:
        chap_id = md.stem.split("-", 1)[0]
        if args.resume and chap_id in results and "video_url" in results[chap_id]:
            print(f"[{chap_id}] skip (resume)")
            continue
        try:
            process_chapter(md, results)
        except Exception as e:
            failed.append(md.stem)
            # Skip-and-continue: a stalled chapter shouldn't kill the whole batch.
            # Auto-flag the chapter as skip so a later --resume run doesn't retry it.
            print(f"\n[{chap_id}] failed: {e}")
            print(f"[{chap_id}] auto-flagging skip; continuing with remaining chapters")
            results.setdefault(chap_id, {})["skip"] = True
            results[chap_id]["skip_reason"] = f"auto-skipped after failure: {str(e)[:200]}"
            _save_results(results)
            continue

    print(f"\nDone. {len(failed)} chapter(s) auto-skipped: {failed}")
    print(f"results in {RESULTS_FILE}")


if __name__ == "__main__":
    main()
