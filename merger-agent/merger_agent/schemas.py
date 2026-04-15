"""Pydantic schemas for the Merger pipeline (same structure as source pipelines)."""
from typing import List
from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    vendor: str
    headline: str
    published_date: str
    summary: str
    detail: str = Field(
        ...,
        description="2-3 paragraphs of in-depth analysis with specific numbers, quotes, technical details, competitive context, and implications.",
    )
    urls: List[str]


class CommunityPulseItem(BaseModel):
    headline: str
    body: str
    heat: str  # "hot" | "warm" | "mild"
    date: str = ""  # e.g. "April 10, 2026"
    source_url: str
    source_label: str  # e.g. "r/LocalLLaMA", "@karpathy on X", "Hacker News"
    related_vendor: str = ""
    related_person: str = ""


class BriefingContent(BaseModel):
    tldr: List[str]
    news_items: List[NewsItem]
    community_pulse_items: List[CommunityPulseItem] = []
    community_pulse: str = ""       # backward compat: flat string
    community_urls: List[str] = []  # backward compat: flat URL list


class HebrewBriefing(BaseModel):
    tldr_he: List[str]
    headlines_he: List[str]
    summaries_he: List[str] = []
    details_he: List[str] = []
    community_pulse_he: str
