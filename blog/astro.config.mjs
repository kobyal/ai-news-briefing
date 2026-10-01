// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import expressiveCode from 'astro-expressive-code';
import sitemap from '@astrojs/sitemap';

// blog.aibriefing.dev — Hebrew-first, English mirror under /en/.
export default defineConfig({
  site: 'https://blog.aibriefing.dev',
  trailingSlash: 'always',
  build: { format: 'directory' },
  i18n: {
    defaultLocale: 'he',
    locales: ['he', 'en'],
    routing: { prefixDefaultLocale: false },
  },
  integrations: [expressiveCode({ themes: ['github-light'], styleOverrides: { borderRadius: '8px', borderColor: '#e4e4dc', codeFontFamily: "ui-monospace, 'SF Mono', Menlo, Consolas, monospace", codeFontSize: '13.5px', frames: { shadowColor: 'transparent', editorActiveTabIndicatorTopColor: '#4f46e5', editorTabBarBackground: '#f3f3ee', editorActiveTabBackground: '#fbfbf9', terminalBackground: '#12121c', terminalTitlebarBackground: '#1c1c2a' } }, defaultProps: { wrap: true } }), mdx(), sitemap({ i18n: { defaultLocale: 'he', locales: { he: 'he-IL', en: 'en-US' } } })],
});
