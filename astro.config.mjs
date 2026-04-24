import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import rehypeCaption from './src/lib/rehype-caption.mjs';

// ai-field-notes — Astro config
// Content sourced from ../articles/<slug>/article.md via content collection
// defined in src/content.config.ts.

// Production builds go to GitHub Pages at https://manavsehgal.github.io/ai-field-notes/,
// so prod needs `base: '/ai-field-notes'`. In dev that prefix just makes the
// root URL 404, which is friction — so drop it unless NODE_ENV === 'production'.
const isProd = process.env.NODE_ENV === 'production';

export default defineConfig({
  site: 'https://manavsehgal.github.io',
  base: isProd ? '/ai-field-notes' : '/',
  trailingSlash: 'always',

  integrations: [mdx()],

  // Dev server binds to all interfaces so Firefox on the laptop/phone can
  // reach the Spark over the LAN or tailnet, not just loopback.
  server: {
    host: true,
    port: 4321,
  },

  markdown: {
    rehypePlugins: [rehypeCaption],
    shikiConfig: {
      theme: 'github-dark-dimmed',
      wrap: true,
    },
  },

  build: {
    assets: 'assets',
  },
});
