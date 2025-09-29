import os
import subprocess
import json

# Using a relative import style to resolve path issues
from ..core.config import get_settings

async def translate_text(text: str, target_language: str, return_prompt: bool = False, extra_rules: str | None = None):
    settings = get_settings()
    base_url = settings.ollama_base_url
    api_key = settings.ollama_api_key
    model = settings.ollama_model

    # Strict translator instructions: output only the translation, preserve placeholders like {name}
    rules = [
        "- Return ONLY the translated text.",
        "- Do NOT add explanations, quotes, labels, or code fences.",
        "- Preserve placeholders exactly as-is (e.g., {name}, {count}).",
        "- Do NOT add punctuation that is not present in the source unless required by grammar.",
        "- Do NOT return exactly the same text as the source unless it is a proper noun/brand/acronym or already localized.",
    ]
    if extra_rules:
        rules.append(extra_rules)
    prompt = (
        f"Translate the following text to {target_language}.\n"
        "Rules:\n" + "\n".join(rules) + "\n\n" +
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
            ['node', 'templates/ollama_cli.mjs', json.dumps(sequence)],
            capture_output=True,
            text=True,
            env=env,
            timeout=60
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

    prompt = f'Summarize the following text in {language} in a concise paragraph (max 100 words):\n\n{text}'
    sequence = ['system: You are a summarizer. Provide concise summaries of provided texts.', f'user: {prompt}']

    try:
        env = os.environ.copy()
        if base_url:
            env['OLLAMA_BASE'] = base_url
        if api_key:
            env['OLLAMA_API_KEY'] = api_key
        if model:
            env['OLLAMA_MODEL'] = model

        result = subprocess.run(
            ['node', 'templates/ollama_cli.mjs', json.dumps(sequence)],
            capture_output=True,
            text=True,
            env=env,
            timeout=60
        )

        if result.returncode != 0:
            raise Exception(f'CLI error: {result.stderr}')

        return result.stdout.strip()
    except Exception as e:
        raise Exception(f'Failed to summarize text: {str(e)}')
