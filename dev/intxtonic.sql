--
-- PostgreSQL database dump
--

\restrict 7mRfouInbAADeTutuImufqgvlWpA9lMlG9EUajxhet9gXELvOC9O59OgkRuoEv7

-- Dumped from database version 17.6 (Debian 17.6-0+deb13u1)
-- Dumped by pg_dump version 17.6 (Debian 17.6-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: app; Type: SCHEMA; Schema: -; Owner: langsum
--

CREATE SCHEMA app;


ALTER SCHEMA app OWNER TO langsum;

--
-- Name: citext; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public;


--
-- Name: EXTENSION citext; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION citext IS 'data type for case-insensitive character strings';


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: bump_reply_count(); Type: FUNCTION; Schema: app; Owner: langsum
--

CREATE FUNCTION app.bump_reply_count() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    UPDATE app.posts SET reply_count = reply_count + 1 WHERE id = NEW.post_id;
  ELSIF TG_OP = 'DELETE' THEN
    UPDATE app.posts SET reply_count = GREATEST(reply_count - 1, 0) WHERE id = OLD.post_id;
  END IF;
  RETURN NULL;
END$$;


ALTER FUNCTION app.bump_reply_count() OWNER TO langsum;

--
-- Name: recompute_post_score(uuid); Type: FUNCTION; Schema: app; Owner: langsum
--

CREATE FUNCTION app.recompute_post_score(p_id uuid) RETURNS void
    LANGUAGE sql
    AS $$
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


ALTER FUNCTION app.recompute_post_score(p_id uuid) OWNER TO langsum;

--
-- Name: recompute_reply_score(uuid); Type: FUNCTION; Schema: app; Owner: langsum
--

CREATE FUNCTION app.recompute_reply_score(r_id uuid) RETURNS void
    LANGUAGE sql
    AS $$
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


ALTER FUNCTION app.recompute_reply_score(r_id uuid) OWNER TO langsum;

--
-- Name: vote_after_write(); Type: FUNCTION; Schema: app; Owner: langsum
--

CREATE FUNCTION app.vote_after_write() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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


ALTER FUNCTION app.vote_after_write() OWNER TO langsum;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: account_roles; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.account_roles (
    account_id uuid NOT NULL,
    role_id uuid NOT NULL
);


ALTER TABLE app.account_roles OWNER TO langsum;

--
-- Name: accounts; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    handle public.citext NOT NULL,
    display_name text NOT NULL,
    email public.citext,
    password_hash text,
    locale text DEFAULT 'en'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    email_confirmed_at timestamp with time zone,
    email_confirmation_token text,
    email_confirmation_token_expires timestamp with time zone,
    email_confirmation_sent_at timestamp with time zone,
    password_reset_token text,
    password_reset_token_expires timestamp with time zone,
    password_reset_sent_at timestamp with time zone,
    magic_login_token text,
    magic_login_token_expires timestamp with time zone,
    magic_login_sent_at timestamp with time zone,
    disabled_at timestamp with time zone
);


ALTER TABLE app.accounts OWNER TO langsum;

--
-- Name: audit_log; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.audit_log (
    id bigint NOT NULL,
    at timestamp with time zone DEFAULT now() NOT NULL,
    actor_id uuid,
    event text NOT NULL,
    details jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE app.audit_log OWNER TO langsum;

--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: app; Owner: langsum
--

CREATE SEQUENCE app.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE app.audit_log_id_seq OWNER TO langsum;

--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: app; Owner: langsum
--

ALTER SEQUENCE app.audit_log_id_seq OWNED BY app.audit_log.id;


--
-- Name: bookmark_tags; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.bookmark_tags (
    bookmark_id uuid NOT NULL,
    tag_slug text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE app.bookmark_tags OWNER TO langsum;

--
-- Name: bookmarks; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.bookmarks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    account_id uuid NOT NULL,
    target_type text NOT NULL,
    target_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT bookmarks_target_type_check CHECK ((target_type = ANY (ARRAY['post'::text, 'reply'::text, 'tag'::text, 'other'::text])))
);


ALTER TABLE app.bookmarks OWNER TO langsum;

--
-- Name: languages; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.languages (
    code text NOT NULL,
    label text NOT NULL
);


ALTER TABLE app.languages OWNER TO langsum;

--
-- Name: media_assets; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.media_assets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    owner_id uuid,
    mime_type text NOT NULL,
    bytes integer NOT NULL,
    width integer,
    height integer,
    storage_path text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT media_assets_bytes_check CHECK ((bytes >= 0))
);


ALTER TABLE app.media_assets OWNER TO langsum;

--
-- Name: moderation_actions; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.moderation_actions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    actor_id uuid,
    target_type text NOT NULL,
    target_id uuid NOT NULL,
    action text NOT NULL,
    reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT moderation_actions_target_type_check CHECK ((target_type = ANY (ARRAY['post'::text, 'reply'::text, 'account'::text, 'tag'::text])))
);


ALTER TABLE app.moderation_actions OWNER TO langsum;

--
-- Name: posts; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.posts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    author_id uuid,
    title text NOT NULL,
    body_md text NOT NULL,
    lang text DEFAULT 'en'::text NOT NULL,
    visibility text DEFAULT 'logged_in'::text NOT NULL,
    score integer DEFAULT 0 NOT NULL,
    reply_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT posts_visibility_check CHECK ((visibility = ANY (ARRAY['logged_in'::text, 'private'::text, 'unlisted'::text])))
);


ALTER TABLE app.posts OWNER TO langsum;

--
-- Name: replies; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.replies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    post_id uuid NOT NULL,
    author_id uuid,
    parent_id uuid,
    body_md text NOT NULL,
    lang text DEFAULT 'en'::text NOT NULL,
    score integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


ALTER TABLE app.replies OWNER TO langsum;

--
-- Name: mv_stats; Type: MATERIALIZED VIEW; Schema: app; Owner: langsum
--

CREATE MATERIALIZED VIEW app.mv_stats AS
 SELECT ( SELECT count(*) AS count
           FROM app.accounts
          WHERE (accounts.deleted_at IS NULL)) AS users,
    ( SELECT count(*) AS count
           FROM app.posts
          WHERE (posts.deleted_at IS NULL)) AS posts,
    ( SELECT count(*) AS count
           FROM app.replies
          WHERE (replies.deleted_at IS NULL)) AS replies,
    now() AS refreshed_at
  WITH NO DATA;


ALTER MATERIALIZED VIEW app.mv_stats OWNER TO langsum;

--
-- Name: notifications; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.notifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    recipient_id uuid NOT NULL,
    kind text NOT NULL,
    ref_type text NOT NULL,
    ref_id uuid,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_read boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE app.notifications OWNER TO langsum;

--
-- Name: permissions; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.permissions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    key text NOT NULL
);


ALTER TABLE app.permissions OWNER TO langsum;

--
-- Name: post_media; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.post_media (
    post_id uuid NOT NULL,
    media_id uuid NOT NULL,
    "position" integer DEFAULT 0 NOT NULL
);


ALTER TABLE app.post_media OWNER TO langsum;

--
-- Name: post_tags; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.post_tags (
    post_id uuid NOT NULL,
    tag_id uuid NOT NULL
);


ALTER TABLE app.post_tags OWNER TO langsum;

--
-- Name: rate_limits; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.rate_limits (
    account_id uuid NOT NULL,
    day_utc date NOT NULL,
    posts_count integer DEFAULT 0 NOT NULL,
    replies_count integer DEFAULT 0 NOT NULL
);


ALTER TABLE app.rate_limits OWNER TO langsum;

--
-- Name: role_permissions; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.role_permissions (
    role_id uuid NOT NULL,
    permission_id uuid NOT NULL
);


ALTER TABLE app.role_permissions OWNER TO langsum;

--
-- Name: roles; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.roles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE app.roles OWNER TO langsum;

