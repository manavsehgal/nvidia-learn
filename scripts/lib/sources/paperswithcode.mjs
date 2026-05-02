// Papers-with-Code public API — links arxiv papers to GitHub repos.
// API base: https://paperswithcode.com/api/v1/

/**
 * Look up the official + community repos linked to an arxiv paper.
 * Returns { repos: [{ url, stars, framework }], paper_url } or null on miss.
 */
export async function fetchPapersWithCodeRepos(arxivId) {
  // Step 1: papers?arxiv_id=...
  const lookupUrl = `https://paperswithcode.com/api/v1/papers/?arxiv_id=${encodeURIComponent(arxivId)}`;
  let res = await fetch(lookupUrl, { headers: { Accept: 'application/json', 'User-Agent': 'frontier-scout/0.1' } });
  if (!res.ok) return null;
  const data = await res.json();
  const paper = data?.results?.[0];
  if (!paper?.id) return null;

  // Step 2: papers/{id}/repositories/
  const reposUrl = `https://paperswithcode.com/api/v1/papers/${paper.id}/repositories/`;
  res = await fetch(reposUrl, { headers: { Accept: 'application/json', 'User-Agent': 'frontier-scout/0.1' } });
  if (!res.ok) return { paper_url: paper.url_abs || null, repos: [] };
  const reposData = await res.json();
  const repos = (reposData?.results || []).map((r) => ({
    url: r.url || null,
    stars: typeof r.stars === 'number' ? r.stars : 0,
    framework: r.framework || null,
    is_official: !!r.is_official,
  })).filter((r) => r.url);

  return { paper_url: paper.url_abs || null, repos };
}
