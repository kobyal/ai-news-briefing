import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import type { Lang } from './i18n';

export async function feed(lang: Lang, site: URL | undefined) {
  const posts = (await getCollection('posts', (p) => p.data.lang === lang && !p.data.draft))
    .sort((a, b) => b.data.pubDate.getTime() - a.data.pubDate.getTime());
  return rss({
    title: lang === 'he' ? 'AI Briefing — בלוג' : 'AI Briefing — Blog',
    description: lang === 'he' ? 'מונח אחד בשבוע מעולם הנדסת ה-AI, מוסבר בלי באזז.' : 'One AI-engineering term a week, explained without the hype.',
    site: site ?? 'https://blog.aibriefing.dev',
    items: posts.map((p) => ({
      title: p.data.title,
      pubDate: p.data.pubDate,
      description: p.data.description,
      link: lang === 'he' ? `/${p.data.key}/` : `/en/${p.data.key}/`,
      categories: [p.data.term, ...p.data.tags],
    })),
    customData: `<language>${lang === 'he' ? 'he-il' : 'en-us'}</language>`,
  });
}
