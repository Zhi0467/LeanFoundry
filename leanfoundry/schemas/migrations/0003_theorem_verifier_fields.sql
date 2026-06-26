-- Persist theorem verifier metadata required to rerun final /exec/verify.

ALTER TABLE theorems ADD COLUMN theorem_name TEXT;
ALTER TABLE theorems ADD COLUMN allowed_axioms TEXT;