--
-- Name: sanctions; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.sanctions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    account_id uuid NOT NULL,
    kind text NOT NULL,
    reason text,
    imposed_by uuid,
    starts_at timestamp with time zone DEFAULT now() NOT NULL,
    ends_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sanctions_kind_check CHECK ((kind = ANY (ARRAY['silence'::text, 'ban'::text])))
);


ALTER TABLE app.sanctions OWNER TO langsum;

--
-- Name: tag_visibility; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.tag_visibility (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tag_id uuid NOT NULL,
    role_id uuid,
    account_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tag_visibility_check CHECK (((((role_id IS NOT NULL))::integer + ((account_id IS NOT NULL))::integer) = 1))
);


ALTER TABLE app.tag_visibility OWNER TO langsum;

--
-- Name: tags; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.tags (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    slug public.citext NOT NULL,
    label text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    is_banned boolean DEFAULT false NOT NULL,
    is_restricted boolean DEFAULT false NOT NULL,
    created_by_admin boolean DEFAULT false NOT NULL
);


ALTER TABLE app.tags OWNER TO langsum;

--
-- Name: translations; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.translations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_type text NOT NULL,
    source_id uuid NOT NULL,
    target_lang text NOT NULL,
    title_trans text,
    body_trans_md text NOT NULL,
    summary_md text,
    generated_by text DEFAULT 'openwebui'::text NOT NULL,
    model_name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT translations_source_type_check CHECK ((source_type = ANY (ARRAY['post'::text, 'reply'::text])))
);


ALTER TABLE app.translations OWNER TO langsum;

--
-- Name: user_limits; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.user_limits (
    account_id uuid NOT NULL,
    max_posts_per_day integer,
    max_replies_per_day integer
);


ALTER TABLE app.user_limits OWNER TO langsum;

--
-- Name: votes; Type: TABLE; Schema: app; Owner: langsum
--

CREATE TABLE app.votes (
    account_id uuid NOT NULL,
    target_type text NOT NULL,
    target_id uuid NOT NULL,
    value smallint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT votes_target_type_check CHECK ((target_type = ANY (ARRAY['post'::text, 'reply'::text]))),
    CONSTRAINT votes_value_check CHECK ((value = ANY (ARRAY['-1'::integer, 1])))
);


ALTER TABLE app.votes OWNER TO langsum;

--
-- Name: audit_log id; Type: DEFAULT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.audit_log ALTER COLUMN id SET DEFAULT nextval('app.audit_log_id_seq'::regclass);


--
-- Data for Name: account_roles; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.account_roles (account_id, role_id) FROM stdin;
f6fab92d-ffc4-4a39-90eb-5cc66e445428	68831c75-ae48-4fac-9766-2480a8b6f581
\.


--
-- Data for Name: accounts; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.accounts (id, handle, display_name, email, password_hash, locale, created_at, updated_at, deleted_at, email_confirmed_at, email_confirmation_token, email_confirmation_token_expires, email_confirmation_sent_at, password_reset_token, password_reset_token_expires, password_reset_sent_at, magic_login_token, magic_login_token_expires, magic_login_sent_at, disabled_at) FROM stdin;
187dc4b3-e936-4a19-ad6c-f30a9820dfb5	Mario1__deleted__oapo0O0r	Mario1	\N	\N	en	2025-10-16 14:00:18.571582+02	2025-10-16 14:00:59.776122+02	2025-10-16 14:00:59.776122+02	2025-10-16 14:00:31.638318+02	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
c4610470-9965-47ec-b08e-0efc9e5321ae	Mario1	Mario1	kapela@gmx.at	$2b$12$NORq12j1R5zraMg70lfQHeCMqGTL93KFFl.KKzwvv6OZ9PsonCMpS	de	2025-10-16 14:04:03.482996+02	2025-10-16 14:04:03.482996+02	\N	2025-10-16 14:04:16.395332+02	\N	\N	2025-10-16 14:04:03.739466+02	\N	\N	\N	\N	\N	\N	\N
9c71d99e-95e5-4878-ae6e-cba8f54468ff	user1__deleted__YINz72vo	user1	\N	\N	en	2025-10-03 17:47:12.080806+02	2025-10-17 07:42:53.20177+02	2025-10-17 07:42:53.20177+02	2025-10-03 17:47:18.387905+02	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
f6fab92d-ffc4-4a39-90eb-5cc66e445428	langadmin	Administrator	langadmin@intxtonic.net	$2b$12$vYoEcifoazefpKiYRRJbPudc5sIGBSRDIw9mmngMmG0mHfaejdcPm	en	2025-10-03 12:39:49.741059+02	2025-10-03 12:39:49.741059+02	\N	\N	479455cffd08cc13cffc442224baecdcb07ab51a3f3ba52b59ed9611e3fe1f9f	2025-10-04 12:39:49.928206+02	2025-10-03 12:39:49.928206+02	\N	\N	\N	\N	\N	\N	\N
44d7aaea-5905-44f0-8254-235c562977fd	user6	user6	user6@intxtonic.net	$2b$12$z.8RwqL9QNWjEYEU3ZsNUutK00ddYFh0s5q.mzT7n7Hj/OSuMI/u6	en	2025-10-16 12:34:08.826874+02	2025-10-16 12:34:08.826874+02	\N	2025-10-16 12:34:23.13922+02	\N	\N	2025-10-16 12:34:09.083851+02	\N	\N	\N	\N	\N	\N	\N
40521ade-c944-47d5-abcc-ca72a9c05d7e	Mario	Mario	reddeb@gmx.at	$2b$12$HbwOeFUhFZi6gbW98FJGBOlqMeEZbSesjbWx.ne1LL2.aOAodOSuy	de	2025-10-16 12:42:15.538751+02	2025-10-16 12:42:15.538751+02	\N	\N	5ed382c1d735d92bfe43f5f4c3850ff325230c728e5d3e71e8ec5197b286b675	2025-10-17 12:42:57.975201+02	2025-10-16 12:42:57.975201+02	\N	\N	\N	\N	\N	\N	\N
0a772b53-79e9-4e64-b4e6-ae2bae460cd5	user4__deleted__4XKU_A_o	user4	\N	\N	en	2025-10-03 17:43:42.927221+02	2025-10-17 07:45:43.666941+02	2025-10-17 07:45:43.666941+02	2025-10-03 17:43:55.630135+02	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
195483b7-7cf2-4678-83f1-d4c171beff76	orangeicebear	orangeicebear	orangeicebear@gmail.com	$2b$12$gFWs5YQCGOSwp53c2budkeyqZaeJOt.XVfGQ3KK.D0KF6mEXlBCOW	en	2025-10-16 12:37:20.186151+02	2025-10-16 12:37:20.186151+02	\N	2025-10-16 12:43:16.167787+02	\N	\N	2025-10-16 12:37:20.442047+02	\N	\N	\N	\N	\N	\N	\N
d0f18188-9d47-4d1a-8339-1c007ad836e9	chello	chello	oib@chello.at	$2b$12$Vq4KNK85uG3.KJyOaWwHYui5p5DCJ/xy7aBQyv6orpaZu5eIEb9kG	en	2025-10-16 12:40:17.453668+02	2025-10-16 12:40:17.453668+02	\N	2025-10-16 12:40:28.935427+02	\N	\N	2025-10-16 12:40:17.710516+02	\N	\N	\N	2eb9cce5e7b481ffa56170fc4eea73aaa0a50de40edd9ace44554937eb39b74d	2025-10-16 13:27:38.674396+02	2025-10-16 12:57:38.674396+02	\N
3fc36df6-c24a-426d-924c-df2943de8b92	user1	user1	user1@intxtonic.net	$2b$12$pQiciZroKL3gNxMdUjq4sObqwvUBEthpZoh9fRif1wNqrszt.HQHC	de	2025-10-17 07:53:51.353176+02	2025-10-17 07:53:51.353176+02	\N	2025-10-17 07:54:17.048305+02	\N	\N	2025-10-17 07:53:51.608081+02	\N	\N	\N	\N	\N	\N	\N
992ee134-0416-4214-9f99-4bc24e296332	user5	user5	user5@keisanki.net	$2b$12$0DETkQYV1ufL65Rt8TuQ2u9KSf3DgF3QXiY1gNyRygX1tZnUrUiKW	de	2025-10-03 21:01:37.22188+02	2025-10-03 21:01:37.22188+02	\N	2025-10-03 21:06:54.236515+02	\N	\N	2025-10-03 21:01:37.400167+02	\N	\N	\N	\N	\N	\N	\N
\.


