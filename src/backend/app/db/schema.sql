-- LangSum Database Schema (PostgreSQL)
-- Aligned with docs/bootstrap/db.md

BEGIN;

-- Schema & extensions
CREATE SCHEMA IF NOT EXISTS app;
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive strings
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- trigram search helpers

-- Core: Accounts
CREATE TABLE IF NOT EXISTS app.accounts (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  handle         citext UNIQUE NOT NULL,
  display_name   text NOT NULL,
  email          citext UNIQUE,
  password_hash  text,
  locale         text NOT NULL DEFAULT 'en',
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  deleted_at     timestamptz,
  email_confirmed_at timestamptz,
  email_confirmation_token text,
  email_confirmation_token_expires timestamptz,
  email_confirmation_sent_at timestamptz
);
CREATE INDEX IF NOT EXISTS accounts_handle_idx ON app.accounts (lower(handle));

-- Roles & permissions
CREATE TABLE IF NOT EXISTS app.roles (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text UNIQUE NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.permissions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  key         text UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS app.role_permissions (
  role_id        uuid NOT NULL REFERENCES app.roles(id) ON DELETE CASCADE,
  permission_id  uuid NOT NULL REFERENCES app.permissions(id) ON DELETE CASCADE,
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS app.account_roles (
  account_id   uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
  role_id      uuid NOT NULL REFERENCES app.roles(id) ON DELETE CASCADE,
  PRIMARY KEY (account_id, role_id)
);

-- Rate limits & per-user overrides
CREATE TABLE IF NOT EXISTS app.rate_limits (
  account_id     uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
  day_utc        date NOT NULL,
  posts_count    integer NOT NULL DEFAULT 0,
  replies_count  integer NOT NULL DEFAULT 0,
  PRIMARY KEY (account_id, day_utc)
);

CREATE TABLE IF NOT EXISTS app.user_limits (
  account_id          uuid PRIMARY KEY REFERENCES app.accounts(id) ON DELETE CASCADE,
  max_posts_per_day   integer,
  max_replies_per_day integer
);

-- Posts
CREATE TABLE IF NOT EXISTS app.posts (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  author_id     uuid REFERENCES app.accounts(id) ON DELETE SET NULL,
  title         text NOT NULL,
  body_md       text NOT NULL,
  lang          text NOT NULL DEFAULT 'en',
  visibility    text NOT NULL DEFAULT 'logged_in' CHECK (visibility IN ('logged_in','private','unlisted')),
  score         integer NOT NULL DEFAULT 0,
  reply_count   integer NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz
);
CREATE INDEX IF NOT EXISTS posts_active_idx ON app.posts (created_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS posts_author_idx ON app.posts (author_id) WHERE deleted_at IS NULL;

-- Replies (threaded)
CREATE TABLE IF NOT EXISTS app.replies (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id       uuid NOT NULL REFERENCES app.posts(id) ON DELETE CASCADE,
  author_id     uuid REFERENCES app.accounts(id) ON DELETE SET NULL,
  parent_id     uuid REFERENCES app.replies(id) ON DELETE CASCADE,
  body_md       text NOT NULL,
  lang          text NOT NULL DEFAULT 'en',
  score         integer NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz
);
CREATE INDEX IF NOT EXISTS replies_post_created ON app.replies (post_id, created_at) WHERE deleted_at IS NULL;

-- Votes (polymorphic target)
CREATE TABLE IF NOT EXISTS app.votes (
  account_id    uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
  target_type   text NOT NULL CHECK (target_type IN ('post','reply')),
  target_id     uuid NOT NULL,
  value         smallint NOT NULL CHECK (value IN (-1, 1)),
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, target_type, target_id)
);
CREATE INDEX IF NOT EXISTS votes_post_idx  ON app.votes (target_id) WHERE target_type = 'post';
CREATE INDEX IF NOT EXISTS votes_reply_idx ON app.votes (target_id) WHERE target_type = 'reply';

-- Media
CREATE TABLE IF NOT EXISTS app.media_assets (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id      uuid REFERENCES app.accounts(id) ON DELETE SET NULL,
  mime_type     text NOT NULL,
  bytes         integer NOT NULL CHECK (bytes >= 0),
  width         integer,
  height        integer,
  storage_path  text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz
);

CREATE TABLE IF NOT EXISTS app.post_media (
  post_id     uuid NOT NULL REFERENCES app.posts(id) ON DELETE CASCADE,
  media_id    uuid NOT NULL REFERENCES app.media_assets(id) ON DELETE CASCADE,
  position    integer NOT NULL DEFAULT 0,
  PRIMARY KEY (post_id, media_id)
);

-- Tags
CREATE TABLE IF NOT EXISTS app.tags (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        citext UNIQUE NOT NULL,
  label       text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  is_banned   boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS tags_slug_idx ON app.tags (slug);

CREATE TABLE IF NOT EXISTS app.post_tags (
  post_id   uuid NOT NULL REFERENCES app.posts(id) ON DELETE CASCADE,
  tag_id    uuid NOT NULL REFERENCES app.tags(id) ON DELETE CASCADE,
  PRIMARY KEY (post_id, tag_id)
);

-- Bookmarks
CREATE TABLE IF NOT EXISTS app.bookmarks (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id   uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
  target_type  text NOT NULL CHECK (target_type IN ('post','reply','other')),
  target_id    uuid NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (account_id, target_type, target_id)
);
CREATE INDEX IF NOT EXISTS bookmarks_account_idx ON app.bookmarks (account_id, target_type);

CREATE TABLE IF NOT EXISTS app.bookmark_tags (
  bookmark_id uuid NOT NULL REFERENCES app.bookmarks(id) ON DELETE CASCADE,
  tag_slug    text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (bookmark_id, tag_slug)
);

INSERT INTO app.tags (id, slug, label)
VALUES (gen_random_uuid(), 'bookmarked', 'Bookmarked')
ON CONFLICT (slug) DO NOTHING;

-- Languages & Translations
CREATE TABLE IF NOT EXISTS app.languages (
  code        text PRIMARY KEY,
  label       text NOT NULL
);

CREATE TABLE IF NOT EXISTS app.translations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type   text NOT NULL CHECK (source_type IN ('post','reply')),
  source_id     uuid NOT NULL,
  target_lang   text NOT NULL REFERENCES app.languages(code),
  title_trans   text,
  body_trans_md text NOT NULL,
  summary_md    text,
  generated_by  text NOT NULL DEFAULT 'openwebui',
  model_name    text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_type, source_id, target_lang)
);
CREATE INDEX IF NOT EXISTS idx_translations_source ON app.translations (source_type, source_id);

-- Moderation
CREATE TABLE IF NOT EXISTS app.sanctions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id  uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('silence','ban')),
  reason      text,
  imposed_by  uuid REFERENCES app.accounts(id) ON DELETE SET NULL,
  starts_at   timestamptz NOT NULL DEFAULT now(),
  ends_at     timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sanctions_active ON app.sanctions (account_id) WHERE ends_at IS NULL OR ends_at > NOW();

