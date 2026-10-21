# Research notebook and P-070 case study

Updated 21 October 2026. Content author: Nguyễn Trường Bảo; prepared with AI assistance from recorded Eviaura team evidence. No attack, model call or lab reset was run to prepare this release.

## Editorial and design decisions

- Audience: cybersecurity learners and engineers who want to assess a claim from its methods and evidence.
- Open each article with the result or problem. Explain the mechanism, alternatives and limitations before suggesting next steps.
- Use source dates, denominators and units. Keep retrieval, generation, delivery, observed attack success and UI tests separate.
- Attribute the overall project to the four-member Eviaura team. Describe Bảo's AI-SOC, Wazuh/target lab and Blue evidence work alongside the other contributions.
- Visual palette: paper `#f6f8f9`, ink `#192c35`, muted text `#55656d`, rules `#d7e0e3`, accent `#17656a`, figure wash `#eaf1f2`.
- Noto Serif is the reading/display face; Noto Sans provides Vietnamese interface text and chart labels. Article text stays within a constrained reading column.
- The featured note leads into a two-column article directory. Search is visible; advanced filters are optional. Mobile uses one column. The case study leads with the actual team demo, then evidence and contributions.
- Motion: one short desktop entrance and small user-triggered feedback. Honour reduced-motion preferences. Video is never autoplayed and uses `preload=none`.
- Add author attribution, English abstract, table of contents, reading progress and keyboard-accessible figure enlargement.

## Applied installed skills

Installed at user scope under `C:\Users\Admin\.codex\skills`:

1. [Sentry blog-writing-guide](https://github.com/getsentry/skills/tree/main/skills/blog-writing-guide): problem/result openings, precise technical claims, real author names, mechanisms, trade-offs and explicit limits. Its corporate voice is adapted to the owner's Vietnamese student research voice.
2. [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design): subject-specific hierarchy, intentional typography, restrained motion and screenshot review.
3. [Vercel web-design-guidelines](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines): labels, keyboard focus, image dimensions, reduced motion, media descriptions and responsive interaction checks.

## Updating the content

`content/research-notes.json` holds metadata for the three P-070 articles. Their bodies are in `seeds/posts/p070-*.md`. Run `python tools/publish_research_notes.py` in the configured CMS environment to create missing articles. Existing slugs are skipped deliberately so this command cannot overwrite live CMS edits.

After first publication, edit the live articles through the CMS. Updating the seed alone does not replace an existing published article.

The project is generated from `content/p070-ai-redteam-soc.html` and its complete Vietnamese source `content/p070-ai-redteam-soc.vi.html`. `source_vi` in `content/pages.json` selects the Vietnamese source. Run the usual build/check/package steps after editing.

Media and selected aggregate measurements are in `assets/p070/`. `sources.json` records original paths and SHA-256 hashes; `evaluation-summary.json` records the data used in the charts. The MP4 and its spoken content were reused from the repository, not recreated. The captions were converted from the team's SRT to WebVTT. The video's different recorded sessions must not be conflated with the 16 October nine-scenario evaluation.

No credentials, operational keys, raw incident traces or local SQLite databases belong in the public bundle.
