# Source material: dgx-spark-day-one-access-first

Cleaned session log and provenance for this article. Drafted 2026-04-21 by the `tech-writer` skill from a Claude Code session. Source material includes what the session directly observed plus reasonable inferences from `~/.claude/settings.local.json` and installed skills (`nemoclaw-guru`). Gaps that require author confirmation are marked inline with `[TODO: confirm with author]` in article.md.

## Source streams

### Direct evidence from this session

- `git init` + `git remote add origin https://github.com/manavsehgal/nvidia-learn.git` in `/home/nvidia/nvidia-learn`, rename default branch to `main`.
- Registration of Playwright-MCP server:
  ```bash
  claude mcp add -e DISPLAY=:1 --scope user --transport stdio \
      playwright -- npx -y @playwright/mcp@latest
  ```
- One-time browser install: `npx -y playwright@latest install chromium` — downloaded Chromium 147 + headless-shell + ffmpeg to `~/.cache/ms-playwright/`.
- `claude mcp list` output confirming `playwright: npx -y @playwright/mcp@latest - ✓ Connected` alongside the three `claude.ai` Google MCP servers.
- Creation of the `tech-writer` user-scope skill at `~/.claude/skills/tech-writer/` with 10 files, including a mandatory privacy/security scrub pass and `scripts/verify_article.sh` secret-pattern scan.

### Inferred from system state

- **Sunshine / Moonlight streaming.** `~/.claude/settings.local.json` contains allow rules for `curl` to `raw.githubusercontent.com/moonlight-stream/*` and `raw.githubusercontent.com/LizardByte/Sunshine/*`, plus a specific `getcap /usr/bin/sunshine-2025.924.154138` command and a `systemctl --user is-enabled sunshine` probe — strong evidence Sunshine is installed and was tuned in an earlier session.
- **Tailscale.** Same settings file has allow rules for `Bash(tailscale status *)` and `Bash(tailscale version *)` — Tailscale is installed and has been inspected.
- **NemoClaw / OpenClaw.** A `nemoclaw-guru` skill is installed at `~/.claude/skills/nemoclaw-guru/` and its description references a DGX Spark + OpenShell sandbox setup — strong evidence NemoClaw was set up on this machine, though the exact commands weren't in this session's transcript.
- **DGX Spark hardware.** Confirmed via OS version (`Linux 6.17.0-1014-nvidia`), user `nvidia`, home path `/home/nvidia/nvidia-learn`.

### What I did NOT have direct access to

- Exact Sunshine configuration / tuning decisions.
- Whether Tailscale is used for streaming, only for admin, or both.
- The precise NemoClaw install sequence on this Spark (the `nemoclaw-guru` skill documents the general flow but not this specific session's outcomes).
- Any GUI setup from gdm3 (referenced in settings permissions) — probably related to auto-login for the Sunshine service.

## Editorial decisions

- **Angle chosen by author:** "Access first, models second" — the unusual ordering of foundation decisions, making the interaction layer the load-bearing story rather than CUDA/drivers/tokens-per-second.
- **Slug chosen by author:** `dgx-spark-day-one-access-first`.
- **Screenshot strategy:** deferred. Playwright-MCP was registered during this session but the tool schema wasn't yet loaded in the active Claude Code session, so no live captures were possible. HTML-comment `screenshot TODO` markers remain in article.md for a polish pass once the session restarts and the browser tools are available.
- **Ubuntu 24.04 / cgroup v2 note:** included as a tradeoff because `nemoclaw-guru`'s skill description calls out "cgroup v2 error on Ubuntu 24.04" as a known symptom. Author to confirm the framing matches their experience.

## Privacy / scrub notes

Nothing flagged during the authoring pass. Things that were deliberately kept out:

- Author email (known from session context) — used only in frontmatter `author` as `Manav Sehgal` display name; not included in body.
- Specific Tailscale IPs, node names, or ACL details — none were in the source material, none in the article.
- No commands with real API keys or tokens made it into the article.
- No full-desktop screenshots taken (none taken at all in this draft).

A final `scripts/verify_article.sh` pass must run before commit.

## Followups the author should check

1. Confirm or refine the NemoClaw paragraph — either replace the `[TODO: confirm with author]` HTML comment with specifics, or trim to a note and link to a future dedicated piece.
2. Confirm or drop the Tailscale-streaming rough-edges note — the article currently asserts this as tradeoff; if you didn't hit it specifically, soften to "possible rough edges".
3. Populate screenshots (all marked inline with `screenshot TODO` HTML comments) in a polish pass. Suggested captures:
   - Sunshine web UI (`https://localhost:47990`), Apps tab
   - `claude mcp list` output (as a code block, not a screenshot — per screenshot-workflows.md)
   - GitHub repo landing page `manavsehgal/nvidia-learn`
4. Verify the frontmatter `time_required` ("~6 hours spread across a week") matches your actual experience; adjust if off.
5. Run `scripts/verify_article.sh dgx-spark-day-one-access-first` before committing — will check frontmatter, image refs, secrets.
