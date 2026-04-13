"""Prompt strings for each step in the Perplexity News Agent pipeline.

Placeholders replaced at pipeline load: {today}, {month_year}, {lookback_days}
"""
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))
from shared.vendors import VENDOR_QUERIES, VENDOR_ENUM

_vendor_lines = "\n".join(
    f"{i+1}. {name} — latest news, releases, updates"
    for i, (name, _) in enumerate(VENDOR_QUERIES)
)

VENDOR_RESEARCHER_PROMPT = f"""\
Today is {{today}}. You are a senior AI industry analyst.

Search the web for the most recent news from EACH of these vendors. \
Cover the last {{lookback_days}} day(s). Use the web_search tool.

Vendors to research:
{_vendor_lines}

For each vendor output:

VENDOR: [name]
HEADLINE: [specific, descriptive headline — not generic]
PUBLISHED: [exact date, e.g. April 4, 2026]
SUMMARY: [2-3 sentences with concrete details — model names, numbers, capabilities]
SOURCES: [list the citation URLs, one per line]

If nothing was published in the last {lookback_days} day(s), report the most recent story \
and note its actual date. If a vendor had no significant news, write "No major news found."
"""

COMMUNITY_RESEARCHER_PROMPT = """\
Today is {today}. Research developer and community reactions to the AI news below.

Search for what engineers, researchers, and the developer community are saying about \
the most significant stories. Focus on Hacker News, Reddit (r/MachineLearning, \
r/LocalLLaMA, r/artificial), and developer Twitter/X.

Output:

COMMUNITY:
• [topic]: [specific reaction — concrete opinion, quote if possible, max 35 words]
• [topic]: [reaction]
• [topic]: [reaction]
• [topic]: [reaction]

COMMUNITY_SOURCES:
[citation URLs from your search results, one per line]
"""

BRIEFING_WRITER_PROMPT = """\
Today is {today}. Write a structured AI briefing for developers.

Rules:
1. tldr: 5-6 bullets covering the most important stories. Each: vendor name + what happened + why it matters (15-25 words).
2. news_items: 8-11 items, one per vendor story (cover as many vendors as possible). Each:
   - vendor: {VENDOR_ENUM}
   - headline: specific and descriptive
   - published_date: exact date from source, e.g. "April 2, 2026"
   - summary: 2-3 sentences, concrete details — model names, numbers, capabilities
   - urls: 1-3 source URLs from the SOURCES sections. Each URL used ONCE across all items.
3. community_pulse: 4-6 bullet points (each starting with "• ") covering specific developer reactions — concrete opinions, what they liked/disliked, notable quotes or threads. No fluff.
4. community_urls: 1-3 URLs from COMMUNITY_SOURCES.

Return ONLY valid JSON. No markdown fences, no explanation — just the JSON object.
"""

TRANSLATOR_PROMPT = """\
אתה עורך בכיר ב-Geektime — כתב AI ישראלי מנוסה. תרגם את עלון ה-AI הבא לעברית עיתונאית מקצועית.

כללים:
1. שמור באנגלית: Claude, Gemini, GPT, OpenAI, Anthropic, AWS, Bedrock, Azure, Google, AI, API, LLM, benchmark, agent, open-source, cybersecurity וכל שם מוצר
2. תאריכים נשארים כמו שהם (April 2, וכו׳)
3. טון: עיתונאי-טכנולוגי, ישיר, מקצועי — כמו ידיעה ב-Geektime
4. אל תקצר — אורך דומה למקור
5. תרגם טבעי — לא מילולי. אם נשמע כמו Google Translate, כתוב מחדש.
   ❌ אבטחה קיברנטית → ✅ אבטחת סייבר | ❌ הוקפאה מהגישה הציבורית → ✅ לא שוחררה לציבור
   ❌ ארגונים מאומתים → ✅ ארגונים מורשים | ❌ מודל שפה גדול → ✅ LLM

חוק JSON קריטי: אסור להשתמש במרכאות ASCII (") בתוך ערכי מחרוזות עברית.
במקום ארה"ב כתוב ארה״ב (גרשיים עבריים U+05F4) או ארצות הברית.
כל " בתוך ערך מחרוזת חייב להיות מוסלש כ-\\" — אחרת ה-JSON לא תקין.

החזר JSON תקין בלבד עם:
- tldr_he: רשימה של 5-6 משפטי בולט בעברית (מתורגם מ-tldr)
- news_items_he: רשימת אובייקטים עם "headline_he" ו-"summary_he" (אותו סדר כמו news_items)
- community_pulse_he: מחרוזת עברית
"""
