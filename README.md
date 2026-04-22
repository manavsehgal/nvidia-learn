# nvidia-learn

Personal learning portfolio: deep-dive essays on maximising the NVIDIA DGX Spark
as a personal AI power user and edge AI builder.

## Run locally

```bash
npm install        # one-time
npm run dev        # dev server: http://localhost:4321/
                   #              http://<spark-lan-ip>:4321/
npm run build      # static build to dist/ (uses /nvidia-learn/ base)
npm run preview    # preview the production build at http://localhost:4321/nvidia-learn/
```

The dev server binds to all interfaces (`server.host: true` in `astro.config.mjs`),
so you can open the site from Firefox on any device on the same LAN or tailnet —
not just on the Spark itself.

## Authoring articles

Articles live at `articles/<slug>/article.md`. Each article folder also holds
`screenshots/`, `transcript.md` (source provenance), and `assets/`.

The voice, structure, frontmatter schema, screenshot workflow, and privacy
scrub are all handled by the `tech-writer` Claude Code skill. Invoke it from
inside Claude Code to draft, polish, or publish an article.

## Design

The site uses a design system called "Field Notes" — parchment and oxblood
with Fraunces (display), Literata (body), and JetBrains Mono (code). See
`src/styles/global.css` for the tokens and component styles.
