-- Initial persistent schema for LeanFoundry replay/evaluation data.
--
-- A migration file is the database version of "create these folders/classes".
-- It declares durable tables and columns so search results can survive after a
-- Python process exits. Applying this file creates empty tables; Python code
-- later inserts rows into them through a ReplayStore implementation.

-- B-type data: theorem statements that may or may not have known proofs.
CREATE TABLE theorems (
  id TEXT PRIMARY KEY NOT NULL,
  -- Lean theorem statement or declaration body submitted to search.
  lean_statement TEXT NOT NULL CHECK (length(lean_statement) >= 1),
  -- Optional natural-language statement paired with lean_statement.
  informal_statement TEXT,
  -- Pinned Lean/Mathlib environment. Do not mix env profiles in training.
  env_profile TEXT NOT NULL CHECK (length(env_profile) >= 1),
  -- Lean import/options header required to typecheck this theorem.
  header TEXT NOT NULL,
  -- Optional Lean block with sorry placeholders used as search roots.
  initial_lean_block TEXT,
  -- Optional quick-sampling difficulty estimate for curriculum selection.
  difficulty_estimate REAL,
  -- Latest measured pass rate for expert-iteration frontier selection.
  pass_rate_current REAL,
  pass_rate_updated_at TIMESTAMP,
  -- Provenance label; also gates search behavior like negation pruning.
  source TEXT NOT NULL DEFAULT 'unknown' CHECK (length(source) >= 1),
  -- Dataset split, usually train/val/test.
  split TEXT NOT NULL DEFAULT 'train',
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- A-type data: theorem plus verified proof, ready for supervised training.
CREATE TABLE a_type_data (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT NOT NULL REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  header TEXT NOT NULL,
  lean_proof TEXT NOT NULL,
  proof_hash TEXT NOT NULL,
  verified_by_backend BOOLEAN NOT NULL DEFAULT TRUE,
  proof_type TEXT,
  tactic_sequence TEXT,
  correction_input TEXT,
  source TEXT NOT NULL,
  model_version INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Search replay buffer. tactic_sequence stores a serialized proof tree, not
-- the live AND/OR runtime graph.
CREATE TABLE trajectories (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT NOT NULL REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_type TEXT NOT NULL,
  whole_proof TEXT,
  tactic_sequence TEXT,
  search_budget_used INTEGER,
  is_subproof BOOLEAN NOT NULL DEFAULT FALSE,
  parent_trajectory_id TEXT,
  model_version INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Positive per-state tactic examples extracted from accepted search steps.
CREATE TABLE policy_examples (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_state_hash TEXT NOT NULL,
  proof_state_pretty TEXT,
  proof_prefix TEXT NOT NULL DEFAULT '',
  tactic TEXT NOT NULL,
  depth INTEGER NOT NULL CHECK (depth >= 0),
  model_version INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Supervised value labels extracted from search traces.
--
-- label = 1 means the state was proved.
-- label = 0 and disproved = TRUE means negation pruning proved the state false.
-- label = 0 and disproved = FALSE means "searched but not proved"; this is a
-- censored negative, so downstream value training should use a lower weight.
CREATE TABLE state_value_labels (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_state_hash TEXT NOT NULL,
  proof_state_pretty TEXT,
  label INTEGER NOT NULL CHECK (label IN (0, 1)),
  weight REAL NOT NULL DEFAULT 1.0 CHECK (weight >= 0),
  disproved BOOLEAN NOT NULL DEFAULT FALSE,
  depth INTEGER CHECK (depth IS NULL OR depth >= 0),
  tactics_tried_on_subtree INTEGER CHECK (
    tactics_tried_on_subtree IS NULL OR tactics_tried_on_subtree >= 0
  ),
  model_version INTEGER NOT NULL,
  CHECK (NOT disproved OR (label = 0 AND weight = 1.0))
);

-- Autoformalized statements sit here before promotion to theorems.
CREATE TABLE formal_statements_staging (
  id TEXT PRIMARY KEY NOT NULL,
  informal_source TEXT,
  informal_statement TEXT,
  lean_statement TEXT NOT NULL,
  env_profile TEXT NOT NULL,
  formalizer_version TEXT,
  semantic_judge_score REAL CHECK (
    semantic_judge_score IS NULL
    OR (semantic_judge_score >= 0 AND semantic_judge_score <= 1)
  ),
  syntax_checked BOOLEAN NOT NULL DEFAULT FALSE,
  dedup_hash TEXT,
  promoted_to_theorems BOOLEAN NOT NULL DEFAULT FALSE
);