--
-- Data for Name: audit_log; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.audit_log (id, at, actor_id, event, details) FROM stdin;
\.


--
-- Data for Name: bookmark_tags; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.bookmark_tags (bookmark_id, tag_slug, created_at) FROM stdin;
\.


--
-- Data for Name: bookmarks; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.bookmarks (id, account_id, target_type, target_id, created_at) FROM stdin;
\.


--
-- Data for Name: languages; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.languages (code, label) FROM stdin;
en	English
de	Deutsch
fr	Français
es	Español
\.


--
-- Data for Name: media_assets; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.media_assets (id, owner_id, mime_type, bytes, width, height, storage_path, created_at, deleted_at) FROM stdin;
\.


--
-- Data for Name: moderation_actions; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.moderation_actions (id, actor_id, target_type, target_id, action, reason, created_at) FROM stdin;
e2e016aa-d45c-4b9b-9a44-34058fdad460	0a772b53-79e9-4e64-b4e6-ae2bae460cd5	post	d356320a-1da4-46e7-a267-b4b92af606f7	report	test	2025-10-15 14:08:16.638998+02
\.


--
-- Data for Name: notifications; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.notifications (id, recipient_id, kind, ref_type, ref_id, payload, is_read, created_at) FROM stdin;
\.


--
-- Data for Name: permissions; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.permissions (id, key) FROM stdin;
40eaf870-be2f-4a75-b395-531ea6113407	post.create
95263857-bd0c-46e6-8cbc-1db744536f84	reply.create
84e523fc-51e7-4dc2-b1c1-c6a59ba69ed3	vote.cast
cf7e2d7c-f5fd-4fcc-92b7-42c7cd0adef8	tag.manage
391c9daa-3f7c-458a-9862-cdcb4cf9a4dc	user.manage
abede979-30cd-49f1-9b84-69457ff3fee0	moderate
\.


--
-- Data for Name: post_media; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.post_media (post_id, media_id, "position") FROM stdin;
\.


--
-- Data for Name: post_tags; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.post_tags (post_id, tag_id) FROM stdin;
42120f5d-c0f8-485c-8497-f96ed915ae81	2211f8ef-ecd1-4b8a-82b4-f7e80db15b5d
42120f5d-c0f8-485c-8497-f96ed915ae81	f7c366ee-6a7a-4030-85f9-1569cc2ea1a2
341e842d-0798-4dab-914b-ba4631e49ee9	2211f8ef-ecd1-4b8a-82b4-f7e80db15b5d
341e842d-0798-4dab-914b-ba4631e49ee9	219d9874-c9e7-465f-90b2-a6166fbc51dc
d356320a-1da4-46e7-a267-b4b92af606f7	2211f8ef-ecd1-4b8a-82b4-f7e80db15b5d
d356320a-1da4-46e7-a267-b4b92af606f7	219d9874-c9e7-465f-90b2-a6166fbc51dc
d356320a-1da4-46e7-a267-b4b92af606f7	2c08089a-40ae-42a7-a0d3-c47d07a01797
d356320a-1da4-46e7-a267-b4b92af606f7	485404b4-0af6-4228-9a0d-4768fcadd664
d356320a-1da4-46e7-a267-b4b92af606f7	9a19dc9c-ebbd-4c1c-8132-d2f30312ceb9
e02cc8e4-b3db-476c-89d2-8336bf7df7f7	0e87e9db-4a00-4a46-9bc6-b924c525412f
e9e58567-7852-4d12-91a8-b9acc8949aa4	43e46e08-a7ed-4143-9c53-4ae541f623df
ee62dd87-24bf-42e7-9ec2-9590bfbb18f3	0e87e9db-4a00-4a46-9bc6-b924c525412f
42120f5d-c0f8-485c-8497-f96ed915ae81	785078ad-97a6-4b64-ba39-5d3b792fad5a
242e218e-ff37-4157-9eaa-73c0a1a2a1c1	68f63c89-3c59-46e2-821c-952cca5ed7c1
ed810519-32fd-4cb9-b2e6-862fd55c1fd9	68f63c89-3c59-46e2-821c-952cca5ed7c1
0aafca72-d14c-45ba-bdf5-3579b5470cd2	68f63c89-3c59-46e2-821c-952cca5ed7c1
205d3c79-dfda-4bc6-abde-4384f72fb774	68f63c89-3c59-46e2-821c-952cca5ed7c1
9d14dc6d-f55b-4ec1-8304-e2dc1819bc1c	68f63c89-3c59-46e2-821c-952cca5ed7c1
\.


