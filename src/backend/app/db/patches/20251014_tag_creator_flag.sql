BEGIN;

ALTER TABLE app.tags
  ADD COLUMN IF NOT EXISTS created_by_admin boolean NOT NULL DEFAULT false;

COMMIT;
