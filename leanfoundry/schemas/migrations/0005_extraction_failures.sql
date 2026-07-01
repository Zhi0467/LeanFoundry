-- Persist extraction/rendering failures for audit and debugging.

CREATE TABLE IF NOT EXISTS extraction_failures (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT NOT NULL REFERENCES theorems(id),
  env_profile TEXT NOT NULL CHECK (length(env_profile) >= 1),
  attempt_id TEXT,
  failure_kind TEXT NOT NULL CHECK (
    failure_kind IN ('rendering', 'verification', 'unsupported')
  ),
  message TEXT NOT NULL CHECK (length(message) >= 1),
  node_id TEXT,
  model_version INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS extraction_failures_attempt_idx
ON extraction_failures(attempt_id);
