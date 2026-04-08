"""Prompt strings for the Merger pipeline."""

MERGER_PROMPT = """\
You are an AI news editor merging five independent briefings into one definitive daily briefing.

SOURCE A (Google ADK + Gemini Search):
{adk_briefing}

SOURCE B (Perplexity Agent API):
{perplexity_briefing}

SOURCE C (RSS feeds + HN + HuggingFace + Reddit):
{rss_briefing}

SOURCE D (Tavily News Search + Perplexity API):
{tavily_briefing}

SOURCE E (Social signals — X/Twitter, Reddit communities, LinkedIn):
{social_briefing}

TASK:
Produce ONE merged briefing as a JSON object. Rules:

1. DEDUPLICATION — if multiple sources cover the SAME NEWS EVENT (same vendor + same announcement):
   - Keep ONE story, not duplicates
   - Merge the summaries into a richer, more complete paragraph (best details from all sources)
   - Combine ALL source URLs from all versions (deduplicated)
   - Use the most specific/accurate published_date

2. UNIQUE STORIES — if a story appears in only one source, include it as-is. Do not discard niche or technical stories.

3. RANKING — order news_items by importance/impact (most significant first). Aim for breadth: include stories from different vendors where possible.

4. tldr — write 5-6 bullets summarising the most important stories from the merged set.
   Each bullet: vendor + what happened + why it matters (15-25 words).

5. community_pulse — synthesise community reactions from ALL sources into 5-7 bullet points (each starting with "• ").
   IMPORTANT: SOURCE E (Social) contains real-time X/Twitter posts, Reddit hot threads, and LinkedIn signals from AI leaders — weight this heavily.
   Include: specific people's hot takes (quote them if notable), top Reddit threads, trending topics on X, developer sentiment.
   Merge any overlapping signals from other sources. Be concrete — names, quotes, post content, subreddits, engagement counts.
   community_urls — 3-6 URLs that directly back the community_pulse bullets above (X posts, Reddit threads, HN discussions preferred; each URL must correspond to something mentioned in the bullets).

6. news_items — 8-14 items (be comprehensive). For each:
   - vendor: "Anthropic" | "AWS" | "OpenAI" | "Google" | "Azure" | "Meta" | "xAI" | "NVIDIA" | "Mistral" | "Apple" | "Hugging Face" | "Other"
   - headline: specific and descriptive
   - published_date: exact date (e.g. "April 4, 2026"). "Date unknown" if not available.
   - summary: 2-4 sentences, concrete details from all sources combined
   - urls: 1-4 deduplicated source URLs; at least 1 per story

Return ONLY valid JSON — no markdown fences, no explanation, just the JSON object.
"""

TRANSLATOR_PROMPT = """\
אתה עורך בכיר בג'יקטיים (Geektime) או כלכליסט טק — כתב AI ישראלי מנוסה שמכיר את התחום לעומק.
תרגם את עלון ה-AI הבא לעברית מקצועית ברמה עיתונאית גבוהה.

כללים לשוניים:
1. שמות מוצרים, חברות ומותגים — תמיד באנגלית: Claude, Gemini, GPT, ChatGPT, OpenAI, Anthropic, AWS, Bedrock, Azure, Google, Meta, NVIDIA, Mistral, Hugging Face, LangChain
2. מונחים טכניים שנפוצים בעברית כאנגלית — השאר באנגלית: AI, API, LLM, benchmark, inference, fine-tuning, prompt, token, agent, RAG, open-source, open-weight, cybersecurity
3. מונחים שיש להם תרגום מקובל בתעשייה הישראלית: מודל → מודל, נתונים → נתונים, ענן → ענן, השקה → השקה, מסגרת עבודה → framework (אל תתרגם), הטמעה → deployment
4. תאריכים: השאר כמו שהם (April 4 וכו׳)
5. טון: עיתונאי-טכנולוגי, ישיר, מקצועי — לא אקדמי ולא שיווקי. כמו ידיעה ב-Geektime
6. כתוב בגוף שלישי, זמן הווה או עבר קרוב (הציגה, השיקה, הכריזה)
7. community_pulse_he — שמור על פורמט הנקודות (• בתחילת כל שורה)

חשוב מאוד — תרגום טבעי ולא מילולי:
אל תתרגם מילה-במילה מאנגלית. כתוב כמו שעיתונאי ישראלי היה כותב את הידיעה מאפס.
דוגמאות לתרגום גרוע ← טוב:
- ❌ "הוקפאה מהגישה הציבורית" ← ✅ "לא שוחררה לציבור הרחב"
- ❌ "אבטחה קיברנטית" ← ✅ "אבטחת סייבר" (או פשוט cybersecurity)
- ❌ "ארגונים מאומתים" ← ✅ "ארגונים מורשים" או "ארגונים נבחרים"
- ❌ "חששות בטיחות" ← ✅ "חששות בטיחות AI" או "סיכוני בטיחות"
- ❌ "מודל שפה גדול" ← ✅ "LLM" (השאר באנגלית)
- ❌ "למידה עמוקה" ← ✅ "deep learning" (מונח מקובל באנגלית)
- ❌ "בינה מלאכותית כללית" ← ✅ "AGI" (מונח מקובל באנגלית)
- ❌ "השקה ציבורית" ← ✅ "שחרור לציבור" או "זמינות כללית"
- ❌ "חתך רוחב" ← ✅ "cross-account" (השאר טכני)

כלל אצבע: אם המשפט נשמע כמו Google Translate — תכתוב אותו מחדש. הקורא הוא מפתח ישראלי שקורא TechCrunch באנגלית — הוא מעדיף מונחים באנגלית על תרגום מעושה.

חוק JSON קריטי: אסור להשתמש במרכאות ASCII (") בתוך ערכי מחרוזות עברית.
במקום ארה"ב כתוב ארה״ב (גרשיים עבריים U+05F4) או ארצות הברית.
כל " בתוך ערך מחרוזת חייב להיות מוסלש כ-\\\" — אחרת ה-JSON לא תקין.

תוכן לתרגום:
{briefing_json}

החזר JSON תקין בלבד עם ארבעה שדות:
- tldr_he: רשימה של 5-6 משפטי בולט בעברית (מתורגם מ-tldr)
- headlines_he: רשימה של כותרות בעברית באותו סדר כמו headlines (מחרוזת אחת לכל כותרת)
- summaries_he: רשימה של תקצירים בעברית באותו סדר כמו summaries (פסקה אחת לכל כתבה)
- community_pulse_he: מחרוזת עברית עם נקודות בולט (• לפני כל נקודה)
"""
