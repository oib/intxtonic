from fastapi import APIRouter, Depends, HTTPException, status
from ..core.db import get_pool
from ..schemas.ai import TranslationRequest, SummarizationRequest, TranslationResponse, SummarizationResponse
from ..services.ai_service import translate_text, summarize_text

ai_route = APIRouter(prefix='/api', tags=['ai'])

@ai_route.post('/posts/{post_id}/translate', response_model=TranslationResponse)
async def translate_post(post_id: str, request: TranslationRequest, pool = Depends(get_pool)):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT body_md FROM app.posts WHERE id = %s AND deleted_at IS NULL", (post_id,))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
            body_md = row[0]
    
    try:
        translated_text = await translate_text(body_md, request.target_language)
        return TranslationResponse(translated_text=translated_text)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Translation failed: {str(e)}')

@ai_route.post('/posts/{post_id}/summarize', response_model=SummarizationResponse)
async def summarize_post(post_id: str, request: SummarizationRequest, pool = Depends(get_pool)):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT body_md FROM app.posts WHERE id = %s AND deleted_at IS NULL", (post_id,))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
            body_md = row[0]
    
    try:
        summary = await summarize_text(body_md, request.language)
        return SummarizationResponse(summary=summary)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f'Summarization failed: {str(e)}')
