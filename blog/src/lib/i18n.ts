export type Lang = 'he' | 'en';

const STRINGS = {
  he: {
    blog: 'בלוג',
    dailyBriefing: 'הבריפינג היומי',
    about: 'אודות',
    heroTitle: 'המילים החדשות של הנדסת AI, בלי הבאזז.',
    heroLede: 'כל שבוע מונח אחד שכולם פתאום מדברים עליו: מאיפה הוא הגיע, מה הוא באמת אומר, איך משתמשים בו, ומה אנחנו חושבים עליו.',
    latest: 'הפוסטים האחרונים',
    readMore: 'לקריאה',
    opinionLabel: 'מה אנחנו חושבים',
    sourcesLabel: 'מקורות',
    watch: 'הסבר בוידאו',
    madeWith: 'איך נכתב הפוסט: נוסח על ידי הסוכן שלנו מתוך {n} מקורות, ונערך ואושר על ידי קובי אלמוג.',
    authorRole: 'מוביל טכנולוגי AI · ענן ו-DevOps · ישראל',
    footerLine: 'הבלוג של AI Briefing · פוסט בשבוע, לא יותר',
    minutes: 'דקות קריאה',
    notFound: 'הדף לא נמצא',
    backHome: 'חזרה לעמוד הראשי',
  },
  en: {
    blog: 'Blog',
    dailyBriefing: 'Daily briefing',
    about: 'About',
    heroTitle: 'The new words of AI engineering, minus the hype.',
    heroLede: 'One term a week that everyone suddenly uses: where it came from, what it actually means, how to use it, and what we think of it.',
    latest: 'Latest posts',
    readMore: 'Read',
    opinionLabel: 'What we think',
    sourcesLabel: 'Sources',
    watch: 'Video explainer',
    madeWith: 'How this was made: drafted by our agent from {n} sources, edited and approved by Koby Almog.',
    authorRole: 'AI tech lead · Cloud & DevOps · Israel',
    footerLine: 'The AI Briefing blog · one post a week, no more',
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
