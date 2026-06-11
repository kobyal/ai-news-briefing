"""Shared Hebrew technical-translation glossary for the AI-news agents.

Single source of truth for how recurring AI-industry terms render in Hebrew,
per Koby's locked house style (reviewed term-by-term 2026-06-11). Imported by:
  - editorial-agent  → editorial_agent/prompts.py  (TRANSLATE_SYSTEM)
  - merger-agent      → merger_agent/prompts.py     (TRANSLATOR_PROMPT)
                        merger_agent/pipeline.py    (summary/detail translate calls)

Do NOT fork these rules into an agent's prompt — extend HE_TERM_GLOSSARY here so
every Hebrew translation path stays consistent. (See root CLAUDE.md: centralize.)
"""

# The locked term map. Framed English-term → Hebrew-rendering so it reads
# correctly when injected into either an English system prompt (editorial) or a
# Hebrew rewrite prompt (merger).
HE_TERM_GLOSSARY = """\
TECHNICAL HEBREW GLOSSARY — locked house style for AI-industry terms. Follow exactly:
- "AI lab" / "labs" → "חברות ה-AI" (plural) / "חברת AI" (singular). NEVER "מעבדה"/"מעבדות"/"מעבדת AI" — those read as a chemistry lab. Labs are companies; render them as חברות.
- "frontier lab(s)" → "חברות ה-AI המובילות". "frontier model(s)" → "המודלים המובילים". The adjective "frontier" → "מוביל/מובילה/מובילות". NEVER keep "frontier" in English, NEVER "מעבדות", NEVER "החזית".
- "weights" / "open weights" / "closed weights" → speak in terms of the MODEL, in Hebrew: "open weights" → "מודלים פתוחים"; "closed weights" → "מודלים סגורים"; "an open-weight model" → "מודל פתוח". NEVER "משקלים"/"משקולות" (gym weights) and do NOT keep the English word "weights" inline.
- "lock/close the weights" / "keep weights private" → "לשמור את המודל סגור" / "לא לשחרר את המודל". NEVER "לנעול את ה-weights".
- "the open-weight camp / ecosystem / movement" → "מחנה המודלים הפתוחים".
- "models slam shut" / "models go closed" / "the great closing" → "המודלים מסתגרים" / "המודלים נסגרים" / "ההסתגרות הגדולה". NEVER "המודלים ננעלים" (נעל = a door/car lock).
- "vendor lock-in" / "vendor-locked" → "תלות בספק" / "כבול לספק". Avoid נעל forms (נעילה/נעול) — they read as a physical lock in this house style.
- "stack" → keep English: "ה-stack שלך". NEVER "מחסנית" (that means a gun magazine).
- "builders" (the developer audience) → "מפתחים" / "בונים". NEVER "לבונים".
- "research collective" → "קבוצת מחקר" / "קהילת מחקר". NEVER "קולקטיב".
- "slam the brakes" / "hit the brakes" → translate the MEANING: "לבלום את הקצב" / "להאט". NEVER the literal pedal "דוושת בלם". "flooring the gas" → "דוחפות במלוא הכוח", not "דוושת הגז".
- "IPO" → "IPO" or "הנפקה"/"הנפקות". "IPO fever" → "קדחת ההנפקות".
- "the money opens up" / "capital floods in" → "הכסף זורם" / "ההון נשפך פנימה". Never "הכסף נפתח".
- "hardened against X" → "מחוזק מפני X" / "ערוך מפני X". Never the clinical "מחוסן בכוונה תחילה".
- "the hot-vendor index" / "who's hot" → "מי בולט השבוע" / "הספקים שבולטים". Avoid "ספקים חמים" (reads literal).
- "the pipeline is leaking" (talent/data) → "צינור ה[כישרון/נתונים] מאבד אחיזה" / "דליפה בצינור". Keep the metaphor only if it reads naturally in Hebrew.
- NEVER write "קומפיוט" — write "כוח מחשוב" or "מחשוב".

Keep in English inline (Israeli devs use the English word): company/product/model names (Claude, GPT, Gemini, Llama, …), agent, open-source, stack, benchmark, inference, token, prompt, deploy, fine-tune, alignment, sandbox, checkpoint, IPO, API, LLM, GPU, RAG, SDK, MoE, zero-day, cybersecurity/cyber."""
