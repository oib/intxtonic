# Multiuser Blog Platform — Concept & Database Schema

## Core Principles

- Only logged-in users can access the app (private community).
- Guests see only the welcome and login/register pages.
- Admin (user1) has full control via a dedicated interface.
- Multi-language UI (28 EU languages).
- On-demand AI translation and summarization of posts and replies.

---

## Bootstrap (Schema & Extensions)

```sql
CREATE SCHEMA IF NOT EXISTS app;
CREATE EXTENSION IF NOT EXISTS pgcrypto;      -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext;        -- case-insensitive emails, tags
```

---

## Users & Roles

```sql
-- Daily counters for posts/replies per user
CREATE TABLE app.rate_limits (
  account_id      uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
  day_utc         date NOT NULL,
  posts_count     integer NOT NULL DEFAULT 0,
  replies_count   integer NOT NULL DEFAULT 0,
  PRIMARY KEY (account_id, day_utc)
);

-- Per-user limit overrides
CREATE TABLE app.user_limits (
  account_id          uuid PRIMARY KEY REFERENCES app.accounts(id) ON DELETE CASCADE,
  max_posts_per_day   integer,
  max_replies_per_day integer
);
```

- **User**: Can create posts, reply, vote, and upload images.
- **Moderator**: Can silence users, moderate posts/replies; their votes count double (handled in the app layer).
- **Admin**: Can perform all actions, including managing roles, tags, limits, and bans.

### User Limits (Behavior)

- Daily post and reply limits are enforced through the above schema.
- Per-user rate limits are configurable by admin.
- Automatic silencing occurs if a user’s content receives too many negative votes.
- Admin can silence or ban manually.sql -- Roles & permissions CREATE TABLE app.roles ( id              uuid PRIMARY KEY DEFAULT gen\_random\_uuid(), name            text UNIQUE NOT NULL, created\_at      timestamptz NOT NULL DEFAULT now() );

CREATE TABLE app.permissions ( id              uuid PRIMARY KEY DEFAULT gen\_random\_uuid(), key             text UNIQUE NOT NULL      -- e.g. 'post.create','user.silence' );

CREATE TABLE app.role\_permissions ( role\_id         uuid NOT NULL REFERENCES app.roles(id) ON DELETE CASCADE, permission\_id   uuid NOT NULL REFERENCES app.permissions(id) ON DELETE CASCADE, PRIMARY KEY (role\_id, permission\_id) );

CREATE TABLE app.account\_roles ( account\_id      uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE, role\_id         uuid NOT NULL REFERENCES app.roles(id) ON DELETE CASCADE, PRIMARY KEY (account\_id, role\_id) );

````

---

## Posts, Replies & Votes
- Users can create posts (with optional images) and replies.
- Voting (up/down) impacts sorting.
- Translations and summaries are generated on demand via OpenWebUI API.

```sql
-- Posts
CREATE TABLE app.posts (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  author_id       uuid NOT NULL REFERENCES app.accounts(id) ON DELETE SET NULL,
  title           text NOT NULL,
  body_md         text NOT NULL,
  lang            text NOT NULL DEFAULT 'en',
  visibility      text NOT NULL DEFAULT 'logged_in' 
                    CHECK (visibility IN ('logged_in','private','unlisted')),
  score           integer NOT NULL DEFAULT 0,
  reply_count     integer NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz
);
CREATE INDEX ON app.posts (created_at) WHERE deleted_at IS NULL;
CREATE INDEX ON app.posts (author_id) WHERE deleted_at IS NULL;

-- Replies (threaded)
CREATE TABLE app.replies (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id         uuid NOT NULL REFERENCES app.posts(id) ON DELETE CASCADE,
  author_id       uuid NOT NULL REFERENCES app.accounts(id) ON DELETE SET NULL,
  parent_id       uuid REFERENCES app.replies(id) ON DELETE CASCADE,
  body_md         text NOT NULL,
  lang            text NOT NULL DEFAULT 'en',
  score           integer NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz
);
CREATE INDEX ON app.replies (post_id, created_at) WHERE deleted_at IS NULL;

-- Votes (polymorphic target)
CREATE TABLE app.votes (
  account_id      uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
  target_type     text NOT NULL CHECK (target_type IN ('post','reply')),
  target_id       uuid NOT NULL,
  value           smallint NOT NULL CHECK (value IN (-1, 1)),
  created_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, target_type, target_id)
);
```

