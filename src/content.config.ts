import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// Articles live at ../articles/<slug>/article.md and are authored via the
// tech-writer skill. We keep that authoring workflow by loading articles
// from outside src/ with a glob loader, and collapse the id to the folder
// slug so URLs are /articles/<slug>/ rather than /articles/<slug>/article/.

export const STAGES = [
  'foundations',
  'training',
  'fine-tuning',
  'inference',
  'deployment',
  'agentic',
  'observability',
  'dev-tools',
] as const;

const articles = defineCollection({
  loader: glob({
    pattern: '*/article.md',
    base: './articles',
    generateId: ({ entry }) => entry.split('/')[0],
  }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    author: z.string().default('Manav Sehgal'),
    product: z.string(),
    stage: z.enum(STAGES),
    difficulty: z.enum(['beginner', 'intermediate', 'advanced']),
    time_required: z.string(),
    hardware: z.string().default('NVIDIA DGX Spark'),
    tags: z.array(z.string()),
    summary: z.string().max(300),
  }),
});

export const collections = { articles };
