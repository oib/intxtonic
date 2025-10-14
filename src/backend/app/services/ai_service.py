import os
import subprocess
import json

from ..core.config import get_settings


_LANGUAGE_LABELS = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ru": "Russian",
    "nl": "Dutch",
    "sv": "Swedish",
    "fi": "Finnish",
    "pl": "Polish",
}


def _language_label(code: str) -> str:
    if not code:
        return "English"
    norm = code.split("-")[0].lower()
    return _LANGUAGE_LABELS.get(norm, code)


async def translate_text(text: str, target_language: str, return_prompt: bool = False, extra_rules: str | None = None):
    settings = get_settings()
    base_url = settings.ollama_base_url
    api_key = settings.ollama_api_key
    model = settings.ollama_model

    target_language = (target_language or "en").strip()
    language_label = _language_label(target_language)
    language_spec = language_label
    if language_label.lower() != target_language.lower():
        language_spec = f"{language_label} ({target_language})"

    rules = [
        f"- Respond in {language_label} only.",
        "- Return ONLY the translated text.",
        "- Do NOT add explanations, quotes, labels, or code fences.",
        "- Preserve placeholders exactly as-is (e.g., {name}, {count}).",
        "- Do NOT add punctuation that is not present in the source unless required by grammar.",
        "- Do NOT return exactly the same text as the source unless it is a proper noun/brand/acronym or already localized.",
    ]
    if extra_rules:
        rules.append(extra_rules)

    prompt = (
        f"Translate the following text to {language_spec}.\n"
        "Rules:\n" + "\n".join(rules) + "\n\n"
        f"Text:\n{text}"
    )
    sequence = [
        'system: You are a professional translator. Follow the rules strictly and return only the translation.',
        f'user: {prompt}'
    ]

    try:
        env = os.environ.copy()
        if base_url:
            env['OLLAMA_BASE'] = base_url
        if api_key:
            env['OLLAMA_API_KEY'] = api_key
        if model:
            env['OLLAMA_MODEL'] = model

        result = subprocess.run(
            ['node', 'src/backend/js/ollama_cli.mjs', json.dumps(sequence)],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        if result.returncode != 0:
            raise Exception(f'CLI error: {result.stderr}')

        output = result.stdout.strip()
        if return_prompt:
            return {"output": output, "prompt": prompt}
        return output
    except Exception as e:
        raise Exception(f'Failed to translate text: {str(e)}')


async def summarize_text(text: str, language: str) -> str:
    settings = get_settings()
    base_url = settings.ollama_base_url
    api_key = settings.ollama_api_key
    model = settings.ollama_model

    language = (language or "en").strip()
    language_label = _language_label(language)
    language_spec = language_label
    if language_label.lower() != language.lower():
        language_spec = f"{language_label} ({language})"

    prompt = (
        f"Summarize the following text in {language_spec} in a concise paragraph (max 100 words).\n"
        "Rules:\n"
        "- Respond in the requested language only.\n"
        "- Do NOT add headings, labels, or explanations.\n"
        "- Preserve proper nouns from the source.\n\n"
        f"Text:\n{text}"
    )
    sequence = [
        'system: You are a summarizer who strictly follows language instructions.',
        f'user: {prompt}'
    ]

    try:
        env = os.environ.copy()
        if base_url:
            env['OLLAMA_BASE'] = base_url
        if api_key:
            env['OLLAMA_API_KEY'] = api_key
        if model:
            env['OLLAMA_MODEL'] = model

        result = subprocess.run(
            ['node', 'src/backend/js/ollama_cli.mjs', json.dumps(sequence)],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        if result.returncode != 0:
            raise Exception(f'CLI error: {result.stderr}')

        summary = result.stdout.strip()
        if language.lower() not in ("en", "english"):
            summary = await translate_text(summary, language)
        return summary
    except Exception as e:
        raise Exception(f'Failed to summarize text: {str(e)}')
