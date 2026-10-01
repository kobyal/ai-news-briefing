export type Lang = 'he' | 'en';

const STRINGS = {
  he: {
    blog: 'בלוג',
    dailyBriefing: 'הבריפינג היומי',
    about: 'אודות',
    heroTitle: 'מאחורי כל באזוורד יש מנגנון.',
    heroLede: 'המונחים שכולם זורקים בהנדסת AI, מפורקים לחלקים: מאיפה זה הגיע, מה זה עושה בפועל, ומה אנחנו חושבים אחרי שהרצנו את זה בעצמנו.',
    latest: 'החדש ביותר',
    series: 'סדרה',
    seriesAll: 'סדרות',
    partOf: 'חלק {n} מתוך {m}',
    prevPart: 'החלק הקודם',
    nextPart: 'החלק הבא',
    tldr: 'אמ;לק',
    contents: 'בפוסט הזה',
    figure: 'איור',
    more: 'עוד מונחים',
    allTerms: 'כל המונחים',
    readMore: 'לקריאה',
    opinionLabel: 'הדעה שלי, אחרי שהרצתי את זה',
    sourcesLabel: 'מקורות',
    watch: 'הסבר בוידאו',
    madeWith: 'איך נכתב הפוסט: נוסח על ידי הסוכן שלנו מתוך {n} מקורות, ונערך ואושר על ידי קובי אלמוג.',
    authorRole: 'מוביל טכנולוגי AI · ענן ו-DevOps · ישראל',
    footerLine: 'הבלוג של AI Briefing',
    minutes: 'דקות קריאה',
    notFound: 'הדף לא נמצא',
    backHome: 'חזרה לעמוד הראשי',
  },
  en: {
    blog: 'Blog',
    dailyBriefing: 'Daily briefing',
    about: 'About',
    heroTitle: 'Behind every buzzword there is a mechanism.',
    heroLede: 'The terms everyone throws around in AI engineering, taken apart: where it came from, what it actually does, and what we think after running it ourselves.',
    latest: 'Latest',
    series: 'Series',
    seriesAll: 'Series',
    partOf: 'Part {n} of {m}',
    prevPart: 'Previous part',
    nextPart: 'Next part',
    tldr: 'TL;DR',
    contents: 'In this post',
    figure: 'Fig.',
    more: 'More terms',
    allTerms: 'All terms',
    readMore: 'Read',
    opinionLabel: 'My take, after running it',
    sourcesLabel: 'Sources',
    watch: 'Video explainer',
    madeWith: 'How this was made: drafted by our agent from {n} sources, edited and approved by Koby Almog.',
    authorRole: 'AI tech lead · Cloud & DevOps · Israel',
    footerLine: 'The AI Briefing blog',
    minutes: 'min read',
    notFound: 'Page not found',
    backHome: 'Back to the front page',
  },
} as const;

export function t(lang: Lang) {
  return STRINGS[lang];
}

/** Same path in the other language: `/` ↔ `/en/`, `/x/` ↔ `/en/x/`. */
export function altLangHref(pathname: string, lang: Lang): string {
  if (lang === 'he') return '/en' + (pathname === '/' ? '/' : pathname);
  const stripped = pathname.replace(/^\/en\/?/, '/');
  return stripped || '/';
}

export function fmtDate(d: Date, lang: Lang): string {
  return d.toLocaleDateString(lang === 'he' ? 'he-IL' : 'en-US', { year: 'numeric', month: 'long', day: 'numeric' });
}

export function readingMinutes(text: string): number {
  return Math.max(1, Math.round(text.split(/\s+/).length / 200));
}

export const postHref = (lang: Lang, key: string) => (lang === 'he' ? `/${key}/` : `/en/${key}/`);
export const seriesHref = (lang: Lang, slug: string) => (lang === 'he' ? `/series/${slug}/` : `/en/series/${slug}/`);
