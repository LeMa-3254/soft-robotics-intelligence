# SoftRobotics Intelligence

SoftRobotics Intelligence tracks fresh developments in **soft & humanoid robotics for materials
scientists and engineers** — actuator materials, tactile skins, self-healing, fabrication, and the
material requirements and jobs at the polymer/robotics frontier. It is a scheduled pipeline that
ingests public sources, filters + LLM-scores + enriches items, stores the archive in SQLite, and
publishes a static GitHub Pages site.

It shares Polymind's architecture; the domain content (topics, sources, and two extra sections) comes
from the *Soft & Humanoid Robotics Intelligence Agent* setup guide.

## What it produces

A static site with:
- **Feed** — the week's ranked, scored developments, grouped by theme.
- **Archive** — searchable/filterable full history.
- **Weekly** — a trend synthesis clustered by theme.
- **Materials** — a Material Requirements table (application → material class → property targets → open
  challenge), generated weekly via LLM web search.

Plus, **off the public site**:
- **Open Positions** — current materials-science / engineering roles at robotics companies (LLM web
  search), written to a date-stamped Word doc `output/SoftRobotics_Jobs_YYYY-MM-DD.docx` and uploaded
  as a **downloadable GitHub Actions artifact** (`open-positions`). It is never committed and never
  published to the site — download it from the workflow run's Artifacts section.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill the API keys locally for live model calls. GitHub Actions uses
repository secrets instead of committing `.env`.

## Common Commands

```bash
make test
make run
make build-site
```

Equivalent direct commands:

```bash
python3 -m unittest discover -s tests
python3 pipeline/run.py --config targeting.yaml --db data/tracker.db
python3 pipeline/run.py --config targeting.yaml --db data/tracker.db --weekly-synthesis
python3 site/build.py --config targeting.yaml --db data/tracker.db --output public
```

The `--weekly-synthesis` run also generates the Material Requirements section (rendered on the site)
and the Open Positions Word doc in `output/` (Anthropic `web_search` tool). Without an
`ANTHROPIC_API_KEY`, scoring/enrichment fall back to a keyword bootstrap and the two web-search
sections are skipped — the pipeline still runs end to end.

## Schedule

The GitHub Actions workflow runs weekly on **Fridays at 8:00 AM PDT** (`cron: 0 15 * * 5`) with
synthesis, builds the static site, deploys to GitHub Pages, commits `data/tracker.db` back when it
changes, and uploads the Open Positions Word doc as a downloadable artifact.

## GitHub Pages Launch Notes

After the repository exists on GitHub (`LeMa-3254/soft-robotics-agent`):

1. Add repository secret `ANTHROPIC_API_KEY` (only key required). `VOYAGE_API_KEY` is optional — add it
   only if you switch `dedup.embedding_provider` to `voyage`; by default dedup uses local embeddings.
2. Enable Pages from GitHub Actions in repository settings; make the repo public if on the free plan.
3. Confirm Pages serves the project URL: `https://lema-3254.github.io/soft-robotics-agent/`.
4. Update `targeting.yaml` (`site.url`) if a custom domain replaces the Pages URL.
5. Verify the `# verify` feed URLs in `targeting.yaml` after the first run and prune any that 404/403
   (the adapters log per-feed failures without breaking the run).
