BEGIN;

CREATE TABLE IF NOT EXISTS app.bookmarks (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id   uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
  target_type  text NOT NULL CHECK (target_type IN ('post','reply','other')),
  target_id    uuid NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (account_id, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS bookmarks_account_idx
  ON app.bookmarks (account_id, target_type);

CREATE TABLE IF NOT EXISTS app.bookmark_tags (
  bookmark_id uuid NOT NULL REFERENCES app.bookmarks(id) ON DELETE CASCADE,
  tag_slug    text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (bookmark_id, tag_slug)
);

INSERT INTO app.tags (id, slug, label)
SELECT gen_random_uuid(), 'bookmarked', 'Bookmarked'
WHERE NOT EXISTS (
  SELECT 1 FROM app.tags WHERE slug = 'bookmarked'
);

COMMIT;
