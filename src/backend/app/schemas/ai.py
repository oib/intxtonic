from pydantic import BaseModel

class TranslationRequest(BaseModel):
    target_language: str = 'en'

class TranslationResponse(BaseModel):
    translated_text: str

class SummarizationRequest(BaseModel):
    language: str = 'en'

class SummarizationResponse(BaseModel):
    summary: str
