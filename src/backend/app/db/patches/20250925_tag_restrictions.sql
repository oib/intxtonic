BEGIN;

ALTER TABLE app.tags
  ADD COLUMN IF NOT EXISTS is_restricted boolean NOT NULL DEFAULT false;

/* Track which accounts/roles can see restricted tags */
CREATE TABLE IF NOT EXISTS app.tag_visibility (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_id      uuid NOT NULL REFERENCES app.tags(id) ON DELETE CASCADE,
  account_id  uuid REFERENCES app.accounts(id) ON DELETE CASCADE,
  role_id     uuid REFERENCES app.roles(id) ON DELETE CASCADE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (account_id IS NOT NULL OR role_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS tag_visibility_tag_idx ON app.tag_visibility(tag_id);
CREATE INDEX IF NOT EXISTS tag_visibility_account_idx ON app.tag_visibility(account_id);
CREATE INDEX IF NOT EXISTS tag_visibility_role_idx ON app.tag_visibility(role_id);

COMMIT;
