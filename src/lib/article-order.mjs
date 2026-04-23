import { execSync } from 'node:child_process';

// Map article id → ordinal (1 = oldest publish, N = newest), using each
// file's first-add commit time as the publish moment. Date frontmatter is
// not granular enough — multiple articles often share a publish day, which
// makes a date-only sort unstable.
export function publishOrdinals(articles, projectRoot) {
  const firstAddTs = new Map();
  try {
    const out = execSync(
      "git log --diff-filter=A --name-only --pretty=format:%at --reverse -- 'articles/*/article.md'",
      { cwd: projectRoot, encoding: 'utf8' },
    );
    let currentTs = null;
    for (const line of out.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed) { currentTs = null; continue; }
      if (/^\d+$/.test(trimmed)) { currentTs = Number(trimmed); continue; }
      if (currentTs !== null && !firstAddTs.has(trimmed)) {
        firstAddTs.set(trimmed, currentTs);
      }
    }
  } catch {
    // Not a git checkout (e.g. tarball build). Fall back to date-only order.
  }

  const decorated = articles.map((a) => ({
    article: a,
    ts: firstAddTs.get(`articles/${a.id}/article.md`) ?? a.data.date.getTime() / 1000,
  }));
  decorated.sort((x, y) => x.ts - y.ts || x.article.id.localeCompare(y.article.id));
  return new Map(decorated.map((d, i) => [d.article.id, i + 1]));
}
