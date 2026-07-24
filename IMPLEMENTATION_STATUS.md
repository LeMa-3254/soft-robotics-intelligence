# SoftRobotics Intelligence — Implementation Status

## Current Status

Bootstrapped from the Polymind pipeline and re-targeted to soft & humanoid robotics. The scaffold is in
place and runs offline end to end (keyword bootstrap scoring, static site build). Live model runs
(Anthropic scoring/enrichment/synthesis + web-search sections; dedup uses local embeddings by default)
need API credentials and a
first GitHub Actions run.

## Completed

- Copied the Polymind architecture (pipeline/sources/store/site/prompts/tests) and stripped instance
  state (git, venv, db, caches).
- Re-targeted `targeting.yaml`: robotics site identity, single-axis `robotics_terms` gate,
  `materials_boost_terms`, conservative excludes, 8-theme taxonomy, and all sources named in the setup
  guide (arXiv/OpenAlex/Crossref, journal RSS, university/lab news, robotics trade media, Google News
  topic + per-company queries).
- Switched the keyword gate (`sources/base.py vocabulary_match`) to single-axis robotics; updated the
  bootstrap boost-term key and `infer_theme` for the robotics themes.
- Rewrote `prompts/relevance.md`, `enrich.md`, `synth.md` for the robotics/materials domain.
- Added the two extra sections: `pipeline/sections.py`, `prompts/material_requirements.md`,
  `prompts/jobs.md`, and the `AnthropicModelClient.search_json` web-search method.
  - **Material Requirements**: stored in the `material_requirements` table and rendered on the site
    (`materials.html`).
  - **Open Positions**: written to a date-stamped Word doc in `output/` (`pipeline/jobs_doc.py`,
    `python-docx`) and uploaded as a downloadable GitHub Actions artifact (`open-positions`) — never
    committed (gitignored), never on the public site.
- Restyled the site (emerald accent, robotics copy, Materials nav).
- Made dedup embeddings default to a local fastembed / ONNX model (`build_embedding_client` +
  `resolve_embedding_provider`) so only the Anthropic key is required; Voyage remains an opt-in provider.
- Set the GitHub Actions schedule to Fridays 8:00 AM PDT (`0 15 * * 5`).
- Updated project metadata (name/description, `anthropic>=0.52.0` for web search).

## Remaining

- Create/push the GitHub repo (`LeMa-3254/soft-robotics-agent`), make it public, enable Pages from
  Actions, add the `ANTHROPIC_API_KEY` secret (only key required; `VOYAGE_API_KEY` optional, for the
  Voyage dedup path only).
- First live run: verify feed URLs marked `# verify` in `targeting.yaml`, prune any that 404/403, and
  confirm the Material Requirements + Job Openings sections populate.
- Tune scoring thresholds and the robotics vocabulary after reviewing the first live scored set.
