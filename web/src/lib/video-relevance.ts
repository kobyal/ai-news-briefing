// AI-relevance gate for video cards on /media/.
//
// The youtube agent stops non-AI videos being COLLECTED from 2026-08-05 forward,
// but archive day JSONs already contain them and /media/ pulls older days in via
// infinite scroll — so the page needs its own render-time filter or the junk
// lives forever. (A 3h46m Lex Fridman episode on the American Civil War was the
// #1 card in the AI video section; six iOS-27-beta videos were also in the pool.)
//
// Two-tier, mirroring _ALWAYS_AI_CHANNELS / _AI_KEYWORDS in the agent's
// pipeline.py: channels curated *because* they cover AI are trusted outright,
// and only broad-interest or untracked channels get keyword-checked. A pure
// keyword filter was too blunt — it dropped "Open-Weight Model Beats GLM 5.2"
// and the official "What's new at AWS" feed.

const AI_KEYWORDS =
  /\bAI\b|\bIA\b|artificial intelligence|\bLLM\b|\bGPT\b|Claude|Gemini|Grok|Qwen|DeepSeek|Kimi|Llama|Mistral|Fable|Astra|Amazon Q|machine learning|deep learning|neural net|transformer|Anthropic|OpenAI|DeepMind|\bAGI\b|chatbot|\bagent(ic|s)?\b|prompt engineer|fine.?tun|large language model|diffusion model|open.?(source|weight).{0,12}model|\bbenchmark\b|robotic|\bcopilot\b|\bcursor\b|\bcodex\b/i;

// Hebrew AI vocabulary — Hebrew titles rarely carry the English keywords.
const AI_KEYWORDS_HE =
  /בינה מלאכותית|סוכן|סוכנים|מודל|מודלים|למידת מכונה|רשת נוירונים|בינה|הנדסת פרומפט|צ׳אטבוט|צ'אטבוט/;

// Channels whose whole editorial identity is AI — anything they upload counts,
// including titles that name a model without saying "AI". Lowercased.
const ALWAYS_AI_CHANNELS = new Set([
  "ai explained", "matthew berman", "wes roth", "david shapiro",
  "prompt engineering", "worldofai", "the ai advantage", "matt wolfe",
  "yannic kilcher", "machine learning street talk", "all about ai",
  "cole medin", "sam witteveen", "ai jason", "indydevdan",
  "cognitive revolution podcast", "cognitive revolution",
  "two minute papers", "andrej karpathy",
  "openai", "google deepmind", "google cloud tech", "google for developers",
  "claude", "anthropic", "amazon web services", "aws events",
  "what's new at aws", "nvidia",
  "cloudai hebrew", "trashtech", "trashtech news", "yuv ai", "yuv-ai",
]);

// Curated but broad-interest: they cover AI often and other things just as
// often, so their uploads must earn their slot on the keyword check. These are
// exactly the channels that leaked the off-topic cards.
const BROAD_INTEREST_CHANNELS = new Set([
  "lex fridman", "networkchuck", "3blue1brown", "computerphile",
  "fireship", "theo - t3.gg", "greg isenberg",
]);

/**
 * True when a video plausibly concerns AI.
 *
 * Deliberately permissive — this drops obvious off-topic uploads, it does not
 * second-guess curation. Videos with no text at all pass, so missing metadata
 * never silently hides a card.
 */
export function isAiRelevantVideo(
  title: string,
  description = "",
  channel = "",
): boolean {
  const ch = channel.toLowerCase().trim();
  if (ch && ALWAYS_AI_CHANNELS.has(ch) && !BROAD_INTEREST_CHANNELS.has(ch)) {
    return true;
  }
  const text = `${title} ${description}`.trim();
  if (!text) return true;
  return AI_KEYWORDS.test(text) || AI_KEYWORDS_HE.test(text);
}
