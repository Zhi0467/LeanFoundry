-- Persist synthetic negation proof attempts for DISPROVED audit trails.

CREATE TABLE IF NOT EXISTS negation_attempts (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT NOT NULL REFERENCES theorems(id),
  env_profile TEXT NOT NULL CHECK (length(env_profile) >= 1),
  attempt_id TEXT,
  source_node_id TEXT NOT NULL CHECK (length(source_node_id) >= 1),
  negated_target TEXT NOT NULL CHECK (length(negated_target) >= 1),
  status TEXT NOT NULL CHECK (length(status) >= 1),
  proved BOOLEAN NOT NULL,
  proved_tactic TEXT,
  tactic_calls_used INTEGER NOT NULL CHECK (tactic_calls_used >= 0),
  rendered_lean TEXT,
  payload_json TEXT NOT NULL CHECK (length(payload_json) >= 1),
  model_version INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS negation_attempts_attempt_idx
ON negation_attempts(attempt_id);
