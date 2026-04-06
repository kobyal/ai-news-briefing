"""Pydantic schemas for the Merger pipeline (same structure as source pipelines)."""
from typing import List
from pydantic import BaseModel


class NewsItem(BaseModel):
    vendor: str
    headline: str
    published_date: str
    summary: str
    urls: List[str]


class BriefingContent(BaseModel):
    tldr: List[str]
    news_items: List[NewsItem]
    community_pulse: str
    community_urls: List[str] = []


class HebrewBriefing(BaseModel):
    tldr_he: List[str]
    community_pulse_he: str