## Votes System
- Users can create posts, reply, vote, and upload images.
- Voting (up/down) impacts sorting and triggers automatic moderation if scores are low.
- Example: A post with ID 'uuid-post-123' receives an upvote; the score increases, and the recompute function updates the total. You can query the current score with: `SELECT score FROM app.posts WHERE id = 'uuid-post-123';`

---

## Media Handling

- Images are automatically resized to fit post width.
- Files are converted into space-efficient compressed formats.
- Media is stored and linked to posts.

```sql
-- Media assets
CREATE TABLE app.media_assets (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id        uuid NOT NULL REFERENCES app.accounts(id) ON DELETE SET NULL,
  mime_type       text NOT NULL,
  bytes           integer NOT NULL CHECK (bytes >= 0),
  width           integer,
  height          integer,
  storage_path    text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz
);

-- Attach media to posts
CREATE TABLE app.post_media (
  post_id         uuid NOT NULL REFERENCES app.posts(id) ON DELETE CASCADE,
  media_id        uuid NOT NULL REFERENCES app.media_assets(id) ON DELETE CASCADE,
  position        integer NOT NULL DEFAULT 0,
  PRIMARY KEY (post_id, media_id)
);
```

---

## Tags System

- Admin has a dedicated UI for tags.
- Tags can be created, deleted, or banned.
- Tags help classify posts and improve search.

```sql
-- Tags
CREATE TABLE app.tags (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug            citext UNIQUE NOT NULL,
  label           text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  is_banned       boolean NOT NULL DEFAULT false
);

CREATE TABLE app.post_tags (
  post_id         uuid NOT NULL REFERENCES app.posts(id) ON DELETE CASCADE,
  tag_id          uuid NOT NULL REFERENCES app.tags(id) ON DELETE CASCADE,
  PRIMARY KEY (post_id, tag_id)
);
```

---

## Translation & Summaries (AI)

- Users can request translations or summaries of posts and replies.
- Powered by OpenWebUI API.
- Limit: maximum of 20 languages per piece of content.

```sql
-- Language catalog
CREATE TABLE app.languages (
  code            text PRIMARY KEY,        -- 'en','de','fr', ...
  label           text NOT NULL
);

-- Translations
CREATE TABLE app.translations (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type     text NOT NULL CHECK (source_type IN ('post','reply')),
  source_id       uuid NOT NULL,
  target_lang     text NOT NULL REFERENCES app.languages(code),
  title_trans     text,
  body_trans_md   text NOT NULL,
  summary_md      text,
  generated_by    text NOT NULL DEFAULT 'openwebui',
  model_name      text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_type, source_id, target_lang)
);
CREATE INDEX ON app.translations (source_type, source_id);
```

---

## Moderation & Sanctions

- Admins and moderators can silence or ban users, and remove or restore posts/replies.
- Auto-silence is triggered by excessive negative votes.

```sql
-- Silences/bans
CREATE TABLE app.sanctions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id      uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
  kind            text NOT NULL CHECK (kind IN ('silence','ban')),
  reason          text,
  imposed_by      uuid REFERENCES app.accounts(id) ON DELETE SET NULL,
  starts_at       timestamptz NOT NULL DEFAULT now(),
  ends_at         timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON app.sanctions (account_id) WHERE ends_at IS NULL OR ends_at > now();

-- Moderation actions log
CREATE TABLE app.moderation_actions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id        uuid NOT NULL REFERENCES app.accounts(id) ON DELETE SET NULL,
  target_type     text NOT NULL CHECK (target_type IN ('post','reply','account','tag')),
  target_id       uuid NOT NULL,
  action          text NOT NULL, -- 'delete','restore','ban','silence','tag_ban', ...
  reason          text,
  created_at      timestamptz NOT NULL DEFAULT now()
);
```

---

## Notifications

