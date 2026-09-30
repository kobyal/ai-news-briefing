import React from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import '@fontsource/heebo/500.css';
import '@fontsource/heebo/800.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/700.css';
import '@fontsource/frank-ruhl-libre/700.css';
import '@fontsource/frank-ruhl-libre/800.css';

// Short looping GIFs embedded inline in posts (rendered with --codec=gif).
// Same brand tokens as the site. 1200×675 @ 15fps keeps a 5s loop under ~2MB.

const INK = '#12121c';
const MUTED = '#6d6d80';
const ACCENT = '#4f46e5';
const FONT = (lang: 'he' | 'en') => (lang === 'he' ? "'Heebo', 'Inter', system-ui, sans-serif" : "'Inter', system-ui, sans-serif");
const DISPLAY = "'Frank Ruhl Libre', Georgia, serif";

export type StepsProps = { lang: 'he' | 'en'; title: string; steps: string[]; loop?: boolean };
export type StatProps = { lang: 'he' | 'en'; value: string; label: string; source?: string };

export const STEPS_FPS = 15;
export const stepsDuration = (p: StepsProps) => STEPS_FPS * (1.2 + p.steps.length * 1.1 + 1.6);
export const statDuration = () => Math.round(STEPS_FPS * 4.5);

const Shell: React.FC<{ lang: 'he' | 'en'; children: React.ReactNode }> = ({ lang, children }) => (
  <AbsoluteFill
    style={{
      background: '#fbfbf9',
      color: INK,
      borderTop: `3px solid ${INK}`,
      fontFamily: FONT(lang),
      direction: lang === 'he' ? 'rtl' : 'ltr',
      padding: '64px 84px',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
    }}
  >
    <div style={{ position: 'absolute', insetInlineEnd: 72, bottom: 32, fontFamily: DISPLAY, fontSize: 18, fontWeight: 800, color: '#a0a0b2', direction: 'ltr' }}>
      blog.aibriefing.dev
    </div>
    {children}
  </AbsoluteFill>
);

export const Steps: React.FC<StepsProps> = ({ lang, title, steps }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  // Fade out at the end so the loop restarts cleanly.
  const tail = interpolate(frame, [durationInFrames - fps * 0.6, durationInFrames - 1], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return (
    <Shell lang={lang}>
      <div style={{ opacity: tail }}>
        <div style={{ fontFamily: DISPLAY, fontSize: 36, fontWeight: 700, color: INK, marginBottom: 30, lineHeight: 1.15 }}>{title}</div>
        {steps.map((s, i) => {
          const start = fps * (0.8 + i * 1.1);
          const p = spring({ frame: frame - start, fps, config: { damping: 200, stiffness: 140 } });
          const active = frame >= start && frame < start + fps * 1.1;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 22, marginBottom: 18, opacity: p, transform: `translateX(${(1 - p) * (lang === 'he' ? 30 : -30)}px)` }}>
              <div style={{
                width: 46, height: 46, borderRadius: 23, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: active ? INK : '#fbfbf9', border: `1.5px solid ${INK}`, color: active ? '#fbfbf9' : INK, fontFamily: DISPLAY, fontWeight: 700, fontSize: 22,
                transition: 'background 0.2s',
              }}>{i + 1}</div>
              <div style={{ fontSize: 36, fontWeight: 500, lineHeight: 1.25 }}>{s}</div>
            </div>
          );
        })}
      </div>
    </Shell>
  );
};

export const Stat: React.FC<StatProps> = ({ lang, value, label, source }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 18, stiffness: 90 } });
  const tail = interpolate(frame, [durationInFrames - fps * 0.6, durationInFrames - 1], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  // Count-up for a leading integer/percent, e.g. "88%" or "1,500"
  const m = value.match(/^(\D*)(\d[\d,]*)(.*)$/);
  let shown = value;
  if (m) {
    const target = parseInt(m[2].replace(/,/g, ''), 10);
    const cur = Math.round(interpolate(frame, [0, fps * 1.6], [0, target], { extrapolateRight: 'clamp' }));
    shown = `${m[1]}${cur.toLocaleString('en-US')}${m[3]}`;
  }
  return (
    <Shell lang={lang}>
      <div style={{ opacity: tail, textAlign: 'center' }}>
        <div style={{ fontFamily: DISPLAY, fontSize: 176, fontWeight: 800, color: ACCENT, letterSpacing: -5, lineHeight: 1, transform: `scale(${0.85 + p * 0.15})`, direction: 'ltr' }}>{shown}</div>
        <div style={{ fontSize: 40, fontWeight: 500, marginTop: 26, lineHeight: 1.3, opacity: interpolate(frame, [fps * 0.4, fps * 1.0], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) }}>{label}</div>
        {source && <div style={{ fontSize: 22, color: MUTED, marginTop: 18 }}>{source}</div>}
      </div>
    </Shell>
  );
};
