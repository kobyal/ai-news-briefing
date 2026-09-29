import type { APIContext } from 'astro';
import { feed } from '../../lib/rss';
export function GET(ctx: APIContext) { return feed('en', ctx.site); }
