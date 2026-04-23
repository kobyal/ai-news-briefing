"""Real test: run yesterday's merger input through Gemini 2.5 Flash and compare to Anthropic Sonnet output.

Produces side-by-side headline diff + saves both outputs so you can read the summaries.

Not a complete merger replacement — just validates whether Gemini Flash produces
comparable JSON with the same input. Proof-of-concept for the shadow-eval plan.
"""
import json
import os
import time
from pathlib import Path

# Load local .env so GOOGLE_API_KEY is available when run standalone
env_path = Path(__file__).parent / "private" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# Reconstruct the merger input the same way merger-agent/pipeline.py does
import glob
DATE = "2026-04-22"
sources = {}

def load_briefing(pattern: str) -> dict:
    files = [f for f in sorted(glob.glob(pattern)) if os.path.basename(f) != "usage.json"]
    if not files:
        return {}
    with open(files[-1]) as f:
        d = json.load(f)
    return d.get("briefing", d)

sources["adk"]        = load_briefing(f"adk-news-agent/output/{DATE}/*.json")
sources["perplexity"] = load_briefing(f"perplexity-news-agent/output/{DATE}/*.json")
sources["rss"]        = load_briefing(f"rss-news-agent/output/{DATE}/*.json")
sources["tavily"]     = load_briefing(f"tavily-news-agent/output/{DATE}/*.json")
sources["exa"]        = load_briefing(f"exa-news-agent/output/{DATE}/*.json")

print("Input source counts:")
for k, v in sources.items():
    print(f"  {k:<12} {len(v.get('news_items', []))} items")

# Build a merger-style prompt (simplified — no social/community for the test)
prompt_parts = ["You are an AI news editor merging five independent briefings into one definitive daily briefing."]
for name, briefing in sources.items():
    items = briefing.get("news_items", [])
    if not items:
        continue
    prompt_parts.append(f"\n\nSOURCE ({name.upper()}):\n" + json.dumps(items, ensure_ascii=False, indent=2)[:8000])
prompt_parts.append("""

TASK: Produce ONE merged briefing as JSON. Deduplicate stories covering the same news event (merge summaries).
Rank by freshness and impact. Include 10-15 news_items. Each item:
{"vendor": "str", "headline": "str", "published_date": "str", "summary": "2-3 sentence str", "urls": [str]}

Return ONLY valid JSON with key "news_items": [...]. No markdown fences.""")
prompt = "\n".join(prompt_parts)
prompt_len = len(prompt)
print(f"\nPrompt built: {prompt_len:,} chars  (~{prompt_len//4:,} tokens)")

# ── Call Gemini 2.5 Flash via direct HTTPS (no SDK needed) ────────────
import urllib.request
google_key = os.environ.get("GOOGLE_API_KEY", "")
if not google_key:
    raise SystemExit("GOOGLE_API_KEY not set in private/.env")

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={google_key}"
body = json.dumps({
    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    "generationConfig": {
        "temperature": 0.3,
        "responseMimeType": "application/json",
        "maxOutputTokens": 32000,
        # Gemini 2.5 Flash splits output budget with internal "thinking".
        # For structured JSON we want all tokens in the response, not reasoning.
        "thinkingConfig": {"thinkingBudget": 0},
    },
}).encode()

t0 = time.time()
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
except Exception as e:
    raise SystemExit(f"Gemini call failed: {e}")
elapsed = time.time() - t0

text = ""
for cand in data.get("candidates", []):
    for part in cand.get("content", {}).get("parts", []):
        text += part.get("text", "")

usage = data.get("usageMetadata", {}) or {}
in_tok = usage.get("promptTokenCount", 0)
out_tok = usage.get("candidatesTokenCount", 0)
# Gemini 2.5 Flash: $0.15 in, $0.60 out per 1M
cost = (in_tok * 0.15 + out_tok * 0.60) / 1_000_000

print(f"\nGemini 2.5 Flash ran in {elapsed:.1f}s")
print(f"  tokens: {in_tok:,} in + {out_tok:,} out")
print(f"  cost:   ${cost:.4f}")

# Parse & save
out_dir = Path(f"shadow_eval/{DATE}")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "gemini_flash_output.json").write_text(text)
try:
    gemini_briefing = json.loads(text)
    gemini_items = gemini_briefing.get("news_items", [])
except Exception as e:
    print(f"  ⚠ could not parse Gemini JSON: {e}")
    gemini_items = []

# Compare to Sonnet (merger's actual output for that day)
sonnet_files = sorted(glob.glob(f"merger-agent/output/{DATE}/merged_*.json"))
sonnet_items = []
if sonnet_files:
    with open(sonnet_files[-1]) as f:
        sonnet_briefing = json.load(f).get("briefing", {})
    sonnet_items = sonnet_briefing.get("news_items", [])
    (out_dir / "sonnet_output.json").write_text(json.dumps({"news_items": sonnet_items}, indent=2, ensure_ascii=False))

print(f"\n{'='*80}")
print(f"HEADLINE COMPARISON ({DATE})")
print(f"  Sonnet 4 (actual merger):  {len(sonnet_items)} stories  · cost ~$0.67")
print(f"  Gemini 2.5 Flash (test):   {len(gemini_items)} stories  · cost ~${cost:.4f}")
print(f"{'='*80}\n")

for i in range(max(len(sonnet_items), len(gemini_items))):
    s = sonnet_items[i] if i < len(sonnet_items) else None
    g = gemini_items[i] if i < len(gemini_items) else None
    s_head = f"[{s.get('vendor','?')}] {s.get('headline','')[:55]}" if s else "—"
    g_head = f"[{g.get('vendor','?')}] {g.get('headline','')[:55]}" if g else "—"
    print(f"  {i+1:>2}. {s_head:<65} | {g_head}")

print(f"\nFull outputs saved to: {out_dir}/")
print(f"Cost ratio: Gemini Flash is {0.67/cost:.0f}× cheaper per merge for this input.")
