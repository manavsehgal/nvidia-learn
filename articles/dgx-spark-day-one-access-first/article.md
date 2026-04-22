---
title: "Access First, Models Second — How I Set Up My DGX Spark for Solo AI Work"
date: 2026-04-21
author: Manav Sehgal
product: Foundation
stage: foundations
difficulty: intermediate
time_required: "~6 hours spread across a week"
hardware: "NVIDIA DGX Spark"
tags: [foundations, interaction-stack, remote-access, agentic, personal-ai, solo-builder]
summary: "Most DGX Spark walkthroughs open with CUDA and tokens/sec. This one opens with streaming, AI-pair-programming, sandboxed agents, and browser automation — the access layer. For a solo edge builder, that interaction stack is more load-bearing than the model stack."
---

<!-- Screenshots for this article are pending a future polish pass — Playwright-MCP
     was registered during the session that produced this draft but the tool
     schema wasn't yet loaded. See transcript.md for details. -->

The conventional DGX unboxing story is well-worn: plug in, install CUDA, run `nvidia-smi`, benchmark Llama, post a tokens-per-second chart. I skipped almost all of that in my first week with the Spark. Before I ran a single inference, I set up four things that have nothing to do with models: a remote-desktop streaming server, an AI-pair-programming CLI that lives on the machine itself, a sandboxed agent runtime, and a browser automation layer that the AI can drive. I built the **access layer** first.

The claim this article backs up: **for a solo edge builder working on one machine, the interaction stack is more load-bearing than the model stack.** Models are fungible — every six months there's a new state-of-the-art you swap in. How you reach the machine, how agents reach the world, and how what you learn becomes a public artifact — those decisions compound, and they're painful to change once laid down.

## Why this matters for a personal AI builder

An individual building with AI on their own hardware has a different bottleneck than a team on a cluster. It isn't GPU count. It isn't model choice. It's **attention, feedback loops, and publishing cadence**. You ship, or your rig becomes an expensive paperweight.

The interaction stack governs all three. It determines how many hours of your week you have to be physically at the machine. It determines how much of your work an agent can take off your plate. It determines whether every interesting session produces only a commit, or also a learning artifact that others can find, read, and cite.

The DGX Spark is uniquely well-suited to this posture because it's *one* machine you can treat as a personal cloud. You don't have the distributed-systems overhead of a cluster; you also don't have the constraints of a laptop. You have enough compute to run real workloads and enough continuity to build a rig that supports you.

## Where this sits in the stack

I'll use "access layer" throughout this piece. What I mean by it, in five roles:

```
                          ┌─ You ──────────────┐
                          │                    │
         Reach            │                    │
      (anywhere) ─────────┼───► Streaming      │  Sunshine + Moonlight
                          │                    │
         Collaborate      │                    │
      (with AI) ──────────┼───► AI pair on rig │  Claude Code (on the Spark)
                          │                    │
         Explore          │                    │
      (the web) ──────────┼───► Browser tools  │  Playwright-MCP
                          │                    │
         Automate         │                    │
      (safely) ───────────┼───► Sandboxes      │  NemoClaw / OpenClaw
                          │                    │
         Publish          │                    │
      (what you learn) ───┼───► Git + blog     │  nvidia-learn + tech-writer
                          │                    │
                          └────────────────────┘
```

Each role corresponds to a decision I made in the first days with the machine. Notably absent from this diagram: any NVIDIA model, inference server, or training framework. Those come next — and they drop into a rig that's ready to receive them.

## The journey

### Streaming: the rig is remote by design

The first thing I installed wasn't CUDA. It was [Sunshine](https://github.com/LizardByte/Sunshine), the open-source game-streaming server, paired with Moonlight clients on my laptop and phone.

SSH is the traditional remote for a Linux box. For AI work, SSH isn't enough. I need to see rendered browsers (NGC catalog, build.nvidia.com, dashboards), GUI tools that don't have a TTY mode, and — critically — a proper desktop where I can watch a long-running training job without tailing logs. Sunshine gives me that desktop with hardware-encoded video, at latency low enough to feel like a local session.

```bash
# Host: Sunshine runs as a user service on the Spark
systemctl --user is-active sunshine
# Client: Moonlight picks up the host on the LAN, or via a Tailscale IP
```

This decision sets an assumption the rest of the stack inherits: **I never need to be in the room with the machine.** The Spark lives in a corner. Nothing downstream requires me to walk over to it.

