"use client";
import { createContext, useContext, useState, useEffect } from "react";

type Lang = "en" | "he";

interface LangCtx {
  lang: Lang;
  toggle: () => void;
  isHe: boolean;
}

const LangContext = createContext<LangCtx>({
  lang: "en",
  toggle: () => {},
  isHe: false,
});

export function LangProvider({ children, initialLang }: { children: React.ReactNode; initialLang?: Lang }) {
  const [lang, setLang] = useState<Lang>(initialLang ?? "en");

  useEffect(() => {
    // When the route forces a language (e.g. /he/* routes), trust the URL
    // over the saved preference so static HTML and hydration match the
    // language Google indexed for that URL.
    if (initialLang) return;
    const saved = localStorage.getItem("lang") as Lang;
    if (saved === "en" || saved === "he") setLang(saved);
  }, [initialLang]);

  const toggle = () =>
    setLang((l) => {
      const next = l === "en" ? "he" : "en";
      localStorage.setItem("lang", next);
      return next;
    });

  return (
    <LangContext.Provider value={{ lang, toggle, isHe: lang === "he" }}>
      <div
        dir={lang === "he" ? "rtl" : "ltr"}
        className={lang === "he" ? "font-hebrew" : ""}
      >
        {children}
      </div>
    </LangContext.Provider>
  );
}

export const useLang = () => useContext(LangContext);
