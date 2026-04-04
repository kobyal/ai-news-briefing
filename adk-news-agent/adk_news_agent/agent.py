"""AI Latest Briefing — 6-step SequentialAgent pipeline."""
import os
from datetime import datetime
from typing import List

from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import google_search
from pydantic import BaseModel

from .tools import build_and_save_html, resolve_source_urls
from .prompts import (
    VENDOR_RESEARCHER_PROMPT,
    URL_RESOLVER_PROMPT,
    COMMUNITY_RESEARCHER_PROMPT,
    BRIEFING_WRITER_PROMPT,
    TRANSLATOR_PROMPT,
    PUBLISHER_PROMPT,
)

MODEL = os.environ.get("GOOGLE_GENAI_MODEL", "gemini-2.5-flash")

# ---------------------------------------------------------------------------
# Pydantic output schema
# ---------------------------------------------------------------------------

class NewsItem(BaseModel):
    vendor: str
    headline: str
    published_date: str   # e.g. "March 22, 2026" or "2 days ago" — exact date from source
    summary: str
    urls: List[str]       # 2-3 source URLs per story

class BriefingContent(BaseModel):
    tldr: List[str]
    news_items: List[NewsItem]
    community_pulse: str
    community_urls: List[str] = []


class NewsItemHe(BaseModel):
    headline_he: str
    summary_he: str


class HebrewBriefing(BaseModel):
    tldr_he: List[str]
    news_items_he: List[NewsItemHe]
    community_pulse_he: str

# ---------------------------------------------------------------------------
# Pipeline date context — injected once at module load
# ---------------------------------------------------------------------------

_today = datetime.now().strftime("%B %d, %Y")
_month_year = datetime.now().strftime("%B %Y")
_lookback_days = int(os.environ.get("LOOKBACK_DAYS", "3"))


def _fmt(template: str) -> str:
    return (template
            .replace("{today}", _today)
            .replace("{month_year}", _month_year)
            .replace("{lookback_days}", str(_lookback_days)))


# ---------------------------------------------------------------------------
# Step 1 — VendorResearcher
# ---------------------------------------------------------------------------

VendorResearcher = LlmAgent(
    name="VendorResearcher",
    model=MODEL,
    tools=[google_search],
    output_key="raw_vendor_news",
    instruction=_fmt(VENDOR_RESEARCHER_PROMPT),
)

# ---------------------------------------------------------------------------
# Step 2 — URLResolver
# Resolves VendorResearcher's grounding redirect URLs IMMEDIATELY while fresh.
# Must use custom tool only — Gemini constraint: no mixing google_search + custom tools.
# ---------------------------------------------------------------------------

URLResolver = LlmAgent(
    name="URLResolver",
    model=MODEL,
    tools=[resolve_source_urls],
    output_key="resolved_sources",
    instruction=_fmt(URL_RESOLVER_PROMPT),
)

# ---------------------------------------------------------------------------
# Step 3 — CommunityResearcher
# ---------------------------------------------------------------------------

CommunityResearcher = LlmAgent(
    name="CommunityResearcher",
    model=MODEL,
    tools=[google_search],
    output_key="raw_community",
    instruction=_fmt(COMMUNITY_RESEARCHER_PROMPT),
)

# ---------------------------------------------------------------------------
# Step 4 — BriefingWriter
# ---------------------------------------------------------------------------

BriefingWriter = LlmAgent(
    name="BriefingWriter",
    model=MODEL,
    output_schema=BriefingContent,
    output_key="briefing",
    instruction=_fmt(BRIEFING_WRITER_PROMPT),
)

# ---------------------------------------------------------------------------
# Step 5 — Translator
# ---------------------------------------------------------------------------

Translator = LlmAgent(
    name="Translator",
    model=MODEL,
    output_schema=HebrewBriefing,
    output_key="briefing_he",
    instruction=_fmt(TRANSLATOR_PROMPT),
)

# ---------------------------------------------------------------------------
# Step 6 — Publisher
# ---------------------------------------------------------------------------

Publisher = LlmAgent(
    name="Publisher",
    model=MODEL,
    tools=[build_and_save_html],
    instruction=_fmt(PUBLISHER_PROMPT),
)

# ---------------------------------------------------------------------------
# Root agent — SequentialAgent
# ---------------------------------------------------------------------------

root_agent = SequentialAgent(
    name="AILatestBriefing",
    description=(
        "Researches the latest AI news from major vendors (Anthropic, AWS, "
        "OpenAI, Google, Azure), gathers community reactions, and produces a clean "
        "HTML latest briefing newsletter."
    ),
    sub_agents=[
        VendorResearcher,     # Step 1: google_search x5  → raw_vendor_news
        URLResolver,          # Step 2: resolve_source_urls (immediate) → resolved_sources
        CommunityResearcher,  # Step 3: google_search x2  → raw_community
        BriefingWriter,       # Step 4: BriefingContent schema → briefing
        Translator,           # Step 5: HebrewBriefing schema → briefing_he
        Publisher,            # Step 6: save HTML
    ],
)
