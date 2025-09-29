BEGIN;

CREATE TABLE IF NOT EXISTS app.tag_visibility (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_id uuid NOT NULL REFERENCES app.tags(id) ON DELETE CASCADE,
  role_id uuid REFERENCES app.roles(id) ON DELETE CASCADE,
  account_id uuid REFERENCES app.accounts(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((role_id IS NOT NULL)::int + (account_id IS NOT NULL)::int = 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS tag_visibility_unique_role
  ON app.tag_visibility(tag_id, role_id)
  WHERE role_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS tag_visibility_unique_account
  ON app.tag_visibility(tag_id, account_id)
  WHERE account_id IS NOT NULL;

COMMIT;
