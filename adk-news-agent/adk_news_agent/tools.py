"""Utility tools for the AI Latest Briefing pipeline.

(Per-agent HTML newsletter rendering used to live here too — removed on
2026-05-03. Nothing read those files; only the merger's HTML is consumed
downstream by send_email.py.)
"""
import ast
import concurrent.futures
import json
import os
import re
import urllib.request
from datetime import datetime
from typing import List


def resolve_source_urls(urls: List[str]) -> List[str]:
    """Follow redirects on each URL, validate they return 200, deduplicate, and filter junk.

    Called by URLResolver agent immediately after URLFinder while grounding redirects are fresh.
    Accepts either a clean list of URLs or a list with one text blob (LLM sometimes passes a
    single string containing multiple newline-separated URLs).
    Returns up to 30 clean, verified article URLs.
    """
    # If the LLM passes a single text blob, extract URLs from it
    if len(urls) == 1 and "\n" in urls[0]:
        urls = re.findall(r"https?://\S+", urls[0])
    # Strip stray markdown punctuation that sometimes gets appended
    urls = [re.sub(r"[)\]>\"',]+$", "", u) for u in urls if u.startswith("http")]

    def _resolve(url: str):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            r = urllib.request.urlopen(req, timeout=8)
            if r.status == 200:
                return r.url
            return None
        except Exception:
            return None

    print(f"URLResolver -- resolving {len(urls)} URLs...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        resolved = list(pool.map(_resolve, urls))
    print(f"URLResolver -- {sum(1 for r in resolved if r)} verified")

    seen: set = set()
    clean: List[str] = []
    for url in resolved:
        if url is None:
            continue
        if url in seen:
            continue
        if "vertexaisearch.cloud.google.com" in url:
            continue
        if re.match(r"https?://[^/]+/?$", url):
            continue
        seen.add(url)
        clean.append(url)
    return clean[:30]


def _parse(value):
    """Parse a value that may be a dict, JSON string, or Python repr string."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
        try:
            return ast.literal_eval(value)
        except Exception:
            pass
        # Fix 1: replace " between Hebrew characters (e.g. ארה"ב → ארה״ב)
        try:
            fixed = re.sub(r'([\u0590-\u05FF])"([\u0590-\u05FF])', r'\1\u05f4\2', value)
            return json.loads(fixed)
        except Exception:
            pass
        # Fix 2: escape any remaining unescaped " inside JSON string values
        try:
            fixed = re.sub(r'(?<=: ")(.+?)(?="(?:\s*[,}]))', lambda m: m.group(0).replace('"', '\\"'), value)
            return json.loads(fixed)
        except Exception:
            pass
    return {}  # Return empty dict gracefully rather than crashing


def build_and_save_html(topic: str = "AI", tool_context=None) -> dict:
    """Save the briefing as JSON for the merger pipeline.

    Reads briefing and briefing_he from session state to avoid LLM truncation
    when large JSON is passed as a tool argument. Deduplicates URLs across all
    news items, writes briefing_<HHMMSS>.json to today's output dir.

    (Function name kept for ADK tool registration. Per-agent HTML newsletter
    generation was removed on 2026-05-03 — nothing read it.)

    Args:
        topic: Topic label (kept for backwards compatibility; not used).

    Returns:
        {"saved_to": json_path, "json_saved_to": json_path, "success": True}
    """
    briefing_json = ""
    hebrew_json = ""
    if tool_context is not None:
        briefing_json = tool_context.state.get("briefing", "")
        hebrew_json = tool_context.state.get("briefing_he", "")
        print(f"Publisher -- read briefing from state ({len(str(briefing_json))} chars)")
    data = _parse(briefing_json)
    he = _parse(hebrew_json) if hebrew_json else {}

    news_items = data.get("news_items", [])

    # Deduplicate URLs globally — same URL appears at most once across the briefing
    global_seen: set = set()

    def _clean_urls(urls):
        result = []
        for u in (urls or []):
            if not u:
                continue
            if "vertexaisearch.cloud.google.com" in u:
                continue
            if re.match(r"https?://[^/]+/?$", u):
                continue
            if u in global_seen:
                continue
            global_seen.add(u)
            result.append(u)
        return result

    for item in news_items:
        item["urls"] = _clean_urls(item.get("urls") or [])
    print(f"Publisher -- saving JSON with {sum(len(i.get('urls', [])) for i in news_items)} unique source links")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(base_dir, "output", datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, f"briefing_{datetime.now().strftime('%H%M%S')}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"source": "adk", "briefing": data, "briefing_he": he}, f, ensure_ascii=False)
    print(f"Publisher -- saved to {json_path}")
    return {"saved_to": json_path, "json_saved_to": json_path, "success": True}
