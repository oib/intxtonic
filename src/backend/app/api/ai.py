from fastapi import APIRouter, Depends, HTTPException, status

from ..core.db import get_pool
from ..core.deps import get_current_account_id
from ..schemas.ai import (
    TranslationRequest,
    SummarizationRequest,
    TranslationResponse,
    SummarizationResponse,
)
from ..services.ai_service import translate_text, summarize_text

ai_route = APIRouter(prefix='/api', tags=['ai'])

@ai_route.post('/posts/{post_id}/translate', response_model=TranslationResponse)
async def translate_post(
    post_id: str,
    request: TranslationRequest,
    pool = Depends(get_pool),
    account_id: str = Depends(get_current_account_id),
):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT body_md FROM app.posts WHERE id = %s AND deleted_at IS NULL",
                (post_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
            body_md = row[0]

            target_language = (request.target_language or "").strip()
            if not target_language:
                await cur.execute(
                    "SELECT locale FROM app.accounts WHERE id = %s",
                    (account_id,),
                )
                locale_row = await cur.fetchone()
                if locale_row and locale_row[0]:
                    target_language = locale_row[0].strip()
            if not target_language:
                target_language = 'en'

    try:
        translated_text = await translate_text(body_md, target_language)
        return TranslationResponse(translated_text=translated_text)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Translation failed: {str(e)}')

@ai_route.post('/posts/{post_id}/summarize', response_model=SummarizationResponse)
async def summarize_post(
    post_id: str,
    request: SummarizationRequest,
    pool = Depends(get_pool),
    account_id: str = Depends(get_current_account_id),
):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            body_md: str | None = None
            if request.source_text:
                body_md = request.source_text
            else:
                await cur.execute(
                    "SELECT body_md FROM app.posts WHERE id = %s AND deleted_at IS NULL",
                    (post_id,),
                )
                row = await cur.fetchone()
                if not row:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
                body_md = row[0]

            summary_language = (request.language or "").strip()
            if not summary_language:
                await cur.execute(
                    "SELECT locale FROM app.accounts WHERE id = %s",
                    (account_id,),
                )
                locale_row = await cur.fetchone()
                if locale_row and locale_row[0]:
                    summary_language = locale_row[0].strip()
            if not summary_language:
                summary_language = 'en'

    try:
        summary = await summarize_text(body_md, summary_language)
        return SummarizationResponse(summary=summary)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Summarization failed: {str(e)}')
