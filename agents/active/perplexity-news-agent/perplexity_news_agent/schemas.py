"""Pydantic output schemas for the Perplexity News Agent pipeline."""
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


class NewsItemHe(BaseModel):
    headline_he: str
    summary_he: str


class HebrewBriefing(BaseModel):
    tldr_he: List[str]
    news_items_he: List[NewsItemHe]
    community_pulse_he: str
