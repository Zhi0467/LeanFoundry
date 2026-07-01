# Schema Release Governance

This document governs durable LeanFoundry replay/eval schemas after they are
used outside a local dev run. It covers SQLite replay migrations and file
artifact manifests.

## Scope

- SQLite replay schema versioning is owned by
  `leanfoundry/replay/sqlite_store.py`.
- `SCHEMA_VERSION` is derived from the last entry in `MIGRATIONS`.
- Durable Python schemas under `leanfoundry/schemas/` are the source of truth;
  SQL migrations must match them.
- Eval artifacts are versioned by manifest fields and content hashes, not by
  SQLite `PRAGMA user_version`.

## Compatibility Contract

Before a schema version is released or used for non-throwaway training data:

1. Treat every migration at or below that released version as immutable.
2. Additive changes use a new numbered migration and an appended
   `(version, path)` entry in `MIGRATIONS`.
3. The initial migration may only be edited for unreleased local development
   cleanup. Once a release tag exists, do not rewrite it to represent later
   schema changes.
4. Supported old versions must upgrade to current through the ordered registry.
   Keep explicit upgrade tests for every released version that is still
   supported. If support is intentionally dropped, document the cutoff in the
   design doc and implementation log.
5. Destructive changes require a migration that preserves old data in a
   replacement column/table or a documented export/import path. Silent data loss
   is not allowed.

## Required Change Checklist

For every durable schema change:

1. Update the Pydantic model first.
2. Update SQL migration(s) to match the model shape.
3. Append a new migration unless the schema is unreleased local work.
4. Add or update migration upgrade tests in `tests/test_replay_store.py`.
5. Keep `tests/test_schema_database_consistency.py` passing for columns,
   nullability, defaults, type affinity, and representative `CHECK`
   constraints.
6. Update `docs/design/leanfoundry_system_design_v11.md` with a dated v11.x
   note when the change affects the durable contract.
7. Record the completed slice in
   `docs/internal-trackers/implementation-log.md`.

## Stable Data Handling

- Prefer nullable columns or SQL defaults for backwards-compatible additions.
- Prefer new tables for new artifact families when old rows should remain
  readable without backfill.
- Keep derived columns documented in the consistency test allowlists.
- Keep backend-specific names out of durable field names unless the artifact is
  explicitly backend-specific.
- Treat eval manifest shape changes like schema changes: add fields
  compatibly, keep content hashes, and document any reader-impacting change.
