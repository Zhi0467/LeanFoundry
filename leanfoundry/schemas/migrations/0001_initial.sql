CREATE TABLE theorems (
  id TEXT PRIMARY KEY,
  lean_statement TEXT NOT NULL,
  informal_statement TEXT,
  env_profile TEXT NOT NULL,
  header TEXT NOT NULL,
  initial_lean_block TEXT,
  difficulty_estimate REAL,
  pass_rate_current REAL,
  pass_rate_updated_at TIMESTAMP,
  source TEXT NOT NULL,
  split TEXT DEFAULT 'train',
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE a_type_data (
  id TEXT PRIMARY KEY,
  theorem_id TEXT REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  header TEXT NOT NULL,
  lean_proof TEXT NOT NULL,
  proof_hash TEXT NOT NULL,
  verified_by_kimina BOOLEAN NOT NULL DEFAULT TRUE,
  proof_type TEXT,
  tactic_sequence TEXT,
  correction_input TEXT,
  source TEXT NOT NULL,
  model_version INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE trajectories (
  id TEXT PRIMARY KEY,
  theorem_id TEXT REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_type TEXT NOT NULL,
  whole_proof TEXT,
  tactic_sequence TEXT,
  search_budget_used INTEGER,
  is_subproof BOOLEAN DEFAULT FALSE,
  parent_trajectory_id TEXT,
  model_version INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE state_value_labels (
  id TEXT PRIMARY KEY,
  theorem_id TEXT REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_state_hash TEXT NOT NULL,
  proof_state_pretty TEXT,
  label INTEGER NOT NULL CHECK (label IN (0, 1)),
  weight REAL NOT NULL DEFAULT 1.0 CHECK (weight >= 0),
  disproved BOOLEAN DEFAULT FALSE,
  depth INTEGER,
  tactics_tried_on_subtree INTEGER,
  model_version INTEGER NOT NULL,
  CHECK (NOT disproved OR (label = 0 AND weight = 1.0))
);

CREATE TABLE formal_statements_staging (
  id TEXT PRIMARY KEY,
  informal_source TEXT,
  informal_statement TEXT,
  lean_statement TEXT,
  env_profile TEXT,
  formalizer_version TEXT,
  semantic_judge_score REAL,
  syntax_checked BOOLEAN,
  dedup_hash TEXT,
  promoted_to_theorems BOOLEAN DEFAULT FALSE
);