- Toast messages appear at the bottom center for user feedback.
- Browser notifications are also supported.

```sql
CREATE TABLE app.notifications (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  recipient_id    uuid NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
  kind            text NOT NULL,        -- 'reply','mention','moderation','system'
  ref_type        text NOT NULL,        -- 'post','reply','none'
  ref_id          uuid,
  payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_read         boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON app.notifications (recipient_id, is_read);
```

---

## Scores, Counters & Triggers

```sql
-- Post score recompute
CREATE OR REPLACE FUNCTION app.recompute_post_score(p_id uuid) RETURNS void LANGUAGE sql AS $$
  UPDATE app.posts p
  SET score = COALESCE(v.s,0), updated_at = now()
  FROM (
    SELECT target_id, SUM(value)::int AS s
    FROM app.votes
    WHERE target_type = 'post' AND target_id = p_id
    GROUP BY target_id
  ) v
  WHERE p.id = p_id;
$$;

-- Reply score recompute
CREATE OR REPLACE FUNCTION app.recompute_reply_score(r_id uuid) RETURNS void LANGUAGE sql AS $$
  UPDATE app.replies r
  SET score = COALESCE(v.s,0), updated_at = now()
  FROM (
    SELECT target_id, SUM(value)::int AS s
    FROM app.votes
    WHERE target_type = 'reply' AND target_id = r_id
    GROUP BY target_id
  ) v
  WHERE r.id = r_id;
$$;

-- Trigger to recompute after votes
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

CREATE TRIGGER trg_votes_after_write
AFTER INSERT OR UPDATE OR DELETE ON app.votes
FOR EACH ROW EXECUTE FUNCTION app.vote_after_write();

-- Reply counter bumpers
CREATE OR REPLACE FUNCTION app.bump_reply_count() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    UPDATE app.posts SET reply_count = reply_count + 1 WHERE id = NEW.post_id;
  ELSIF TG_OP = 'DELETE' THEN
    UPDATE app.posts SET reply_count = GREATEST(reply_count - 1, 0) WHERE id = OLD.post_id;
  END IF;
  RETURN NULL;
END$$;

CREATE TRIGGER trg_reply_count_ins
AFTER INSERT ON app.replies
FOR EACH ROW EXECUTE FUNCTION app.bump_reply_count();

CREATE TRIGGER trg_reply_count_del
AFTER DELETE ON app.replies
FOR EACH ROW EXECUTE FUNCTION app.bump_reply_count();
```

---

## Helpful Indexes, Audit & Stats

```sql
-- Helpful indexes
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX posts_active_idx ON app.posts (created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX tags_slug_idx ON app.tags (slug);
CREATE INDEX replies_post_created ON app.replies (post_id, created_at DESC) WHERE deleted_at IS NULL;

-- Audit log
CREATE TABLE app.audit_log (
  id              bigserial PRIMARY KEY,
  at              timestamptz NOT NULL DEFAULT now(),
  actor_id        uuid REFERENCES app.accounts(id) ON DELETE SET NULL,
  event           text NOT NULL,
  details         jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX ON app.audit_log (at DESC);

-- Materialized view for admin stats
CREATE MATERIALIZED VIEW app.mv_stats AS
SELECT
  (SELECT COUNT(*) FROM app.accounts WHERE deleted_at IS NULL) AS users,
  (SELECT COUNT(*) FROM app.posts    WHERE deleted_at IS NULL) AS posts,
  (SELECT COUNT(*) FROM app.replies  WHERE deleted_at IS NULL) AS replies,
  now() AS refreshed_at;
```

---

## Pages

- **Welcome Page** (visible to guests).
- **Login/Register Page**.
- **Dashboard** (feed of posts, with votes and replies).
- **Post Detail Page** (with replies and translations).
- **Admin UI** (tags, users, stats, moderation).

---

## Technical Notes for Windsurf Programming & Performance

- Dark theme UI.
- Mobile-first layout with a responsive 960px desktop grid.
- Dedicated CSS file per HTML page.
- Toast notifications at the bottom center.
- Integrated browser notifications.
- Minimalist design focused on readability.
