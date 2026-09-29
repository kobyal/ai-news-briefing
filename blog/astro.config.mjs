// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
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
  integrations: [mdx(), sitemap({ i18n: { defaultLocale: 'he', locales: { he: 'he-IL', en: 'en-US' } } })],
});
