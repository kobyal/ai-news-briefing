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

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>("en");

  useEffect(() => {
    const saved = localStorage.getItem("lang") as Lang;
    if (saved === "en" || saved === "he") setLang(saved);
  }, []);

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