--
-- Data for Name: posts; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.posts (id, author_id, title, body_md, lang, visibility, score, reply_count, created_at, updated_at, deleted_at) FROM stdin;
ce80b5e1-40b6-4892-97fa-6daed384edaf	40521ade-c944-47d5-abcc-ca72a9c05d7e	Post E004	The E004 cooperation is located in the kernel where everything is transmitted system-wide	en	logged_in	0	0	2025-10-16 13:11:20.003427+02	2025-10-16 13:11:20.003427+02	\N
341e842d-0798-4dab-914b-ba4631e49ee9	9c71d99e-95e5-4878-ae6e-cba8f54468ff	[deleted]	[deleted]	en	logged_in	0	0	2025-10-04 05:55:43.440073+02	2025-10-17 07:42:53.20177+02	2025-10-17 07:42:53.20177+02
d356320a-1da4-46e7-a267-b4b92af606f7	9c71d99e-95e5-4878-ae6e-cba8f54468ff	[deleted]	[deleted]	en	logged_in	2	1	2025-10-04 07:14:56.698139+02	2025-10-17 07:42:53.20177+02	2025-10-17 07:42:53.20177+02
42120f5d-c0f8-485c-8497-f96ed915ae81	0a772b53-79e9-4e64-b4e6-ae2bae460cd5	[deleted]	[deleted]	en	logged_in	2	0	2025-10-03 17:45:23.548455+02	2025-10-17 07:45:43.666941+02	2025-10-17 07:45:43.666941+02
e02cc8e4-b3db-476c-89d2-8336bf7df7f7	0a772b53-79e9-4e64-b4e6-ae2bae460cd5	[deleted]	[deleted]	en	logged_in	0	0	2025-10-16 13:36:38.492674+02	2025-10-17 07:45:43.666941+02	2025-10-17 07:45:43.666941+02
e9e58567-7852-4d12-91a8-b9acc8949aa4	0a772b53-79e9-4e64-b4e6-ae2bae460cd5	[deleted]	[deleted]	en	logged_in	0	0	2025-10-16 14:02:46.050635+02	2025-10-17 07:45:43.666941+02	2025-10-17 07:45:43.666941+02
ee62dd87-24bf-42e7-9ec2-9590bfbb18f3	0a772b53-79e9-4e64-b4e6-ae2bae460cd5	[deleted]	[deleted]	en	logged_in	0	0	2025-10-16 14:59:21.911823+02	2025-10-17 07:45:43.666941+02	2025-10-17 07:45:43.666941+02
242e218e-ff37-4157-9eaa-73c0a1a2a1c1	3fc36df6-c24a-426d-924c-df2943de8b92	Giacomo Leopardi	Boredom is in some ways the most sublime human feeling. … Not being able to be satisfied with any earthly thing or, so to speak, with the whole earth; considering the immeasurable extent of space, the number and the wonderful size of the worlds, and finding that everything is small and petty in comparison with the capacity of one’s own mind; picturing to oneself the infinite number of worlds, and the infinite universe, and feeling that the soul and our desire must be still greater than such a universe; always accusing things of insufficiency and nothingness; and suffering huge lack and emptiness, and therefore boredom – all this seems to me the greatest sign of grandeur and nobility, which there is in human nature. And so, boredom is seldom seen in persons of no account, and very seldom or never in other creatures.	en	logged_in	0	0	2025-10-17 08:59:16.420504+02	2025-10-17 08:59:16.420504+02	\N
ed810519-32fd-4cb9-b2e6-862fd55c1fd9	3fc36df6-c24a-426d-924c-df2943de8b92	Johann Gottfried Herder	The curious inconsistency of the human condition becomes clear: As an animal, the human being tends to the earth, and is attached to it as his dwelling place. As a human being, he has within him the seeds of immortality, which require to be planted in another soil. As an animal, he can satisfy his wants, and people who are content with this feel themselves sufficiently happy here below; but those who seek a nobler purpose find everything around them imperfect and incomplete. What is most noble is never accomplished upon the earth, what is most pure is rarely stable and long-lasting. This arena is only a place of exercise and trial for the powers of our hearts and minds. The history of the human species – including what it has attempted and what has happened to it, the efforts it has made and the revolutions it has undergone – proves this sufficiently.	en	logged_in	0	0	2025-10-17 09:03:28.813697+02	2025-10-17 09:03:28.813697+02	\N
586c3029-1b23-4fa8-bb5d-6cc92b40ed25	3fc36df6-c24a-426d-924c-df2943de8b92	Sophie de Condorcet	A person who is worthy of esteem is happy to esteem others. His heart is easily moved by the mere thought of a good action, and it is tied and attached to anybody he thinks can perform such an action. He is happy to be with him, and their brotherhood of virtue creates between them freedom and equality, which they may experience tenderly like the tenderness between the closest blood and natural relatives.\n\nIt is so true that the pleasure we find in loving comes (at least in the case of friendship), to a large extent, from our pleasure of making people happy through our affections, so that only generous souls can love. Souls that lack magnanimity or nobility, or that have been corrupted by selfishness, might want to be loved and might seek love’s delight and fruits, but only generous hearts who can be touched by the happiness of others really know how to love.	en	logged_in	0	0	2025-10-17 09:11:04.774863+02	2025-10-17 09:11:04.774863+02	\N
0aafca72-d14c-45ba-bdf5-3579b5470cd2	3fc36df6-c24a-426d-924c-df2943de8b92	Joaquín Xirau Palau	The social and political crisis through which the world is passing has a metaphysical background that has been little noticed, or is wholly unknown to the great majority of people. It persists in the air that we breathe; its presence is so familiar that it is imperceptible. …\n\nModern life is chaos, not Cosmos. As such, it lacks a center, it is meaningless, aimless. The ancient world was an organism. And, as in every organism, each part served the whole, and the whole gave service to the parts. … The living body of reality had its foundation in the material realm, and its culmination was in the splendor of the spirit. … [But now] the organism splits and disappears. We are left only [with the duality of] matter and spirit, the real and the ideal. The glory of the world is reduced to either one or the other. Thus transformed into a thin thread of ideas or an endless flux of causes and effects, the world becomes an illusion. And through idealism and materialization, mathematical calculus or atomic movement, it tends to dissolve into nothingness.	en	logged_in	0	0	2025-10-17 09:19:58.367304+02	2025-10-17 09:19:58.367304+02	\N
205d3c79-dfda-4bc6-abde-4384f72fb774	3fc36df6-c24a-426d-924c-df2943de8b92	Emil Cioran	* Once the shutters are closed, I stretch out in the dark. The outer world, a fading murmur, dissolves. All that is left is myself and … there’s the rub. Hermits have spent their lives in dialogue with what was most hidden within them. If only, following their example, I could give myself up to that extreme exercise, in which one unites with the intimacy of one’s own being! It is this self-interview, this inward transition which matters, and which has no value unless continually renewed, so that the self is finally absorbed by its essential version.\n\n* The faint light in each of us which dates back to before our birth, to before all births, is what must be protected if we want to rejoin that remote glory from which we shall never know why we were separated.\n\n* I have never known a single sensation of fulfillment, of true happiness, without thinking that it was the moment when – now or never – I should disappear for good.	en	logged_in	0	0	2025-10-17 09:24:01.87161+02	2025-10-17 09:24:01.87161+02	\N
9d14dc6d-f55b-4ec1-8304-e2dc1819bc1c	3fc36df6-c24a-426d-924c-df2943de8b92	Juan Bautista Alberdi	Since philosophy is the denial of all authority other than the authority of reason, philosophy is the mother of all emancipation, of all freedom, of all social progress. … There is only one freedom – that of reason, which has as many phases as there are elements in the human spirit. So when all these freedoms, or phases of rational freedom, do not exist at the same time, it can be said that no freedom properly exists. … To be free is not merely to act according to reason, but also to think according to reason, to believe according to reason, to write according to reason, to see according to reason… If, then, we want to be free, let us first be worthy of it. Freedom does not come in a flash. It is the slow birth of civilization. Freedom is not the conquest of a day; it is one of the purposes of humanity, a purpose that it will never achieve except relatively.	en	logged_in	2	0	2025-10-17 09:39:33.105168+02	2025-10-17 09:51:26.009304+02	\N
\.


--
-- Data for Name: rate_limits; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.rate_limits (account_id, day_utc, posts_count, replies_count) FROM stdin;
0a772b53-79e9-4e64-b4e6-ae2bae460cd5	2025-10-03	1	0
9c71d99e-95e5-4878-ae6e-cba8f54468ff	2025-10-04	2	0
0a772b53-79e9-4e64-b4e6-ae2bae460cd5	2025-10-15	0	1
40521ade-c944-47d5-abcc-ca72a9c05d7e	2025-10-16	1	0
0a772b53-79e9-4e64-b4e6-ae2bae460cd5	2025-10-16	3	0
3fc36df6-c24a-426d-924c-df2943de8b92	2025-10-17	6	0
\.


--
-- Data for Name: replies; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.replies (id, post_id, author_id, parent_id, body_md, lang, score, created_at, updated_at, deleted_at) FROM stdin;
bc7efb34-6dab-4888-a9a4-c1cde445a1d2	d356320a-1da4-46e7-a267-b4b92af606f7	0a772b53-79e9-4e64-b4e6-ae2bae460cd5	\N	[deleted]	en	0	2025-10-15 16:00:53.493702+02	2025-10-17 07:45:43.666941+02	2025-10-17 07:45:43.666941+02
\.


--
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.role_permissions (role_id, permission_id) FROM stdin;
68831c75-ae48-4fac-9766-2480a8b6f581	40eaf870-be2f-4a75-b395-531ea6113407
68831c75-ae48-4fac-9766-2480a8b6f581	95263857-bd0c-46e6-8cbc-1db744536f84
68831c75-ae48-4fac-9766-2480a8b6f581	84e523fc-51e7-4dc2-b1c1-c6a59ba69ed3
68831c75-ae48-4fac-9766-2480a8b6f581	cf7e2d7c-f5fd-4fcc-92b7-42c7cd0adef8
68831c75-ae48-4fac-9766-2480a8b6f581	391c9daa-3f7c-458a-9862-cdcb4cf9a4dc
68831c75-ae48-4fac-9766-2480a8b6f581	abede979-30cd-49f1-9b84-69457ff3fee0
14ddb7dd-1365-4aa7-b166-6b935b179396	40eaf870-be2f-4a75-b395-531ea6113407
14ddb7dd-1365-4aa7-b166-6b935b179396	95263857-bd0c-46e6-8cbc-1db744536f84
14ddb7dd-1365-4aa7-b166-6b935b179396	84e523fc-51e7-4dc2-b1c1-c6a59ba69ed3
14ddb7dd-1365-4aa7-b166-6b935b179396	abede979-30cd-49f1-9b84-69457ff3fee0
3c57bc41-8c7e-4dce-9f99-87b932fd18f4	40eaf870-be2f-4a75-b395-531ea6113407
3c57bc41-8c7e-4dce-9f99-87b932fd18f4	95263857-bd0c-46e6-8cbc-1db744536f84
3c57bc41-8c7e-4dce-9f99-87b932fd18f4	84e523fc-51e7-4dc2-b1c1-c6a59ba69ed3
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.roles (id, name, created_at) FROM stdin;
68831c75-ae48-4fac-9766-2480a8b6f581	admin	2025-09-21 10:31:04.373977+02
14ddb7dd-1365-4aa7-b166-6b935b179396	moderator	2025-09-21 10:31:04.373977+02
3c57bc41-8c7e-4dce-9f99-87b932fd18f4	user	2025-09-21 10:31:04.373977+02
\.


