-- Preserve the Lean header/import block for autoformalized staging records.

ALTER TABLE formal_statements_staging
ADD COLUMN header TEXT NOT NULL DEFAULT '';
