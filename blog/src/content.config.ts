import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { glob } from 'astro/loaders';

// One folder per post key; `he.mdx` is canonical, `en.mdx` the mirror.
// The blog-agent writes these; a schema failure fails the build, not the site.
const posts = defineCollection({
  loader: glob({ pattern: '*/{he,en}.mdx', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    description: z.string().max(200),
    lang: z.enum(['he', 'en']),
    key: z.string(),                    // shared between he/en, = folder name = URL slug
    term: z.string(),                   // the English term this post explains
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    tags: z.array(z.string()).default([]),
    hero: z.string().optional(),        // /posts/<key>/hero.jpg
    diagram: z.string().optional(),     // /posts/<key>/diagram.svg
    video: z.string().optional(),       // /posts/<key>/video.mp4
    videoPoster: z.string().optional(),
    sources: z.array(z.object({ title: z.string(), url: z.string().url(), date: z.string().optional() })).min(1),
    opinion: z.string(),                // markdown, house voice
    madeWith: z.object({
      model: z.string(),
      sourceCount: z.number(),
      reviewedBy: z.string().default('Koby Almog'),
    }),
    draft: z.boolean().default(false),
  }),
});

export const collections = { posts };
