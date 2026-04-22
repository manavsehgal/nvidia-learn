import { defineConfig } from 'astro/config';

// nvidia-learn — Astro config
// Content sourced from ../articles/<slug>/article.md via content collection
// defined in src/content.config.ts. Shiki tuned to match the Field Notes palette.

// Production builds go to GitHub Pages at /manavsehgal.github.io/nvidia-learn/,
// so prod needs `base: '/nvidia-learn'`. In dev that prefix just makes the
// root URL 404, which is friction — so drop it unless NODE_ENV === 'production'.
const isProd = process.env.NODE_ENV === 'production';

export default defineConfig({
  site: 'https://manavsehgal.github.io',
  base: isProd ? '/nvidia-learn' : '/',
  trailingSlash: 'always',

  // Dev server binds to all interfaces so Firefox on the laptop/phone can
  // reach the Spark over the LAN or tailnet, not just loopback.
  server: {
    host: true,
    port: 4321,
  },

  markdown: {
    shikiConfig: {
      theme: 'vitesse-dark',
      wrap: true,
    },
  },

  build: {
    assets: 'assets',
  },
});