--
-- Data for Name: sanctions; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.sanctions (id, account_id, kind, reason, imposed_by, starts_at, ends_at, created_at) FROM stdin;
\.


--
-- Data for Name: tag_visibility; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.tag_visibility (id, tag_id, role_id, account_id, created_at) FROM stdin;
97154ec6-afa1-493e-8314-bc51e1e8195c	76cf399c-72b1-41ae-aa2f-9a74e2495a31	\N	992ee134-0416-4214-9f99-4bc24e296332	2025-10-03 22:10:31.109497+02
c30cf51c-64c9-417a-8801-bfc6ea0a1e9d	43e46e08-a7ed-4143-9c53-4ae541f623df	\N	0a772b53-79e9-4e64-b4e6-ae2bae460cd5	2025-10-03 22:10:50.890017+02
8775f604-2017-41dd-84e1-ba329325f400	fab15023-41c2-4e2f-a9df-931ff0369d83	\N	f6fab92d-ffc4-4a39-90eb-5cc66e445428	2025-10-03 22:20:18.70747+02
4f5d56f8-c318-4f4d-9bef-5c4c3edd428e	af3b6a0a-9027-4697-9526-0dbc65aa360a	\N	40521ade-c944-47d5-abcc-ca72a9c05d7e	2025-10-16 14:01:45.72018+02
\.


--
-- Data for Name: tags; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.tags (id, slug, label, created_at, is_banned, is_restricted, created_by_admin) FROM stdin;
2211f8ef-ecd1-4b8a-82b4-f7e80db15b5d	en	EN	2025-10-03 12:39:50.148351+02	f	f	f
f7c366ee-6a7a-4030-85f9-1569cc2ea1a2	user4	user4	2025-10-03 17:45:23.548455+02	f	f	f
f212b119-4d90-4a00-b10f-7b41b6bd3e92	general	General	2025-10-03 18:26:05.954735+02	f	f	f
785078ad-97a6-4b64-ba39-5d3b792fad5a	bookmarked	Bookmarked	2025-10-03 21:23:11.575775+02	f	f	f
219d9874-c9e7-465f-90b2-a6166fbc51dc	user1	user1	2025-10-04 05:55:43.440073+02	f	f	f
fab15023-41c2-4e2f-a9df-931ff0369d83	secret	secret	2025-10-03 20:49:31.32159+02	f	t	t
af3b6a0a-9027-4697-9526-0dbc65aa360a	room1	room1	2025-10-03 20:52:26.189944+02	f	t	t
43e46e08-a7ed-4143-9c53-4ae541f623df	room2	room2	2025-10-03 20:53:14.220728+02	f	t	t
76cf399c-72b1-41ae-aa2f-9a74e2495a31	room3	room3	2025-10-03 20:55:15.308275+02	f	t	t
2c08089a-40ae-42a7-a0d3-c47d07a01797	long	long	2025-10-15 15:25:11.675831+02	f	f	f
485404b4-0af6-4228-9a0d-4768fcadd664	123	123	2025-10-15 15:34:33.282086+02	f	f	f
9a19dc9c-ebbd-4c1c-8132-d2f30312ceb9	456	456	2025-10-15 16:00:07.039486+02	f	f	f
0e87e9db-4a00-4a46-9bc6-b924c525412f	plato	plato	2025-10-16 13:36:35.494924+02	f	t	t
68f63c89-3c59-46e2-821c-952cca5ed7c1	philosophical	philosophical	2025-10-17 08:59:21.634095+02	f	f	f
\.


