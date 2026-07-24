CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_name TEXT NOT NULL,
  tier TEXT NOT NULL,
  authors TEXT NOT NULL DEFAULT '[]',
  published_date TEXT,
  fetched_date TEXT NOT NULL,
  abstract TEXT,
  doi TEXT,
  embedding TEXT,
  relevance_score REAL,
  quality_score REAL,
  score_reason TEXT,
  theme TEXT,
  summary TEXT,
  why_it_matters TEXT,
  digest_date TEXT,
  status TEXT NOT NULL,
  dup_of TEXT
);

CREATE TABLE IF NOT EXISTS weekly_summaries (
  week_start TEXT PRIMARY KEY,
  week_end TEXT NOT NULL,
  synthesis_md TEXT NOT NULL,
  item_ids TEXT NOT NULL,
  generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  counts_json TEXT NOT NULL,
  errors_json TEXT NOT NULL DEFAULT '[]',
  token_usage_json TEXT NOT NULL DEFAULT '{}'
);

-- Weekly Material Requirements section (application -> material class -> open challenge).
-- payload_json holds the model's {"materials": [...]} object for the week.
-- (Job Openings is written to a Word doc in output/, not stored here.)
CREATE TABLE IF NOT EXISTS material_requirements (
  week_start TEXT PRIMARY KEY,
  week_end TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  generated_at TEXT NOT NULL
);

