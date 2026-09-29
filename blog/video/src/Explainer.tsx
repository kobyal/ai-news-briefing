import React from 'react';
import { AbsoluteFill, Audio, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import '@fontsource/heebo/500.css';
import '@fontsource/heebo/800.css';
import '@fontsource/inter/500.css';
import '@fontsource/space-grotesk/700.css';
import type { ExplainerProps, Scene } from './props';

// Brand — same tokens as blog/src/styles/global.css.
const INK = '#0f0f1a';
const MUTED = '#3d3d5a';
const ACCENT = '#4f46e5';
const BG = '#f4f4f8';
const FONT_HE = "'Heebo', 'Inter', system-ui, sans-serif";
const FONT_EN = "'Inter', system-ui, sans-serif";
const DISPLAY = "'Space Grotesk', 'Heebo', sans-serif";

const Frame: React.FC<{ lang: 'he' | 'en'; children: React.ReactNode; dark?: boolean }> = ({ lang, children, dark }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fade = interpolate(frame, [0, fps * 0.4], [0, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill
      style={{
        background: dark ? INK : `linear-gradient(135deg, #ffffff 0%, ${BG} 55%, #eeedfb 100%)`,
        color: dark ? '#fff' : INK,
        fontFamily: lang === 'he' ? FONT_HE : FONT_EN,
        direction: lang === 'he' ? 'rtl' : 'ltr',
        padding: '110px 140px',
        opacity: fade,
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
      }}
    >
      <div style={{ position: 'absolute', insetInlineStart: 0, top: 0, bottom: 0, width: 18, background: ACCENT }} />
      <div style={{ position: 'absolute', insetInlineEnd: 120, top: 70, fontFamily: DISPLAY, fontSize: 30, fontWeight: 700, color: dark ? '#c7c6ff' : ACCENT, direction: 'ltr' }}>
        AI Briefing · Blog
      </div>
      {children}
    </AbsoluteFill>
  );
};

const Rise: React.FC<{ delay?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ delay = 0, children, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - delay, fps, config: { damping: 200, stiffness: 120 } });
  return <div style={{ transform: `translateY(${(1 - p) * 40}px)`, opacity: p, ...style }}>{children}</div>;
};

const SceneView: React.FC<{ scene: Scene; lang: 'he' | 'en' }> = ({ scene, lang }) => {
  switch (scene.type) {
    case 'title':
      return (
        <Frame lang={lang}>
          <div style={{ marginTop: 0 }}>
            <Rise><div style={{ fontFamily: DISPLAY, fontSize: 40, fontWeight: 700, color: ACCENT, letterSpacing: 4, textTransform: 'uppercase', direction: 'ltr', textAlign: lang === 'he' ? 'right' : 'left' }}>{scene.heading}</div></Rise>
            <Rise delay={8}><div style={{ fontSize: 96, fontWeight: 800, lineHeight: 1.1, marginTop: 24, letterSpacing: -2 }}>{scene.sub}</div></Rise>
          </div>
        </Frame>
      );
    case 'text':
      return (
        <Frame lang={lang}>
          <Rise><div style={{ fontSize: 34, fontWeight: 700, color: ACCENT, marginTop: 0 }}>{scene.heading}</div></Rise>
          <Rise delay={6}><div style={{ fontSize: 64, fontWeight: 500, lineHeight: 1.35, marginTop: 30, color: INK, maxWidth: 1500 }}>{scene.text}</div></Rise>
        </Frame>
      );
    case 'bullets':
      return (
        <Frame lang={lang}>
          <Rise><div style={{ fontSize: 34, fontWeight: 700, color: ACCENT, marginTop: 0 }}>{scene.heading}</div></Rise>
          <div style={{ marginTop: 30 }}>
            {scene.items.map((it, i) => (
              <Rise key={i} delay={8 + i * 10}>
                <div style={{ display: 'flex', gap: 28, alignItems: 'flex-start', fontSize: 54, lineHeight: 1.3, marginBottom: 28, maxWidth: 1550 }}>
                  <div style={{ width: 22, height: 22, borderRadius: 11, background: ACCENT, marginTop: 26, flexShrink: 0 }} />
                  <div>{it}</div>
                </div>
              </Rise>
            ))}
          </div>
        </Frame>
      );
    case 'image':
      return (
        <Frame lang={lang}>
          <Rise><div style={{ fontSize: 34, fontWeight: 700, color: ACCENT, marginTop: 0 }}>{scene.heading}</div></Rise>
          <Rise delay={6}>
            <div style={{ marginTop: 24, background: '#fff', borderRadius: 24, padding: 30, boxShadow: '0 8px 40px rgba(0,0,0,0.08)', width: 1640, height: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Img src={staticFile(scene.image)} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
            </div>
            {scene.caption && <div style={{ fontSize: 28, color: MUTED, marginTop: 16 }}>{scene.caption}</div>}
          </Rise>
        </Frame>
      );
    case 'quote':
      return (
        <Frame lang={lang} dark>
          <div style={{ marginTop: 0 }}>
            <Rise><div style={{ fontSize: 72, fontWeight: 700, lineHeight: 1.3, maxWidth: 1500, direction: /[֐-׿]/.test(scene.text) ? 'rtl' : 'ltr' }}>“{scene.text}”</div></Rise>
            <Rise delay={10}><div style={{ fontSize: 34, color: '#c7c6ff', marginTop: 40 }}>— {scene.who}</div></Rise>
          </div>
        </Frame>
      );
    case 'opinion':
      return (
        <Frame lang={lang}>
          <Rise><div style={{ fontSize: 30, fontWeight: 800, color: ACCENT, letterSpacing: 3, textTransform: 'uppercase', marginTop: 0 }}>{scene.heading}</div></Rise>
          <Rise delay={6}><div style={{ fontSize: 58, fontWeight: 500, lineHeight: 1.4, marginTop: 30, maxWidth: 1550 }}>{scene.text}</div></Rise>
        </Frame>
      );
    case 'outro':
      return (
        <Frame lang={lang} dark>
          <div style={{ marginTop: 0, textAlign: 'center' }}>
            <Rise><div style={{ fontSize: 60, fontWeight: 700 }}>{scene.text}</div></Rise>
            <Rise delay={8}><div style={{ fontFamily: DISPLAY, fontSize: 64, color: '#c7c6ff', marginTop: 30, direction: 'ltr' }}>{scene.url}</div></Rise>
          </div>
        </Frame>
      );
  }
};

export const Explainer: React.FC<ExplainerProps> = ({ lang, scenes }) => {
  const { fps } = useVideoConfig();
  let start = 0;
  return (
    <AbsoluteFill style={{ background: BG }}>
      {scenes.map((scene, i) => {
        const from = start;
        const dur = Math.max(1, Math.round(scene.durationSec * fps));
        start += dur;
        return (
          <Sequence key={i} from={from} durationInFrames={dur}>
            <SceneView scene={scene} lang={lang} />
            {scene.audio && <Audio src={staticFile(scene.audio)} />}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
