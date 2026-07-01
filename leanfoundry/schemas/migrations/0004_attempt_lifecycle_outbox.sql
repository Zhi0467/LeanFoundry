-- Persist backend cleanup/cancel lifecycle items for audit and retry.

CREATE TABLE IF NOT EXISTS attempt_lifecycle_outbox (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT NOT NULL REFERENCES theorems(id),
  env_profile TEXT NOT NULL CHECK (length(env_profile) >= 1),
  attempt_id TEXT NOT NULL CHECK (length(attempt_id) >= 1),
  backend_item_id TEXT NOT NULL CHECK (length(backend_item_id) >= 1),
  lifecycle_stage TEXT NOT NULL CHECK (
    lifecycle_stage IN ('cleanup', 'cancel')
  ),
  lifecycle_status TEXT NOT NULL CHECK (length(lifecycle_status) >= 1),
  retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
  max_retries INTEGER CHECK (max_retries IS NULL OR max_retries >= 0),
  last_error TEXT,
  next_retry_at TIMESTAMP,
  terminal BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS attempt_lifecycle_outbox_attempt_idx
ON attempt_lifecycle_outbox(attempt_id);

CREATE INDEX IF NOT EXISTS attempt_lifecycle_outbox_retry_idx
ON attempt_lifecycle_outbox(terminal, next_retry_at);
