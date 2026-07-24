# SoftRobotics Intelligence — Plan

A weekly research platform for **soft & humanoid robotics + materials**, built on Polymind's pipeline
architecture and re-targeted to the robotics domain from the *Soft & Humanoid Robotics Intelligence
Agent* setup guide.

## Architecture (shared with Polymind)

Ingest public sources → single-axis robotics keyword gate → LLM relevance/quality scoring → enrichment
→ local-embedding dedup (fastembed / ONNX; Voyage optional) against a 30-day memory → SQLite
archive → static GitHub Pages site (feed +
archive + weekly synthesis). Config-driven via `targeting.yaml`.

## Domain adaptations

- **Gate**: single-axis (`targeting.robotics_terms`) instead of Polymind's two-axis AI×materials gate —
  robotics is the domain anchor; `materials_boost_terms` raise the score for a materials-scientist
  audience; the LLM rubric (`prompts/relevance.md`) is the fine filter.
- **Themes** (8): Humanoid Robotics, Soft Robotics Research, Actuator Materials, Soft Skin & Tactile
  Sensing, Durability & Self-Healing, Fabrication & Manufacturing, HRI & Safety, Applications.
- **Sources**: arXiv (cs.RO, cond-mat.soft, eess.SY), OpenAlex, Crossref, robotics/materials journal
  RSS, university/lab press rooms, robotics trade media, and Google News topic + per-company queries
  (Optimus, Figure, Boston Dynamics, 1X, Agility, Apptronik, Unitree, Sanctuary, Physical
  Intelligence, Festo). See `targeting.yaml` for the full mapping.

## Two extra sections (weekly, LLM web search)

- **Material Requirements** — application → material class → property targets → open challenge.
  Stored in the `material_requirements` table and rendered on the site (`materials.html`).
- **Open Positions** — current materials-science / engineering roles at robotics companies. Written to
  a date-stamped Word doc (`output/SoftRobotics_Jobs_YYYY-MM-DD.docx`) and uploaded as a downloadable
  GitHub Actions artifact (`open-positions`) — never committed, never on the public site, so a public
  Pages deploy doesn't publish job listings.

Both run on the `--weekly-synthesis` path via the Anthropic `web_search` tool (`pipeline/sections.py`,
`prompts/material_requirements.md`, `prompts/jobs.md`); the jobs doc is built by `pipeline/jobs_doc.py`.

## Schedule

Weekly on Fridays 8:00 AM PDT (`cron: 0 15 * * 5`) via GitHub Actions → Pages.