--
-- Data for Name: translations; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.translations (id, source_type, source_id, target_lang, title_trans, body_trans_md, summary_md, generated_by, model_name, created_at) FROM stdin;
17624f63-8d98-4d23-a467-e2e1775b1e14	post	ce80b5e1-40b6-4892-97fa-6daed384edaf	en	\N	The E004 cooperation is situated within the kernel, where all information is shared system-wide.	\N	openwebui	\N	2025-10-17 08:40:31.986119+02
c4821415-9b22-4e43-b86a-26d5e7735c96	post	ce80b5e1-40b6-4892-97fa-6daed384edaf	de	\N	Die E004 Zusammenarbeit befindet sich im Kern, wo alles systemweit übertragen wird.	Die E004 Zusammenarbeit befindet sich im Zentrum und überträgt alles systemweit.	openwebui	\N	2025-10-17 08:49:36.62256+02
54bb826b-65ec-4cbb-88c1-07f862e7205d	post	242e218e-ff37-4157-9eaa-73c0a1a2a1c1	de	\N	Der Hunger ist in gewisser Weise der schönste menschliche Empfindung. … Nichts auf der Erde zu finden, das man sich nicht zufrieden geben kann oder sogar das ganze Universum; die unendliche Größe und Zahl der Welten und die wunderbare Größe aller Dinge, die nichts im Vergleich sind mit dem Kapital eines eigenen Geistes; Bilder von einer unendlichen Anzahl von Welten und einem unendlichen Universum, und das Gefühl, dass der Geist und unsere Wünsche noch größer sein müssen als solch ein Universum; immer die Dinge ins Unzufriedensein und nichts ins Unwichtigsein zu zwingen; und große Leere und Leidenschaft – alles ist mir das größte Zeichen von Größe und Ehre, das in der menschlichen Natur gibt. Und so, der Hunger ist selten zu sehen bei Personen, die nichts für sich sind, und sehr selten oder nie bei anderen Tieren.	Der Hunger ist eine wundervolle menschliche Empfindung, die nichts auf der Erde zu finden hat, das man nicht zufrieden geben kann. Es ist die unendliche Größe und Zahl der Welten und Dinge, die nichts im Vergleich sind mit einem eigenen Geisteskapital. Der Hunger fühlt sich groß und ehrenvoll an, wenn man es nicht in den Griff bekommt. Menschen und Tiere zeigen ihn selten oder nie, außer bei denen, die nichts für sich sind.	openwebui	\N	2025-10-17 09:02:02.666547+02
b743c430-cef4-4755-be3a-9143d3e9f8b2	post	ed810519-32fd-4cb9-b2e6-862fd55c1fd9	de	\N	Die ungewöhnliche Unstimmigkeit des menschlichen Zustandes wird klar: Als Tier, fühlt der Mensch sich an die Erde angelehnt und ist daran gebunden wie sein Heim. Als Mensch hat er in ihm die Kräfte der ewigen Lebendigkeit, die in einem anderen Boden gepflanzt werden müssen. Als Tier kann er seine Wünsche erfüllen, und Menschen, die damit zufrieden sind, fühlen sich hier unten zufrieden und glücklich; aber diejenigen, die nach einer besseren Absicht suchen, finden alles um sie herum unperfekt und unbeständig. Was am höchsten noble ist, wird nie auf der Erde vollbracht, was am höchsten rein ist, ist selten stabile und langfristig. Dieser Raum ist nur ein Ort für die Ausübung und Prüfung unserer Herzens- und Geisteskräfte. Die Geschichte des menschlichen Geschlechts – einschließlich was es versucht hat und was geschehen ist, die Anstrengungen es gemacht hat und die Revolutionen es durchgemacht hat – beweist dies ziemlich gut.	Der Mensch fühlt sich an der Erde angelehnt und gebunden wie ein Tier, aber er besitzt die Kräfte der ewigen Lebendigkeit. Als Tier kann er seine Wünsche erfüllen, aber Menschen, die nach einer besseren Absicht suchen, finden alles um sie herum unperfekt und unbeständig. Dieser Raum ist nur für die Ausübung und Prüfung unserer Herzens- und Geisteskräfte. Die Geschichte des menschlichen Geschlechts zeigt, dass es nie auf der Erde noble oder reinartige Dinge vollbracht hat.	openwebui	\N	2025-10-17 09:03:45.071114+02
26d60721-7b7d-4ad6-8539-be04ebf2b5a5	post	586c3029-1b23-4fa8-bb5d-6cc92b40ed25	de	\N	Ein Mensch, der wertvoll geliebt wird, ist glücklich, anderen zu schätzen. Sein Herz reagiert leicht auf das Gedanken an gute Taten und ist mit jedem, der sie ausführen könnte, verbunden. Er genießt es, mit ihm zu sein, und die Brüderchaft der Würde zwischen ihnen erzeugt Freiheit und Gleichheit, die sie wie die Liebe zwischen dem besten Blut und natürlichen Verwandten empfinden können.	Ein Mensch, der geliebt wird, ist glücklich und reagiert leicht auf gute Taten. Er genießt Brüderchaft und Freiheit mit anderen, die ihm ähnlich sind. Dies führt zu Gleichheit und Liebe, die er empfindet wie mit dem besten Blut und natürlichen Verwandten.	openwebui	\N	2025-10-17 09:11:20.745961+02
33ee58fc-ae88-440d-9f99-048ed668976d	post	0aafca72-d14c-45ba-bdf5-3579b5470cd2	de	\N	Die soziale und politische Krise durch die Welt ist mit einer metaphysischen Grundlage verbunden, die wenig beachtet oder vollständig unbekannt für die großen Mehrheit der Menschen ist. Sie hängt in der Luft, die wir atmen, und ihre Präsenz ist so allgemein, dass sie uns nicht wahrnehmbar ist.\n\nDer moderne Leben ist Chaos, nicht Kosmos. So hat es keinen Zentrum, es ist ohne Sinn und Ziellosigkeit. Der alte Welt war ein Organismus. Und wie in jedem Organismus, jeder Teil diente dem Ganzen und der Ganzheit diente jedem Teil. …\n\nDie lebende Körnung der Wirklichkeit hatte ihre Grundlage im materiellen Reich und ihr Ziele stand in der Glorie des Geistes. … [Aber jetzt] das Organismus wird gespalten und verschwindet. Wir sind nur noch mit dem Duality von Materie und Geist, der Realität und der Ideale übersetzt. Die Glorie der Welt wird reduziert zu einer Idee oder zu einem endlosen Fluss von Ursachen und Folgen, die Welt wird eine Illusion. Und durch Ideal	Die soziale und politische Krise ist mit einer metaphysischen Grundlage verbunden, die für die meisten Menschen wenig beachtet oder unbekannt ist. Der moderne Leben ist Chaos, ohne Zentrum oder Sinn. Die Welt war ein Organismus, in dem jeder Teil diente der Ganzheit. Heute sind wir nur noch mit Materie und Geist übersetzt, reduziert zu Ideen und Illusionen.	openwebui	\N	2025-10-17 09:20:08.76119+02
f9bb4049-4b17-4b5e-be83-2ea2f563cb4b	post	205d3c79-dfda-4bc6-abde-4384f72fb774	de	\N	* Die Schatten sind zugeschlossen, und ich streichele mich im Dunkeln aus. Der außerirdische Hintergrund, ein verblahter Laut, verschwindet. Alles, was übrig bleibt, ist ich und … da ist der Punkt. Hermits haben ihre Leben in die Rede gesetzt mit dem, was am besten in ihnen verborgen war. Wenn nur, nach ihrem Beispiel, ich mich auf diese extreme Übung einlassen könnte, in der ich mich mit der Intimität meines eigenen Wesens vereinen würde! Es ist das Selbstgespräch, die innere Übergang, das sich fürsorglich behält, und das hat keinen Wert, wenn es nicht ständig neu gewonnen wird, so dass das Selbst endgültig in seine essentielle Version eingehüllt ist.\n\n* Das leichte Licht in jedem von uns, das zurückliegt an früherer Zeit als unser Leben, ist was zu schützen, wenn wir uns wünschen, wieder auf die entfernte Glorie zurückzufinden, die wir nie wissen, warum wir getrennt wurden.\n\n* Ich habe nie einen einzigen Gefühl der Erfüllung, eines	Ich verstehe. Bitte geben Sie mir den Text in Deutsch (de) und ich werde ihn für Sie übersetzen und kurz zusammenfassen.	openwebui	\N	2025-10-17 09:24:13.069718+02
39eb58d4-bda8-4bf2-9d7f-44459a26e953	post	0aafca72-d14c-45ba-bdf5-3579b5470cd2	en	\N	The social and political crisis through which the world is passing has a metaphysical background that has been little noticed, or is wholly unknown to the great majority of people. It persists in the air we breathe; its presence is so familiar that it is imperceptible. Modern life is chaos, not Cosmos. As such, it lacks a center, it is meaningless, aimless. The ancient world was an organism. And, as in every organism, each part served the whole, and the whole gave service to the parts. The living body of reality had its foundation in the material realm, and its culmination was in the splendor of the spirit. But now, the organism splits and disappears. We are left only with the duality of matter and spirit, the real and the ideal. The glory of the world is reduced to either one or the other. Thus transformed into a thin thread of ideas or an endless flux of causes and effects, the world becomes an illusion. And through idealism and materialization, mathematical calculus or atomic movement, it tends to dissolve into nothingness.	\N	openwebui	\N	2025-10-17 11:20:05.560117+02
c5ff557a-267c-444b-802d-3f4e0c30ed5b	post	9d14dc6d-f55b-4ec1-8304-e2dc1819bc1c	de	\N	Seit der Philosophie ist die Ableitung aller Autorität außerhalb der Autorität der Vernunft die Mutter aller Entfesselung, aller Freiheit, aller sozialen Fortschritt. … Es gibt nur eine Freiheit – die der Vernunft, die wie viele Elemente im menschlichen Geist existiert. Also wenn alle diese Freiheiten oder Phasen rationaler Freiheit nicht gleichzeitig existieren, kann man sagen, dass keine Freiheit richtig existiert. … Um frei zu sein ist es nicht nur, nach Vernunft zu handeln, sondern auch, nach Vernunft zu denken, zu glauben und zu schreiben, um zu sehen… Wenn also wir frei werden wollen, sollten wir erst einmal wertvoll sein. Freiheit kommt nicht in einem Blitz. Es ist die langsame Geburt der Kultur. Freiheit ist nicht das Siegeszug der Tage; es ist eines der Ziele der Menschheit, eine Ziele, das es niemals erreichen wird, außer relativ.	Die Philosophie fordert auf, alle Autorität außerhalb der Vernunft zu vernichten. Freiheit bedeutet rationaler Handeln und Denken, glauben und Schreiben. Um frei zu sein, müssen wir wertvoll sein und die Kultur langsam entwickeln. Freiheit ist nicht schnell, sondern ein Ziel der Menschheit, das niemals erreicht wird.	openwebui	\N	2025-10-17 09:39:45.227335+02
1b417113-9415-486f-a0ad-66bf5695ee18	post	586c3029-1b23-4fa8-bb5d-6cc92b40ed25	en	\N	A person who is worthy of esteem is happy to esteem others. His heart is easily moved by the mere thought of a good action, and it is tied and attached to anybody he thinks can perform such an action. He is happy to be with him, and their brotherhood of virtue creates between them freedom and equality, which they may experience tenderly like the tenderness between the closest blood and natural relatives.	A person who is worthy of esteem is happy to esteem others, moved by the thought of good actions. They bond with those they believe can perform such actions, creating a brotherhood of virtue that fosters freedom and equality, much like the bond between close family members.	openwebui	\N	2025-10-17 12:17:59.959259+02
d0e3a664-918e-4073-a3ca-55cffdf3a5cb	post	ed810519-32fd-4cb9-b2e6-862fd55c1fd9	en	\N	The curious inconsistency of the human condition becomes clear: As an animal, the human being tends to the earth, and is attached to it as his dwelling place. As a human being, he has within him the seeds of immortality, which require to be planted in another soil. As an animal, he can satisfy his wants, and people who are content with this feel themselves sufficiently happy here below; but those who seek a nobler purpose find everything around them imperfect and incomplete. What is most noble is never accomplished upon the earth, what is most pure is rarely stable and long-lasting. This arena is only a place of exercise and trial for the powers of our hearts and minds. The history of the human species – including what it has attempted and what has happened to it, the efforts it has made and the revolutions it has undergone – proves this sufficiently.	The human condition's curious inconsistency becomes clear: as an animal, we tend to the earth and feel attached to it as our dwelling place. As a human being, we possess seeds of immortality that require planting in another soil. Animals can satisfy their wants, but those seeking nobler purposes find everything around them imperfect and incomplete. What is noble never fully achieved on Earth, purity rarely stable and long-lasting. This world serves as an arena for the exercise and trial of our hearts and minds. The history of humanity proves this consistently: from its attempts and outcomes, efforts made and revolutions undergone, it shows that the human condition's inconsistency is inevitable.	openwebui	\N	2025-10-18 08:38:44.383963+02
\.