CREATE TABLE IF NOT EXISTS app.moderation_actions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id    uuid REFERENCES app.accounts(id) ON DELETE SET NULL,
  target_type text NOT NULL CHECK (target_type IN ('post','reply','account','tag')),
  target_id   uuid NOT NULL,
  action      text NOT NULL,
  reason      text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.notifications (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  recipient_id  uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
  kind          text NOT NULL,
  ref_type      text NOT NULL,
  ref_id        uuid,
  payload       jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_read       boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notifications_idx ON app.notifications (recipient_id, is_read);

-- Score recompute functions
CREATE OR REPLACE FUNCTION app.recompute_post_score(p_id uuid) RETURNS void LANGUAGE sql AS $$
  UPDATE app.posts p
     SET score = COALESCE(v.s, 0), updated_at = now()
    FROM (
      SELECT target_id, SUM(value)::int AS s
        FROM app.votes
       WHERE target_type = 'post' AND target_id = p_id
       GROUP BY target_id
    ) v
   WHERE p.id = p_id;
$$;

CREATE OR REPLACE FUNCTION app.recompute_reply_score(r_id uuid) RETURNS void LANGUAGE sql AS $$
  UPDATE app.replies r
     SET score = COALESCE(v.s, 0), updated_at = now()
    FROM (
      SELECT target_id, SUM(value)::int AS s
        FROM app.votes
       WHERE target_type = 'reply' AND target_id = r_id
       GROUP BY target_id
    ) v
   WHERE r.id = r_id;
$$;

CREATE OR REPLACE FUNCTION app.vote_after_write() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.target_type = 'post' THEN
      PERFORM app.recompute_post_score(OLD.target_id);
    ELSE
      PERFORM app.recompute_reply_score(OLD.target_id);
    END IF;
    RETURN NULL;
  END IF;

  IF NEW.target_type = 'post' THEN
    PERFORM app.recompute_post_score(NEW.target_id);
  ELSE
    PERFORM app.recompute_reply_score(NEW.target_id);
  END IF;
  RETURN NULL;
END$$;

DROP TRIGGER IF EXISTS trg_votes_after_write ON app.votes;
CREATE TRIGGER trg_votes_after_write
AFTER INSERT OR UPDATE OR DELETE ON app.votes
FOR EACH ROW EXECUTE FUNCTION app.vote_after_write();

-- Reply counters
CREATE OR REPLACE FUNCTION app.bump_reply_count() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    UPDATE app.posts SET reply_count = reply_count + 1 WHERE id = NEW.post_id;
  ELSIF TG_OP = 'DELETE' THEN
    UPDATE app.posts SET reply_count = GREATEST(reply_count - 1, 0) WHERE id = OLD.post_id;
  END IF;
  RETURN NULL;
END$$;

DROP TRIGGER IF EXISTS trg_reply_count_ins ON app.replies;
CREATE TRIGGER trg_reply_count_ins
AFTER INSERT ON app.replies
FOR EACH ROW EXECUTE FUNCTION app.bump_reply_count();

DROP TRIGGER IF EXISTS trg_reply_count_del ON app.replies;
CREATE TRIGGER trg_reply_count_del
AFTER DELETE ON app.replies
FOR EACH ROW EXECUTE FUNCTION app.bump_reply_count();

-- Audit log
CREATE TABLE IF NOT EXISTS app.audit_log (
  id          bigserial PRIMARY KEY,
  at          timestamptz NOT NULL DEFAULT now(),
  actor_id    uuid REFERENCES app.accounts(id) ON DELETE SET NULL,
  event       text NOT NULL,
  details     jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS audit_log_at_idx ON app.audit_log (at DESC);

-- Admin stats materialized view
DROP MATERIALIZED VIEW IF EXISTS app.mv_stats;
CREATE MATERIALIZED VIEW app.mv_stats AS
SELECT
  (SELECT COUNT(*) FROM app.accounts WHERE deleted_at IS NULL) AS users,
  (SELECT COUNT(*) FROM app.posts    WHERE deleted_at IS NULL) AS posts,
  (SELECT COUNT(*) FROM app.replies  WHERE deleted_at IS NULL) AS replies,
  now() AS refreshed_at;

COMMIT;
