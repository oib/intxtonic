from __future__ import annotations

from typing import Optional

from psycopg import AsyncConnection

from .language_utils import language_label, normalize_code


async def fetch_translation(
    conn: AsyncConnection,
    *,
    source_type: str,
    source_id: str,
    target_lang: str,
) -> Optional[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT title_trans, body_trans_md, summary_md, model_name, created_at
            FROM app.translations
            WHERE source_type = %s AND source_id = %s AND target_lang = %s
            """,
            (source_type, source_id, target_lang),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "title_trans": row[0],
            "body_trans_md": row[1],
            "summary_md": row[2],
            "model_name": row[3],
            "created_at": row[4],
        }


async def store_translation(
    conn: AsyncConnection,
    *,
    source_type: str,
    source_id: str,
    target_lang: str,
    body_trans_md: Optional[str] = None,
    title_trans: Optional[str] = None,
    summary_md: Optional[str] = None,
    model_name: Optional[str] = None,
) -> None:
    normalized_lang = normalize_code(target_lang)
    if normalized_lang:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO app.languages (code, label)
                VALUES (%s, %s)
                ON CONFLICT (code) DO NOTHING
                """,
                (normalized_lang, language_label(normalized_lang)),
            )

    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO app.translations (
                source_type,
                source_id,
                target_lang,
                title_trans,
                body_trans_md,
                summary_md,
                model_name
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_type, source_id, target_lang)
            DO UPDATE SET
                title_trans = COALESCE(EXCLUDED.title_trans, app.translations.title_trans),
                body_trans_md = COALESCE(EXCLUDED.body_trans_md, app.translations.body_trans_md),
                summary_md = COALESCE(EXCLUDED.summary_md, app.translations.summary_md),
                model_name = COALESCE(EXCLUDED.model_name, app.translations.model_name),
                created_at = now()
            """,
            (
                source_type,
                source_id,
                target_lang,
                title_trans,
                body_trans_md,
                summary_md,
                model_name,
            ),
        )