--
-- Data for Name: user_limits; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.user_limits (account_id, max_posts_per_day, max_replies_per_day) FROM stdin;
\.


--
-- Data for Name: votes; Type: TABLE DATA; Schema: app; Owner: langsum
--

COPY app.votes (account_id, target_type, target_id, value, created_at) FROM stdin;
9c71d99e-95e5-4878-ae6e-cba8f54468ff	post	42120f5d-c0f8-485c-8497-f96ed915ae81	1	2025-10-03 17:53:07.058498+02
0a772b53-79e9-4e64-b4e6-ae2bae460cd5	post	d356320a-1da4-46e7-a267-b4b92af606f7	1	2025-10-15 16:01:05.966914+02
3fc36df6-c24a-426d-924c-df2943de8b92	post	9d14dc6d-f55b-4ec1-8304-e2dc1819bc1c	1	2025-10-17 09:51:26.009304+02
\.


--
-- Name: audit_log_id_seq; Type: SEQUENCE SET; Schema: app; Owner: langsum
--

SELECT pg_catalog.setval('app.audit_log_id_seq', 1, false);


--
-- Name: account_roles account_roles_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.account_roles
    ADD CONSTRAINT account_roles_pkey PRIMARY KEY (account_id, role_id);


--
-- Name: accounts accounts_email_key; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.accounts
    ADD CONSTRAINT accounts_email_key UNIQUE (email);


--
-- Name: accounts accounts_handle_key; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.accounts
    ADD CONSTRAINT accounts_handle_key UNIQUE (handle);


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: bookmark_tags bookmark_tags_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.bookmark_tags
    ADD CONSTRAINT bookmark_tags_pkey PRIMARY KEY (bookmark_id, tag_slug);


--
-- Name: bookmarks bookmarks_account_id_target_type_target_id_key; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.bookmarks
    ADD CONSTRAINT bookmarks_account_id_target_type_target_id_key UNIQUE (account_id, target_type, target_id);


--
-- Name: bookmarks bookmarks_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.bookmarks
    ADD CONSTRAINT bookmarks_pkey PRIMARY KEY (id);


--
-- Name: languages languages_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.languages
    ADD CONSTRAINT languages_pkey PRIMARY KEY (code);


--
-- Name: media_assets media_assets_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.media_assets
    ADD CONSTRAINT media_assets_pkey PRIMARY KEY (id);


--
-- Name: moderation_actions moderation_actions_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.moderation_actions
    ADD CONSTRAINT moderation_actions_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_key_key; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.permissions
    ADD CONSTRAINT permissions_key_key UNIQUE (key);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: post_media post_media_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.post_media
    ADD CONSTRAINT post_media_pkey PRIMARY KEY (post_id, media_id);


--
-- Name: post_tags post_tags_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.post_tags
    ADD CONSTRAINT post_tags_pkey PRIMARY KEY (post_id, tag_id);


--
-- Name: posts posts_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.posts
    ADD CONSTRAINT posts_pkey PRIMARY KEY (id);


--
-- Name: rate_limits rate_limits_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.rate_limits
    ADD CONSTRAINT rate_limits_pkey PRIMARY KEY (account_id, day_utc);


--
-- Name: replies replies_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.replies
    ADD CONSTRAINT replies_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (role_id, permission_id);


--
-- Name: roles roles_name_key; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.roles
    ADD CONSTRAINT roles_name_key UNIQUE (name);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: sanctions sanctions_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.sanctions
    ADD CONSTRAINT sanctions_pkey PRIMARY KEY (id);


--
-- Name: tag_visibility tag_visibility_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.tag_visibility
    ADD CONSTRAINT tag_visibility_pkey PRIMARY KEY (id);


--
-- Name: tags tags_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);


--
-- Name: tags tags_slug_key; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.tags
    ADD CONSTRAINT tags_slug_key UNIQUE (slug);


--
-- Name: translations translations_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.translations
    ADD CONSTRAINT translations_pkey PRIMARY KEY (id);


--
-- Name: translations translations_source_type_source_id_target_lang_key; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.translations
    ADD CONSTRAINT translations_source_type_source_id_target_lang_key UNIQUE (source_type, source_id, target_lang);


--
-- Name: user_limits user_limits_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.user_limits
    ADD CONSTRAINT user_limits_pkey PRIMARY KEY (account_id);


--
-- Name: votes votes_pkey; Type: CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.votes
    ADD CONSTRAINT votes_pkey PRIMARY KEY (account_id, target_type, target_id);


--
-- Name: accounts_handle_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX accounts_handle_idx ON app.accounts USING btree (lower((handle)::text));


--
-- Name: audit_log_at_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX audit_log_at_idx ON app.audit_log USING btree (at DESC);


--
-- Name: bookmarks_account_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX bookmarks_account_idx ON app.bookmarks USING btree (account_id, target_type);


--
-- Name: idx_sanctions_end_at; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX idx_sanctions_end_at ON app.sanctions USING btree (account_id, ends_at) WHERE (ends_at IS NOT NULL);


--
-- Name: idx_sanctions_open; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX idx_sanctions_open ON app.sanctions USING btree (account_id) WHERE (ends_at IS NULL);


--
-- Name: idx_translations_source; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX idx_translations_source ON app.translations USING btree (source_type, source_id);


--
-- Name: notifications_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX notifications_idx ON app.notifications USING btree (recipient_id, is_read);


--
-- Name: posts_active_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX posts_active_idx ON app.posts USING btree (created_at) WHERE (deleted_at IS NULL);


--
-- Name: posts_author_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX posts_author_idx ON app.posts USING btree (author_id) WHERE (deleted_at IS NULL);


--
-- Name: replies_post_created; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX replies_post_created ON app.replies USING btree (post_id, created_at) WHERE (deleted_at IS NULL);


--
-- Name: sanctions_active_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX sanctions_active_idx ON app.sanctions USING btree (account_id, ends_at);


--
-- Name: tag_visibility_account_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX tag_visibility_account_idx ON app.tag_visibility USING btree (account_id);


--
-- Name: tag_visibility_role_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX tag_visibility_role_idx ON app.tag_visibility USING btree (role_id);


--
-- Name: tag_visibility_tag_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX tag_visibility_tag_idx ON app.tag_visibility USING btree (tag_id);


