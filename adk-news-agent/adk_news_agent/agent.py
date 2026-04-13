"""AI Latest Briefing — parallel research pipeline with timing callbacks."""
import os
import time
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import google_search
from google.genai import types
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
# Pydantic output schemas
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
    from shared.vendors import VENDOR_ENUM
    return (template
            .replace("{today}", _today)
            .replace("{month_year}", _month_year)
            .replace("{lookback_days}", str(_lookback_days))
            .replace("{VENDOR_ENUM}", VENDOR_ENUM))


# ---------------------------------------------------------------------------
# Callbacks — per-agent timing logs
# ---------------------------------------------------------------------------

def _make_callbacks(name: str):
    """Return (before, after) callbacks that log timing for a named agent."""
    def before(callback_context: CallbackContext) -> Optional[types.Content]:
        callback_context.state[f"_t_{name}"] = time.time()
        print(f"  ▶  {name}")
        return None

    def after(callback_context: CallbackContext) -> Optional[types.Content]:
        t0 = callback_context.state.get(f"_t_{name}")
        elapsed = f"{time.time() - t0:.1f}s" if t0 else "?"
        print(f"  ✓  {name:<22} {elapsed}")
        return None

    return before, after


# ---------------------------------------------------------------------------
# Step 1 — VendorResearcher
# ---------------------------------------------------------------------------

_vr_before, _vr_after = _make_callbacks("VendorResearcher")
VendorResearcher = LlmAgent(
    name="VendorResearcher",
    model=MODEL,
    tools=[google_search],
    output_key="raw_vendor_news",
    instruction=_fmt(VENDOR_RESEARCHER_PROMPT),
    before_agent_callback=_vr_before,
    after_agent_callback=_vr_after,
)

# ---------------------------------------------------------------------------
# Step 2 — URLResolver
# Resolves VendorResearcher's grounding redirect URLs IMMEDIATELY while fresh.
# Must use custom tool only — Gemini constraint: no mixing google_search + custom tools.
# ---------------------------------------------------------------------------

_ur_before, _ur_after = _make_callbacks("URLResolver")
URLResolver = LlmAgent(
    name="URLResolver",
    model=MODEL,
    tools=[resolve_source_urls],
    output_key="resolved_sources",
    instruction=_fmt(URL_RESOLVER_PROMPT),
    before_agent_callback=_ur_before,
    after_agent_callback=_ur_after,
)

# ---------------------------------------------------------------------------
# Step 3 — CommunityResearcher (runs in parallel with VendorResearcher+URLResolver)
# ---------------------------------------------------------------------------

_cr_before, _cr_after = _make_callbacks("CommunityResearcher")
CommunityResearcher = LlmAgent(
    name="CommunityResearcher",
    model=MODEL,
    tools=[google_search],
    output_key="raw_community",
    instruction=_fmt(COMMUNITY_RESEARCHER_PROMPT),
    before_agent_callback=_cr_before,
    after_agent_callback=_cr_after,
)

# ---------------------------------------------------------------------------
# Step 4 — BriefingWriter
# ---------------------------------------------------------------------------

_bw_before, _bw_after = _make_callbacks("BriefingWriter")
BriefingWriter = LlmAgent(
    name="BriefingWriter",
    model=MODEL,
    output_schema=BriefingContent,
    output_key="briefing",
    instruction=_fmt(BRIEFING_WRITER_PROMPT),
    before_agent_callback=_bw_before,
    after_agent_callback=_bw_after,
)

# ---------------------------------------------------------------------------
# Step 5 — Translator
# ---------------------------------------------------------------------------

_tr_before, _tr_after = _make_callbacks("Translator")
Translator = LlmAgent(
    name="Translator",
    model=MODEL,
    output_schema=HebrewBriefing,
    output_key="briefing_he",
    instruction=_fmt(TRANSLATOR_PROMPT),
    before_agent_callback=_tr_before,
    after_agent_callback=_tr_after,
)

# ---------------------------------------------------------------------------
# Step 6 — Publisher
# ---------------------------------------------------------------------------

_pb_before, _pb_after = _make_callbacks("Publisher")
Publisher = LlmAgent(
    name="Publisher",
    model=MODEL,
    tools=[build_and_save_html],
    instruction=_fmt(PUBLISHER_PROMPT),
    before_agent_callback=_pb_before,
    after_agent_callback=_pb_after,
)

# ---------------------------------------------------------------------------
# Research phase — VendorResearcher→URLResolver in parallel with CommunityResearcher
# Saves ~33% of total time since both branches are independent.
# ---------------------------------------------------------------------------

VendorPipeline = SequentialAgent(
    name="VendorPipeline",
    sub_agents=[VendorResearcher, URLResolver],
)

ResearchPhase = ParallelAgent(
    name="ResearchPhase",
    sub_agents=[VendorPipeline, CommunityResearcher],
)

# ---------------------------------------------------------------------------
# Root agent
# ---------------------------------------------------------------------------

root_agent = SequentialAgent(
    name="AILatestBriefing",
    description=(
        "Researches the latest AI news from major vendors (Anthropic, AWS, "
        "OpenAI, Google, Azure), gathers community reactions, and produces a clean "
        "HTML latest briefing newsletter."
    ),
    sub_agents=[
        ResearchPhase,    # Parallel: VendorResearcher+URLResolver || CommunityResearcher
        BriefingWriter,   # Step 4: BriefingContent schema → briefing
        Translator,       # Step 5: HebrewBriefing schema → briefing_he
        Publisher,        # Step 6: save HTML
    ],
)
