"""Tests for _generate_per_story_audio in publish_data.py.

Run from repo root:  python3 scripts/test_per_story_audio.py
Exits non-zero if any assertion fails.

The test stubs out the actual edge-tts synth call (no network) — what it
verifies is the surrounding bookkeeping: which files get created, which
URL fields land on each item, idempotent re-runs, headline prefix.
"""
import hashlib
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Importing publish_data.py runs the whole module (it's a script, not a lib),
# so we vendor just the function under test by exec-ing it from source. This
# avoids triggering the file-glob / DeepL / OG-image work that runs at import.
import ast
import textwrap

src = (REPO / "publish_data.py").read_text(encoding="utf-8")
tree = ast.parse(src)
func_src_blocks = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in {
        "_generate_per_story_audio", "_generate_tldr_audio",
    }:
        func_src_blocks.append(ast.get_source_segment(src, node))
ns: dict = {"Path": Path}
exec("\n\n".join(func_src_blocks), ns)
_generate_per_story_audio = ns["_generate_per_story_audio"]


def _mock_story_id(item: dict) -> str:
    primary = (item.get("urls") or [item.get("headline", "")])[0]
    return hashlib.sha256(primary.encode()).hexdigest()[:12]


# ── Fixture ─────────────────────────────────────────────────────────────────
STORY = {
    "headline": "Anthropic ships Opus 5",
    "headline_he": "אנת'רופיק משחררת את Opus 5",
    "summary": "A new flagship model.",
    "summary_he": "מודל דגל חדש.",
    "detail": "More analysis here. Multiple paragraphs of context.",
    "detail_he": "ניתוח נרחב יותר. מספר פסקאות עם הקשר.",
    "urls": ["https://anthropic.com/news/opus-5"],
}
EXPECTED_SID = hashlib.sha256(b"https://anthropic.com/news/opus-5").hexdigest()[:12]


# ── Test 1: 4 MP3s generated, all 4 URL fields populated, headline prefixed ─
def test_full_generation():
    calls = []  # (text, voice, out_path) tuples observed by the synth_fn stub

    def fake_synth(text, voice, out_path):
        calls.append((text, voice, out_path))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"FAKE_MP3_BYTES")
        return True

    with tempfile.TemporaryDirectory() as td:
        audio_dir = Path(td) / "audio" / "2026-05-06"
        item = dict(STORY)
        stats = _generate_per_story_audio(
            [item], audio_dir, "2026-05-06",
            "en-US-GuyNeural", "he-IL-AvriNeural",
            "https://example.test", _mock_story_id, synth_fn=fake_synth,
        )

        # 4 calls, 4 URL fields, 4 files on disk
        assert stats == {"generated": 4, "skipped": 0, "failed": 0, "expected": 4}, stats
        assert len(calls) == 4, f"expected 4 synth calls, got {len(calls)}"

        for field in ("summary_audio_url", "summary_audio_url_he",
                      "detail_audio_url", "detail_audio_url_he"):
            assert field in item, f"item missing {field}"
            assert item[field].startswith("https://example.test/audio/2026-05-06/"), item[field]

        for fname in (f"story_{EXPECTED_SID}_summary_en.mp3",
                      f"story_{EXPECTED_SID}_summary_he.mp3",
                      f"story_{EXPECTED_SID}_detail_en.mp3",
                      f"story_{EXPECTED_SID}_detail_he.mp3"):
            assert (audio_dir / fname).exists(), f"missing {fname}"

        # Headline prefix is in the text passed to synth (4 calls, all should
        # start with the relevant headline, then ".\n\n", then the body).
        for text, voice, _ in calls:
            assert ".\n\n" in text, f"expected headline.\\n\\n body separator in: {text!r}"
            head, _, body = text.partition(".\n\n")
            assert head, "headline prefix missing"
            assert body, "body missing after headline"

        # EN calls use EN voice, HE calls use HE voice
        en_calls = [c for c in calls if c[1] == "en-US-GuyNeural"]
        he_calls = [c for c in calls if c[1] == "he-IL-AvriNeural"]
        assert len(en_calls) == 2 and len(he_calls) == 2, (en_calls, he_calls)
        assert any("Anthropic ships Opus 5" in c[0] for c in en_calls), "EN headline not in EN call text"
        assert any("אנת'רופיק" in c[0] for c in he_calls), "HE headline not in HE call text"
    print("PASS test_full_generation")