--
-- Name: tag_visibility_unique_account; Type: INDEX; Schema: app; Owner: langsum
--

CREATE UNIQUE INDEX tag_visibility_unique_account ON app.tag_visibility USING btree (tag_id, account_id) WHERE (account_id IS NOT NULL);


--
-- Name: tag_visibility_unique_role; Type: INDEX; Schema: app; Owner: langsum
--

CREATE UNIQUE INDEX tag_visibility_unique_role ON app.tag_visibility USING btree (tag_id, role_id) WHERE (role_id IS NOT NULL);


--
-- Name: tags_slug_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX tags_slug_idx ON app.tags USING btree (slug);


--
-- Name: translations_src_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX translations_src_idx ON app.translations USING btree (source_type, source_id);


--
-- Name: votes_post_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX votes_post_idx ON app.votes USING btree (target_id) WHERE (target_type = 'post'::text);


--
-- Name: votes_reply_idx; Type: INDEX; Schema: app; Owner: langsum
--

CREATE INDEX votes_reply_idx ON app.votes USING btree (target_id) WHERE (target_type = 'reply'::text);


--
-- Name: replies trg_reply_count_del; Type: TRIGGER; Schema: app; Owner: langsum
--

CREATE TRIGGER trg_reply_count_del AFTER DELETE ON app.replies FOR EACH ROW EXECUTE FUNCTION app.bump_reply_count();


--
-- Name: replies trg_reply_count_ins; Type: TRIGGER; Schema: app; Owner: langsum
--

CREATE TRIGGER trg_reply_count_ins AFTER INSERT ON app.replies FOR EACH ROW EXECUTE FUNCTION app.bump_reply_count();


--
-- Name: votes trg_votes_after_write; Type: TRIGGER; Schema: app; Owner: langsum
--

CREATE TRIGGER trg_votes_after_write AFTER INSERT OR DELETE OR UPDATE ON app.votes FOR EACH ROW EXECUTE FUNCTION app.vote_after_write();


--
-- Name: account_roles account_roles_account_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.account_roles
    ADD CONSTRAINT account_roles_account_id_fkey FOREIGN KEY (account_id) REFERENCES app.accounts(id) ON DELETE CASCADE;


--
-- Name: account_roles account_roles_role_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.account_roles
    ADD CONSTRAINT account_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES app.roles(id) ON DELETE CASCADE;


--
-- Name: audit_log audit_log_actor_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.audit_log
    ADD CONSTRAINT audit_log_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES app.accounts(id) ON DELETE SET NULL;


--
-- Name: bookmark_tags bookmark_tags_bookmark_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.bookmark_tags
    ADD CONSTRAINT bookmark_tags_bookmark_id_fkey FOREIGN KEY (bookmark_id) REFERENCES app.bookmarks(id) ON DELETE CASCADE;


--
-- Name: bookmarks bookmarks_account_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.bookmarks
    ADD CONSTRAINT bookmarks_account_id_fkey FOREIGN KEY (account_id) REFERENCES app.accounts(id) ON DELETE CASCADE;


--
-- Name: media_assets media_assets_owner_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.media_assets
    ADD CONSTRAINT media_assets_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES app.accounts(id) ON DELETE SET NULL;


--
-- Name: moderation_actions moderation_actions_actor_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.moderation_actions
    ADD CONSTRAINT moderation_actions_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES app.accounts(id) ON DELETE SET NULL;


--
-- Name: notifications notifications_recipient_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.notifications
    ADD CONSTRAINT notifications_recipient_id_fkey FOREIGN KEY (recipient_id) REFERENCES app.accounts(id) ON DELETE CASCADE;


--
-- Name: post_media post_media_media_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.post_media
    ADD CONSTRAINT post_media_media_id_fkey FOREIGN KEY (media_id) REFERENCES app.media_assets(id) ON DELETE CASCADE;


--
-- Name: post_media post_media_post_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.post_media
    ADD CONSTRAINT post_media_post_id_fkey FOREIGN KEY (post_id) REFERENCES app.posts(id) ON DELETE CASCADE;


--
-- Name: post_tags post_tags_post_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.post_tags
    ADD CONSTRAINT post_tags_post_id_fkey FOREIGN KEY (post_id) REFERENCES app.posts(id) ON DELETE CASCADE;


--
-- Name: post_tags post_tags_tag_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.post_tags
    ADD CONSTRAINT post_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES app.tags(id) ON DELETE CASCADE;


--
-- Name: posts posts_author_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.posts
    ADD CONSTRAINT posts_author_id_fkey FOREIGN KEY (author_id) REFERENCES app.accounts(id) ON DELETE SET NULL;


--
-- Name: rate_limits rate_limits_account_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.rate_limits
    ADD CONSTRAINT rate_limits_account_id_fkey FOREIGN KEY (account_id) REFERENCES app.accounts(id) ON DELETE CASCADE;


--
-- Name: replies replies_author_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.replies
    ADD CONSTRAINT replies_author_id_fkey FOREIGN KEY (author_id) REFERENCES app.accounts(id) ON DELETE SET NULL;


--
-- Name: replies replies_parent_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.replies
    ADD CONSTRAINT replies_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES app.replies(id) ON DELETE CASCADE;


--
-- Name: replies replies_post_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.replies
    ADD CONSTRAINT replies_post_id_fkey FOREIGN KEY (post_id) REFERENCES app.posts(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.role_permissions
    ADD CONSTRAINT role_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES app.permissions(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_role_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.role_permissions
    ADD CONSTRAINT role_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES app.roles(id) ON DELETE CASCADE;


--
-- Name: sanctions sanctions_account_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.sanctions
    ADD CONSTRAINT sanctions_account_id_fkey FOREIGN KEY (account_id) REFERENCES app.accounts(id) ON DELETE CASCADE;


--
-- Name: sanctions sanctions_imposed_by_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.sanctions
    ADD CONSTRAINT sanctions_imposed_by_fkey FOREIGN KEY (imposed_by) REFERENCES app.accounts(id) ON DELETE SET NULL;


--
-- Name: tag_visibility tag_visibility_account_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.tag_visibility
    ADD CONSTRAINT tag_visibility_account_id_fkey FOREIGN KEY (account_id) REFERENCES app.accounts(id) ON DELETE CASCADE;


--
-- Name: tag_visibility tag_visibility_role_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.tag_visibility
    ADD CONSTRAINT tag_visibility_role_id_fkey FOREIGN KEY (role_id) REFERENCES app.roles(id) ON DELETE CASCADE;


--
-- Name: tag_visibility tag_visibility_tag_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.tag_visibility
    ADD CONSTRAINT tag_visibility_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES app.tags(id) ON DELETE CASCADE;


--
-- Name: translations translations_target_lang_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.translations
    ADD CONSTRAINT translations_target_lang_fkey FOREIGN KEY (target_lang) REFERENCES app.languages(code);


--
-- Name: user_limits user_limits_account_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.user_limits
    ADD CONSTRAINT user_limits_account_id_fkey FOREIGN KEY (account_id) REFERENCES app.accounts(id) ON DELETE CASCADE;


--
-- Name: votes votes_account_id_fkey; Type: FK CONSTRAINT; Schema: app; Owner: langsum
--

ALTER TABLE ONLY app.votes
    ADD CONSTRAINT votes_account_id_fkey FOREIGN KEY (account_id) REFERENCES app.accounts(id) ON DELETE CASCADE;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT USAGE ON SCHEMA public TO langsum;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT ON TABLES TO langsum;


--
-- Name: mv_stats; Type: MATERIALIZED VIEW DATA; Schema: app; Owner: langsum
--

REFRESH MATERIALIZED VIEW app.mv_stats;


--
-- PostgreSQL database dump complete
--

\unrestrict 7mRfouInbAADeTutuImufqgvlWpA9lMlG9EUajxhet9gXELvOC9O59OgkRuoEv7

