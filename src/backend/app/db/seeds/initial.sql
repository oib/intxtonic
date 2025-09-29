-- LangSum initial seed data
-- Safe to run once on a fresh database
BEGIN;

-- Roles
INSERT INTO app.roles (id, name)
VALUES
  (gen_random_uuid(), 'admin'),
  (gen_random_uuid(), 'moderator'),
  (gen_random_uuid(), 'user')
ON CONFLICT (name) DO NOTHING;

-- Minimal permissions (extend later in app)
INSERT INTO app.permissions (id, key)
VALUES
  (gen_random_uuid(), 'post.create'),
  (gen_random_uuid(), 'reply.create'),
  (gen_random_uuid(), 'vote.cast'),
  (gen_random_uuid(), 'tag.manage'),
  (gen_random_uuid(), 'user.manage'),
  (gen_random_uuid(), 'moderate')
ON CONFLICT (key) DO NOTHING;

-- Grant a few defaults to roles (admin gets all)
-- Map permissions by name to ids
WITH p AS (
  SELECT key, id FROM app.permissions
), r AS (
  SELECT name, id FROM app.roles
)
INSERT INTO app.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM r CROSS JOIN p
WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;

WITH p AS (SELECT key, id FROM app.permissions), r AS (SELECT name, id FROM app.roles)
INSERT INTO app.role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM r JOIN p ON p.key IN ('post.create','reply.create','vote.cast','moderate') WHERE r.name = 'moderator'
ON CONFLICT DO NOTHING;

WITH p AS (SELECT key, id FROM app.permissions), r AS (SELECT name, id FROM app.roles)
INSERT INTO app.role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM r JOIN p ON p.key IN ('post.create','reply.create','vote.cast') WHERE r.name = 'user'
ON CONFLICT DO NOTHING;

-- Admin account: user1 (password to be set by app; password_hash can be updated later)
INSERT INTO app.accounts (id, handle, display_name, email, locale)
VALUES (gen_random_uuid(), 'user1', 'Administrator', 'user1@intxtonic.net', 'en')
ON CONFLICT (handle) DO NOTHING;

-- Attach admin role to user1
WITH a AS (
  SELECT id FROM app.accounts WHERE handle = 'user1'
), r AS (
  SELECT id FROM app.roles WHERE name = 'admin'
)
INSERT INTO app.account_roles (account_id, role_id)
SELECT a.id, r.id FROM a, r
ON CONFLICT DO NOTHING;

-- Baseline languages
INSERT INTO app.languages (code, label) VALUES
  ('en','English'),
  ('de','Deutsch'),
  ('fr','Français'),
  ('es','Español')
ON CONFLICT (code) DO NOTHING;

-- Example tags
INSERT INTO app.tags (id, slug, label)
VALUES (gen_random_uuid(), 'general', 'General')
ON CONFLICT (slug) DO NOTHING;

-- Refresh admin stats MV
REFRESH MATERIALIZED VIEW app.mv_stats;

COMMIT;
