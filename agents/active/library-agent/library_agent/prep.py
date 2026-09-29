"""fetch → asr → slides for one session dir. Runs under the recording-to-review
skill venv (mlx-whisper/opencv live there, not in the repo venv), so it takes
its lib path from argv rather than importing anything from this repo.

Each stage skips itself when its output already exists, so a run cut short by
the time budget resumes where it stopped. Mirrors the skill's batch.one but
staged, and fetches at <=720p: slides are legible at that size and the download
is a fraction of the 1080p one.

    python prep.py <r2r_lib> <work> <url> --lang en
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument("lib"); ap.add_argument("work"); ap.add_argument("url")
ap.add_argument("--lang", default="en")
a = ap.parse_args()
sys.path.insert(0, a.lib)
import asr, slides  # noqa: E402

work = a.work
rec, wav = os.path.join(work, "rec.mp4"), os.path.join(work, "audio.wav")
blocks = os.path.join(work, "transcript_blocks.txt")
crop = os.path.join(work, "frames", "crop")
st_path = os.path.join(work, "status.json")
st = json.load(open(st_path)) if os.path.exists(st_path) else {"src": a.url}
need_video = not os.path.exists(blocks) or not glob.glob(os.path.join(crop, "*.jpg"))

if need_video and not os.path.exists(rec):
    t0 = time.time()
    # The default web client's media URLs 403 for the installed yt-dlp
    # (2026-09-28); web_embedded still serves 720p. Override via YT_CLIENT if
    # YouTube moves again — a yt-dlp upgrade is the real fix.
    client = os.environ.get("YT_CLIENT", "web_embedded")
    subprocess.run(["yt-dlp", "--no-update", "--extractor-args", f"youtube:player_client={client}",
                    "-f", "bv*[height<=720]+ba/b[height<=720]",
                    "--merge-output-format", "mp4", "-o", rec, a.url], check=True)
    st["fetched_s"] = round(time.time() - t0)

if not os.path.exists(blocks):
    if not os.path.exists(wav):
        asr.extract_audio(rec, wav)
    st["asr"] = asr.transcribe(wav, work, a.lang)

if not glob.glob(os.path.join(crop, "*.jpg")):
    raw = slides.detect(rec, os.path.join(work, "frames"))
    kept = slides.dedupe(raw, os.path.join(work, "frames"))
    slides.crop_all(kept, crop)
    slides.sheets(kept, os.path.join(work, "frames"), per=30)
    st["frames"] = {"raw": len(raw), "kept": len(kept)}

st["ok"] = True
json.dump(st, open(st_path, "w"), ensure_ascii=False, indent=2)
print(json.dumps({k: st.get(k) for k in ("fetched_s", "asr", "frames")}))