# ── Test 2: idempotent re-run skips existing MP3s, still stamps URLs ────────
def test_idempotent_rerun():
    call_count = {"n": 0}

    def fake_synth(text, voice, out_path):
        call_count["n"] += 1
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"FAKE_MP3_BYTES")
        return True

    with tempfile.TemporaryDirectory() as td:
        audio_dir = Path(td) / "audio" / "2026-05-06"
        item = dict(STORY)
        # First run: should generate 4
        s1 = _generate_per_story_audio(
            [item], audio_dir, "2026-05-06",
            "en", "he", "https://example.test", _mock_story_id, synth_fn=fake_synth,
        )
        assert s1["generated"] == 4, s1
        assert call_count["n"] == 4, call_count

        # Re-run on a fresh item dict (simulates next pipeline run with same story)
        item2 = dict(STORY)
        s2 = _generate_per_story_audio(
            [item2], audio_dir, "2026-05-06",
            "en", "he", "https://example.test", _mock_story_id, synth_fn=fake_synth,
        )
        assert s2 == {"generated": 0, "skipped": 4, "failed": 0, "expected": 4}, s2
        assert call_count["n"] == 4, "synth should not have been called again"

        # URL fields are stamped on item2 even though it didn't synth
        for field in ("summary_audio_url", "summary_audio_url_he",
                      "detail_audio_url", "detail_audio_url_he"):
            assert field in item2, f"re-run didn't stamp {field}"
    print("PASS test_idempotent_rerun")


# ── Test 3: empty body → no MP3 generated for that flavour, no URL field ────
def test_empty_body_skipped():
    calls = []

    def fake_synth(text, voice, out_path):
        calls.append((text, voice))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"FAKE")
        return True

    with tempfile.TemporaryDirectory() as td:
        audio_dir = Path(td) / "audio" / "2026-05-06"
        item = dict(STORY)
        item["detail"] = ""        # missing EN detail
        item["detail_he"] = ""     # missing HE detail
        stats = _generate_per_story_audio(
            [item], audio_dir, "2026-05-06",
            "en", "he", "https://example.test", _mock_story_id, synth_fn=fake_synth,
        )
        # Only summary EN + summary HE should generate (2 of 4)
        assert stats["generated"] == 2, stats
        assert "summary_audio_url" in item
        assert "summary_audio_url_he" in item
        assert "detail_audio_url" not in item, "should not stamp detail URL when body empty"
        assert "detail_audio_url_he" not in item
    print("PASS test_empty_body_skipped")


# ── Test 4: synth failure → no URL stamped, failed counter increments ───────
def test_synth_failure():
    def fake_synth_failing(text, voice, out_path):
        return False  # simulates edge-tts crash / no network

    with tempfile.TemporaryDirectory() as td:
        audio_dir = Path(td) / "audio" / "2026-05-06"
        item = dict(STORY)
        stats = _generate_per_story_audio(
            [item], audio_dir, "2026-05-06",
            "en", "he", "https://example.test", _mock_story_id, synth_fn=fake_synth_failing,
        )
        assert stats == {"generated": 0, "skipped": 0, "failed": 4, "expected": 4}, stats
        for field in ("summary_audio_url", "summary_audio_url_he",
                      "detail_audio_url", "detail_audio_url_he"):
            assert field not in item, f"should not stamp {field} on failure"
    print("PASS test_synth_failure")


# ── Test 5: HE headline falls back to EN when missing (still synthesises HE) ─
def test_he_headline_fallback():
    calls = []

    def fake_synth(text, voice, out_path):
        calls.append((text, voice))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"FAKE")
        return True

    with tempfile.TemporaryDirectory() as td:
        audio_dir = Path(td) / "audio" / "2026-05-06"
        item = dict(STORY)
        item["headline_he"] = ""  # no Hebrew headline
        # Body still in HE so we'd otherwise synthesise — must use EN headline as prefix
        stats = _generate_per_story_audio(
            [item], audio_dir, "2026-05-06",
            "en-US-GuyNeural", "he-IL-AvriNeural",
            "https://example.test", _mock_story_id, synth_fn=fake_synth,
        )
        assert stats["generated"] == 4, stats
        he_calls = [c for c in calls if c[1] == "he-IL-AvriNeural"]
        for text, _ in he_calls:
            assert "Anthropic ships Opus 5" in text, (
                f"HE call should fall back to EN headline as prefix, got: {text!r}"
            )
    print("PASS test_he_headline_fallback")


if __name__ == "__main__":
    test_full_generation()
    test_idempotent_rerun()
    test_empty_body_skipped()
    test_synth_failure()
    test_he_headline_fallback()
    print("\nAll 5 tests passed.")
