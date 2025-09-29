BEGIN;

ALTER TABLE app.bookmarks
  DROP CONSTRAINT IF EXISTS bookmarks_target_type_check;

ALTER TABLE app.bookmarks
  ADD CONSTRAINT bookmarks_target_type_check
  CHECK (target_type IN ('post','reply','tag','other'));

COMMIT;
