from pydantic import BaseModel

class TranslationRequest(BaseModel):
    target_language: str | None = None

class TranslationResponse(BaseModel):
    translated_text: str

class SummarizationRequest(BaseModel):
    language: str | None = None
    source_text: str | None = None

class SummarizationResponse(BaseModel):
    summary: str