<!-- screenshot TODO: Sunshine web UI (https://localhost:47990) with the Apps tab visible -->

### Claude Code: the AI pair lives on the rig, not my laptop

The second install was Claude Code itself — on the Spark, not on the laptop I use to drive it. This is a choice worth thinking about. A lot of AI-coding workflows have the IDE and the AI living on the developer's client machine, talking to a remote runtime over SSH. I inverted that.

The agent runs where the files are. It owns the local disk, the `DISPLAY`, the Docker socket. When I ask it to "install Playwright-MCP and take a screenshot," it doesn't marshal commands over SSH and fight permission mismatches — it just does them, on the box, as itself. The latency between decision and action is zero hops.

```bash
# On the Spark
claude --version
# claude-code is installed as a user-level tool; sessions persist in
# ~/.claude/projects/<sanitized-cwd>/
```

The corollary of this choice: my laptop becomes a thin client. Browser for email, Moonlight for the rig, nothing heavy. The Spark is the workstation.

### Playwright-MCP: giving the AI a real browser

Most common agentic task in my workflow so far: "go look this up and bring me the relevant piece." Claude Code has `WebFetch` for URL content and `WebSearch` for queries — they're adequate for reading static pages. For anything dynamic — logged-in dashboards, JS-heavy SPAs, the NIM playground, the NGC catalog with its faceted filters — they fall short.

I registered [Playwright-MCP](https://github.com/microsoft/playwright-mcp) as a user-scope MCP server:

```bash
claude mcp add -e DISPLAY=:1 --scope user --transport stdio \
    playwright -- npx -y @playwright/mcp@latest
npx -y playwright@latest install chromium
```

After a session restart, Claude Code gets a set of `mcp__playwright__browser_*` tools: navigate, click, type, snapshot, screenshot. The AI can now *drive* a browser rather than just read it. The `DISPLAY=:1` env var means I can flip to headed mode and watch it work when I'm debugging.

The quiet part: this tool also produces the screenshots in my blog articles. When a writeup needs a shot of the NGC product page, the agent navigates there, takes the capture, crops it, and embeds it — without me switching windows.

<!-- screenshot TODO: output of `claude mcp list` showing the four connected servers
     including playwright ✓ Connected -->

### NemoClaw sandboxes: making agents safe to automate

The fourth install was NemoClaw — NVIDIA Nemotron-backed agent sandboxes running on `k3s` inside OpenShell containers. If you've never looked at this stack: think "isolated POSIX environments where an agent can freely `apt install`, `rm -rf`, `curl | sh`, and the worst-case blast radius is the sandbox itself."

NemoClaw sits between my files and whatever an agent wants to try next. Without it, I'd have to choose between (a) agents that are crippled because I won't give them shell, or (b) agents that can wreck my config. With it, the answer is: give the agent its own directory, its own user, its own cgroup budget. Let it go.

```bash
# Agents run in their own sandboxes, orchestrated via the nemoclaw CLI
nemoclaw onboard
# ...one-time setup, then agents can be spun up per-task
```

This is the piece that converts "I can imagine agents being useful here" into "agents do real work on this rig." The Nemotron backing matters because those models are tuned for the call-and-response agent rhythm — long horizons, tool use, recovering from their own errors.

<!-- [TODO: confirm with author — was NemoClaw set up on this specific Spark already?
     The nemoclaw-guru skill suggests yes, but the exact install sequence isn't
     in my session transcript.] -->

### Publishing as a foundation, not an afterthought

The last thing I set up in this first-week batch isn't a tool at all — it's a pipeline. A GitHub repository (`manavsehgal/nvidia-learn`) wired as the `origin` remote on a fresh folder, an `articles/` subfolder with Jekyll-ready frontmatter, and a `tech-writer` Claude Code skill that knows how to turn a session into an essay with embedded screenshots from Playwright-MCP.

```bash
git init
git remote add origin https://github.com/manavsehgal/nvidia-learn.git
git branch -m main
```

Most setup posts treat publishing as something you do *if you feel like it*. I want every serious session on this rig to produce a learning artifact — partly because that's the only way solo work compounds into a reputation, and partly because having to explain something publicly is the best forcing function for understanding it.

The `tech-writer` skill lives at `~/.claude/skills/tech-writer/`. It has an enforced editorial voice ("deep-dive essay, not cookbook"), a mandatory privacy scrub pass on every commit, and a shell script that blocks commits containing API keys, personal IPs, or other leakage patterns. The article you're reading was produced by it — first draft written by the skill, this polish by me.

## Verification — what "it's working" feels like on DGX Spark

The access layer is working when I do this, and it feels ordinary:

I'm at a café. I open Moonlight on my laptop, pick the Spark from the device list, and I'm looking at my desktop — same one I'd see standing next to the machine at home. I open Claude Code in the `nvidia-learn` directory. I say: "remember the NIM setup session from yesterday? Write it up as an article." The agent reads the session transcript, walks the NGC catalog via Playwright-MCP to grab fresh screenshots, drafts the piece with my voice, runs the scrub, commits it locally. I skim, make two edits, run `git push`. The article is public before my flat white is done.

I didn't touch a terminal as a terminal. I didn't type a `docker` command. I didn't think about SSH, port forwarding, or file transfer. The interaction stack carried the entire session.

When this feels ordinary, the foundation is working. If anything in that story feels awkward — if the agent can't browse authenticated pages, if the screenshots come out wrong, if the commit touches files it shouldn't — that's where the next polish pass goes.

## Tradeoffs and surprises

**Sunshine over Tailscale has rough edges.** LAN is smooth. Going over a mesh VPN introduces codec negotiation issues for some client/host pairs and occasionally a low-bitrate fallback that's useless for reading small UI text. <!-- [TODO: confirm with author — any specific Tailscale tuning you ended up doing?] -->

**Ubuntu 24.04 and cgroup v2 confuse older sandbox tooling.** NemoClaw handles this in its installer. If you tried to roll your own containerized agent stack from scratch on 24.04, you'd fight it — the OpenShell / k3s / cgroup v2 combination has edge cases that aren't well-documented yet. Let the tooling do the plumbing.

**Claude Code sessions are per-directory.** Context isn't shared across projects without explicit memory files. For cross-cutting blog writing that references work in several directories, this is mild friction — I ended up putting the editorial-direction memory in the project memory of the `nvidia-learn` cwd specifically so the `tech-writer` skill finds it consistently.

**Playwright-MCP's default profile doesn't persist logins.** If you want to routinely screenshot authenticated pages (your NGC dashboard, your build.nvidia.com account), you need to re-register the MCP server with `--user-data-dir=/home/nvidia/.cache/playwright-mcp-profile` so cookies survive. I didn't do this in the first pass and paid for it the first time I wanted an NGC API-keys-page shot.

**The access layer is not a one-afternoon project.** It took roughly six hours of focused work spread across a week. I'd budget a full weekend if you're doing this for the first time, with another evening for re-tuning each piece after it meets the others (the Sunshine/Tailscale combination especially benefits from a second pass).

## What this unlocks

With the access layer in place, here are three things I can do this week that I couldn't last week:

1. **Remote AI-driven benchmarks.** I can kick off a long-running training or inference benchmark before leaving the house, close the lid on my laptop, and check in on progress from any device running Moonlight. The agent monitors for me and pings when it's done or stuck.

2. **Daily agentic workflows with real side effects.** Agents on this rig can execute code, modify files, browse authenticated dashboards, and commit results — without me worrying they'll break my shell or leak credentials. "Let the agent do it" stops being hypothetical.

3. **Publishing as a continuous byproduct of learning.** Every evaluation session, every new model I try, every failed experiment turns into a committed article draft with roughly the same effort it'd take to write a few notes. The rig is a learning compounder, not just a runtime.

The next article in this series will be the first ML workload — likely a NIM deployment and what it tells me about on-device inference economics vs. the cloud API I used to pay for.

## Closing

Models are fungible. Six months from now, there will be a new state-of-the-art you swap in, and the year after that another one. The interaction stack is not fungible — changing how you reach your machine, how agents work alongside you, how safely you let them run, and how you turn your sessions into published artifacts is expensive and disruptive.

Getting it right on Day 1 means every subsequent decision about which model, which inference server, which fine-tuning library compounds against a stable base. The DGX Spark is the right hardware for this kind of solo-power-user posture — enough compute to be serious, enough continuity to be a partner — but the hardware is only half of it. The other half is the stack above, and that's what I wanted to get down while the choices were still fresh.

Next up: **the first real NIM inference on the Spark, and what the cold-start numbers tell me about replacing my API spend.**
