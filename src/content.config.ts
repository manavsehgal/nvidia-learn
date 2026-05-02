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

// Editorial series — the running narrative threads. An article belongs to
// at most one series. Preamble pieces outside the arc system leave it
// unset. Foundations covers F1–F7 and the bridge (B). The three application
// arcs follow the bridge; Looking Beyond Spark is the fourth, opportunistic
// thread for arithmetic that extrapolates beyond the 128 GB Spark envelope.
export const SERIES = [
  'Foundations',
  'Second Brain',
  'LLM Wiki',
  'Autoresearch',
  'Looking Beyond Spark',
  'Frontier Scout',
] as const;

// Slug-safe form for series, used in /series/<slug>/ URLs and the filter
// component. Mirror order with SERIES so chip rendering matches.
export const SERIES_SLUGS: Record<(typeof SERIES)[number], string> = {
  'Foundations': 'foundations',
  'Second Brain': 'second-brain',
  'LLM Wiki': 'llm-wiki',
  'Autoresearch': 'autoresearch',
  'Looking Beyond Spark': 'looking-beyond-spark',
  'Frontier Scout': 'frontier-scout',
};

export const SERIES_BY_SLUG: Record<string, (typeof SERIES)[number]> =
  Object.fromEntries(
    Object.entries(SERIES_SLUGS).map(([name, slug]) => [slug, name as (typeof SERIES)[number]]),
  );

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
    // Name (not path) of a signature figure component under
    // src/components/svg/. Rendered as the card's thumbnail on the home
    // and stage-filter pages. Optional — cards without one show no aside.
    signature: z.string().optional(),
    // Lifecycle. `published` = written and live. `upcoming` = placeholder
    // preview with an abstract; rendered dimmed with an "Upcoming" badge
    // and excluded from the home index (it still appears on its stage page
    // so readers see what is coming next).
    status: z.enum(['published', 'upcoming']).default('published'),
    // Articles frequently span more than one stage (e.g. a foundations
    // piece that also installs dev-tools). `stage` stays the primary
    // bucket; `also_stages` lists secondary buckets so the article shows
    // up on those stage pages too.
    also_stages: z.array(z.enum(STAGES)).default([]),
    // Editorial series — the running narrative thread the article belongs
    // to. Optional: preamble pieces outside the arc system leave it unset.
    series: z.enum(SERIES).optional(),
  }),
});

export const collections = { articles };
