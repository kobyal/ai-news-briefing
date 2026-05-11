export interface VendorMeta {
  label: string;
  color: string;
  bg: string;
  darkColor: string;
}

export const VENDORS: Record<string, VendorMeta> = {
  "Anthropic":    { label: "Anthropic",    color: "#7c3aed", bg: "#f3e8ff", darkColor: "#a855f7" },
  "AWS":          { label: "AWS",          color: "#ea580c", bg: "#fff7ed", darkColor: "#f97316" },
  "OpenAI":       { label: "OpenAI",       color: "#16a34a", bg: "#f0fdf4", darkColor: "#22c55e" },
  "Google":       { label: "Google",       color: "#2563eb", bg: "#eff6ff", darkColor: "#60a5fa" },
  "Azure":        { label: "Azure",        color: "#0078d4", bg: "#e8f4fd", darkColor: "#38bdf8" },
  "Meta":         { label: "Meta",         color: "#1877f2", bg: "#eff6ff", darkColor: "#60a5fa" },
  "xAI":          { label: "xAI",          color: "#111827", bg: "#f4f4f5", darkColor: "#d1d5db" },
  "NVIDIA":       { label: "NVIDIA",       color: "#76b900", bg: "#f7fce1", darkColor: "#84cc16" },
  "Mistral":      { label: "Mistral",      color: "#f97316", bg: "#fff7ed", darkColor: "#fb923c" },
  "Apple":        { label: "Apple",        color: "#555555", bg: "#f9fafb", darkColor: "#9ca3af" },
  "Hugging Face": { label: "Hugging Face", color: "#d97706", bg: "#fffbeb", darkColor: "#fbbf24" },
  "Alibaba":      { label: "Alibaba",      color: "#ff6a00", bg: "#fff4eb", darkColor: "#ff8533" },
  "DeepSeek":     { label: "DeepSeek",     color: "#0ea5e9", bg: "#e0f2fe", darkColor: "#38bdf8" },
  "Samsung":      { label: "Samsung",      color: "#1428a0", bg: "#eef2ff", darkColor: "#818cf8" },
  "Cohere":       { label: "Cohere",       color: "#39594d", bg: "#ecfdf5", darkColor: "#10b981" },
  "SpaceX":       { label: "SpaceX",       color: "#000000", bg: "#f4f4f5", darkColor: "#a1a1aa" },
  "Other":        { label: "Other",        color: "#6366f1", bg: "#eef2ff", darkColor: "#818cf8" },
};

export const VENDOR_LIST = [
  "Anthropic", "OpenAI", "Google", "AWS", "Azure", "Meta",
  "xAI", "NVIDIA", "Mistral", "Apple", "Hugging Face",
  "Alibaba", "DeepSeek", "Samsung", "Cohere", "SpaceX",
];

export function getVendor(name: string): VendorMeta {
  return VENDORS[name] || VENDORS["Other"];
}

/** Vendor → canonical domain for favicon lookup. Mirrors shared/image_fallback._VENDOR_DOMAIN
 *  so backend + frontend stay in sync on which homepage represents each vendor. */
export const VENDOR_DOMAIN: Record<string, string> = {
  "Anthropic":    "anthropic.com",
  "OpenAI":       "openai.com",
  "Google":       "google.com",
  "AWS":          "aws.amazon.com",
  "Azure":        "azure.microsoft.com",
  "Microsoft":    "microsoft.com",
  "Meta":         "ai.meta.com",
  "NVIDIA":       "nvidia.com",
  "xAI":          "x.ai",
  "Apple":        "apple.com",
  "Mistral":      "mistral.ai",
  "Hugging Face": "huggingface.co",
  "Alibaba":      "alibaba.com",
  "DeepSeek":     "deepseek.com",
  "Samsung":      "samsung.com",
  "Cohere":       "cohere.com",
  "SpaceX":       "spacex.com",
};

/** Returns a Google-favicon URL for the vendor at the requested size, or empty
 *  string if the vendor isn't in the canonical map. Frontend renders the
 *  result with onError fallback so a missing favicon never breaks layout. */
export function getVendorLogo(name: string, size = 32): string {
  const d = VENDOR_DOMAIN[name];
  if (!d) return "";
  return `https://www.google.com/s2/favicons?domain=${d}&sz=${size}`;
}
