-- Add durable per-state policy examples for Path-A extraction.

CREATE TABLE IF NOT EXISTS policy_examples (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_state_hash TEXT NOT NULL,
  proof_state_pretty TEXT,
  proof_prefix TEXT NOT NULL DEFAULT '',
  tactic TEXT NOT NULL,
  depth INTEGER NOT NULL,
  model_version INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
