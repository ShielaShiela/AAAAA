---
name: agentic-product-discovery-video
description: Runs a full cross-border e-commerce product discovery pipeline with six AI agents — market research, customer insight, product understanding, a structured product Digital Twin, and a product video package (theme, script, localization notes, plus a shot-by-shot spreadsheet with ChatGPT image prompts, Omni-style image-to-video prompts, voice-generation prompts, and dialogue/captions for external AI video tools) — with a Quality Review agent checking for unsourced or exaggerated claims. Use for "explore a cross-border e-commerce product opportunity", "research a product and generate content for it", "pre-launch product analysis", "product video script that isn't exaggerated", "build a product digital twin", "short-form video storyboard with AI generation prompts", or Agentic Product Discovery / AI product exploration / multi-agent product analysis. Even with just a product name or vague category idea, run the full pipeline rather than answering from general knowledge alone.
---

# Agentic AI Product Discovery & Video Generator

## What this does

A six-stage pipeline: **discover market opportunity → understand the product → build a Digital Twin → produce a product video → quality review**. Each stage is owned by one clearly-scoped agent, and every stage after the first three only reads the *structured* output of the previous stage — it never goes back to re-read the rawest research notes. This is deliberate: it keeps every claim traceable and auditable, so "AI product video" doesn't quietly become unsourced marketing fantasy.

**What this skill actually delivers**: a full text package (theme, outline, script, localization notes) *and* a shot-by-shot production spreadsheet — one row per scene, with an image-generation prompt (for ChatGPT/DALL-E), an image-to-video prompt (for an Omni-style image-to-video model), a voice-generation prompt, and the actual dialogue/captions. This is meant to be fed into external AI generation tools by the user to produce the real video; this skill does not call those tools itself. (An earlier version of this skill fully auto-assembled a video inside this environment using PIL slide cards + offline TTS + ffmpeg — that route is kept only as an explicit fallback, since testing showed the output quality — robotic voice, static visuals — wasn't good enough to be the default. See `agents/product-video.md` for when to use it instead.)

## Before starting: scope it (don't skip this)

Before running the six agents, confirm with the user (skip anything already clear from the conversation):
1. **Product**: a specific product name/link, or at minimum a clear category direction.
2. **Target markets**: which countries/regions? If unspecified, default to 2-3 representative markets and note in the report that this is a default assumption — don't let the market list balloon and dilute quality.
3. **Output depth**: full six-stage run (default), or only some stages (e.g. the user already has market research and wants to start from the Digital Twin).
4. **Video cut**: default to a short-form storyboard (~60-120 seconds, 6-12 scenes) unless the user specifies a different length/scene count. If multiple markets need their own localized cut, that means a separate set of storyboard rows (or a separate sheet) per market/language — don't silently produce only one language while implying full localization happened.

Don't over-ask with AskUserQuestion beyond these points — everything else can be handled by each agent's own judgment, with assumptions noted in its output.

## Execution flow

Create a working folder (e.g. `<product-slug>-analysis/`) and put every stage's output there. Use the Agent tool to call the six agents below, in sequence where noted and in parallel where noted. Each agent's full responsibilities and output format live in the corresponding file under `agents/` — **read that file before calling the agent, and put its entire content into the subagent's prompt**, since the subagent starts fresh and can't see this SKILL.md or the current conversation.

### Batch 1 (parallel): the research trio
Call these three subagents at the same time (multiple Agent calls in the same turn) — they don't depend on each other:

1. **Market Research Agent** — read `agents/market-research.md`; needs WebSearch/WebFetch for real verification. Output: `01_market_research.md`.
2. **Customer Insight Agent** — read `agents/customer-insight.md`. Output: `02_customer_insight.md`.
3. **Product Intelligence Agent** — read `agents/product-intelligence.md`; needs WebSearch/WebFetch. Output: `03_product_intelligence.md`.

Every one of these three prompts needs: the product info, the target market list, and the exact output file path. Wait for all three before moving on.

### Step 2: Digital Twin Agent
Read `agents/digital-twin.md` and `references/digital-twin-schema.md`, and put both into the subagent's prompt. This agent reads the three outputs above and merges them into `digital_twin.json` and `digital_twin.md`.

**After this step, skim `digital_twin.json` yourself.** Check for obviously empty fields or conflicts that weren't captured. If the merge quality is clearly off, fix it directly or ask the subagent to redo it rather than pushing a bad merge downstream.

### Step 3: Product Video Agent
Read `agents/product-video.md` and put the content plus the paths to `digital_twin.json`/`digital_twin.md` into the subagent's prompt. This agent will need to read the `xlsx` skill's SKILL.md to build the production spreadsheet correctly — make sure the subagent has access to the Skill tool (or Bash + openpyxl) to do so. Output lands in `05_video_package/`, including the production storyboard spreadsheet.

### Step 4: Quality Review Agent
Read `agents/quality-review.md` — this agent needs to read every prior stage's output (research notes, digital twin, the full video package including the storyboard spreadsheet's dialogue/caption columns) and audit it item by item. Output: `06_quality_review.md`.

**This is the quality gate — don't skip it**, even if the user seems to be in a hurry. If it surfaces a serious problem (a core selling point with no basis, an exaggerated claim in the actual video narration, a safety contradiction), proactively tell the user rather than quietly letting it through.

## Wrap-up
1. Write `00_summary.md` at the top of the working folder: 2-3 short paragraphs on whether the product is worth pursuing, the strongest selling point, where the video package is, and whether Quality Review flagged anything needing human sign-off. This is the first thing the user should see.
2. Deliver with SendUserFile: `00_summary.md`, `digital_twin.md`, everything in `05_video_package/` (including the storyboard spreadsheet), and `06_quality_review.md`. The raw research notes (01-03) can stay in the working folder without being sent proactively, unless the user wants to see the underlying evidence.

## Design principles (for you, not for the user-facing output)

- **Traceability beats polish.** Every claim should be traceable to evidence. If there's no evidence, say so honestly — don't fabricate numbers or sources to make the report look complete.
- **Later stages don't redo earlier stages' work.** The Digital Twin Agent doesn't re-research the market; the Product Video Agent doesn't re-analyze customer segments. This division of labor keeps the pipeline efficient and keeps each stage's output independently reviewable.
- **Honest limitations matter more than inflated selling points.** The Product Intelligence and Quality Review agents exist specifically to counter the tendency of AI-generated content to over-flatter a product. Don't soften this just because the user might want to hear the product is flawless.
- **Be precise about what "video" means here.** The default deliverable is a *production spreadsheet* — real, usable prompts for external image/video/voice generation tools — not a finished video file. Don't imply a finished MP4 exists unless the legacy ffmpeg fallback was explicitly used (and even then, be upfront that it's a robotic-voice slideshow, not AI-generated live-action).
- **This is a script for a human team or downstream tool to pick up, not final ad copy.** Storyboards and narration should be concrete enough that anyone could execute them, but assume someone still reviews before publishing — the Quality Review report's "needs human confirmation" list is written for that person.
