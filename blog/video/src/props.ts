// Contract between agents/active/blog-agent/blog_agent/media.py and the video.
export type Scene =
  | { type: 'title'; heading: string; sub: string; audio?: string; durationSec: number }
  | { type: 'text'; heading: string; text: string; audio?: string; durationSec: number }
  | { type: 'bullets'; heading: string; items: string[]; audio?: string; durationSec: number }
  | { type: 'image'; heading: string; image: string; caption?: string; audio?: string; durationSec: number }
  | { type: 'quote'; text: string; who: string; audio?: string; durationSec: number }
  | { type: 'opinion'; heading: string; text: string; audio?: string; durationSec: number }
  | { type: 'outro'; text: string; url: string; audio?: string; durationSec: number };

export type ExplainerProps = {
  lang: 'he' | 'en';
  term: string;
  scenes: Scene[];
};

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

export const defaultProps: ExplainerProps = {
  lang: 'he',
  term: 'loop engineering',
  scenes: [
    { type: 'title', heading: 'Loop engineering', sub: 'מה זה, ולמה כולם מדברים על זה', durationSec: 4 },
    { type: 'text', heading: 'ההגדרה', text: 'לבנות את העבודה של הסוכן כמחזור: להריץ, לבדוק, לתקן, שוב.', durationSec: 5 },
    { type: 'bullets', heading: 'איך משתמשים', items: ['בדיקה אוטומטית אחרי כל צעד', 'תקציב ניסיונות', 'עצירה ברורה'], durationSec: 6 },
    { type: 'quote', text: 'Verification beats generation.', who: 'AI Briefing', durationSec: 4 },
    { type: 'opinion', heading: 'מה אנחנו חושבים', text: 'שם חדש לדיסציפלינה ישנה. וזה בסדר.', durationSec: 5 },
    { type: 'outro', text: 'הפוסט המלא בבלוג', url: 'blog.aibriefing.dev', durationSec: 4 },
  ],
};
