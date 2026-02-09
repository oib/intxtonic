import os
import shutil
import subprocess
import json
import logging
from functools import lru_cache
from pathlib import Path

from ..core.config import get_settings
from .language_utils import language_label as _shared_language_label


logger = logging.getLogger(__name__)

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

_FILE_LOGGER = logging.getLogger("translation_debug")
if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "").endswith("translation-debug.log") for h in _FILE_LOGGER.handlers):
    from pathlib import Path

    log_path = Path(__file__).resolve().parents[4] / "dev" / "logs" / "translation-debug.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _FILE_LOGGER.addHandler(file_handler)
    _FILE_LOGGER.setLevel(logging.INFO)


_CLI_PATH = Path(__file__).resolve().parent.parent.parent / "js" / "ollama_cli.mjs"
if not _CLI_PATH.exists():
    candidate = Path(__file__).resolve().parents[3] / "backend" / "js" / "ollama_cli.mjs"
    if candidate.exists():
        _CLI_PATH = candidate
    else:
        raise FileNotFoundError(f"ollama_cli.mjs not found at {_CLI_PATH} or {candidate}")


@lru_cache(maxsize=1)
def _resolve_node_command() -> str:
    env_override = (
        os.getenv("NODE_BIN")
        or os.getenv("NODE_PATH")
        or os.getenv("OLLAMA_NODE_BIN")
        or ""
    ).strip()

    candidates: list[str] = []
    if env_override:
        candidates.append(env_override)
    candidates.extend(["node", "nodejs"])

    for candidate in candidates:
        if candidate and shutil.which(candidate):
            return candidate

    raise FileNotFoundError(
        "Node.js executable not found. Install Node.js or set NODE_BIN to the Node.js binary path."
    )


def _language_label(code: str) -> str:
    return _shared_language_label(code)


def split_text_into_chunks(text: str, max_chars: int = 1200) -> list[str]:
    if not text:
        return [""]
    paragraphs = text.split('\n\n')
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current:
            para_len += 2  # account for the double newline separator
        if current and current_len + para_len > max_chars:
            chunks.append('\n\n'.join(current))
            current = [para]
            current_len = len(para)
        else:
            if current:
                current_len += 2 + len(para)
            else:
                current_len = len(para)
            current.append(para)

    if current:
        chunks.append('\n\n'.join(current))
    elif not chunks:
        chunks.append("")
    return chunks


async def translate_text(
    text: str,
    target_language: str,
    return_prompt: bool = False,
    extra_rules: str | None = None,
):
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
        "- Do NOT summarize, shorten, or omit any portion of the original content.",
        "- Preserve paragraph breaks and line breaks from the source text.",
        "- Preserve placeholders exactly as-is (e.g., {name}, {count}).",
        "- Do NOT add punctuation that is not present in the source unless required by grammar.",
        "- Do NOT return exactly the same text as the source unless it is a proper noun/brand/acronym or already localized.",
        "- Translate every word into the target language; only leave source-language words when they are proper nouns, brands, acronyms, or untranslatable placeholders.",
    ]
    if extra_rules:
        rules.append(extra_rules)

    try:
        env = os.environ.copy()
        if base_url:
            env['OLLAMA_BASE'] = base_url
        if api_key:
            env['OLLAMA_API_KEY'] = api_key
        if model:
            env['OLLAMA_MODEL'] = model

        translated_chunks: list[str] = []
        first_prompt: str | None = None
        chunks = split_text_into_chunks(text or "")
        try:
            node_command = _resolve_node_command()
        except FileNotFoundError as resolve_exc:
            _FILE_LOGGER.error("node resolution failed: %s", str(resolve_exc), exc_info=True)
            raise Exception(str(resolve_exc)) from resolve_exc
        # logger.debug(
        #     "Translating %d chunk(s) for target language %s", len(chunks), target_language
        # )
        # _FILE_LOGGER.info(
        #     "start translation chunks=%d target=%s", len(chunks), target_language
        # )

        for idx, chunk in enumerate(chunks):
            prompt = (
                f"Translate the following text to {language_spec}.\n"
                "Rules:\n" + "\n".join(rules) + "\n\n"
                f"Text:\n{chunk}"
            )
            sequence = [
                'system: You are a professional translator. Follow the rules strictly and return only the translation.',
                f'user: {prompt}'
            ]

            result = subprocess.run(
                [node_command, str(_CLI_PATH), json.dumps(sequence)],
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
            )

            if result.returncode != 0:
                raise Exception(f'CLI error: {result.stderr}')

            output = result.stdout.strip()
            translated_chunks.append(output)
            # logger.debug(
            #     "Received translation for chunk %d/%d (chars=%d)",
            #     idx + 1,
            #     len(chunks),
            #     len(output),
            # )
            # _FILE_LOGGER.info(
            #     "chunk complete index=%d total=%d chars=%d",
            #     idx + 1,
            #     len(chunks),
            #     len(output),
            # )
            if idx == 0 and return_prompt:
                first_prompt = prompt

        combined_output = "\n".join(translated_chunks)
        if return_prompt:
            return {"output": combined_output, "prompt": first_prompt or ""}
        return combined_output
    except Exception as e:
        _FILE_LOGGER.error("translation failed: %s", str(e), exc_info=True)
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

        try:
            node_command = _resolve_node_command()
        except FileNotFoundError as resolve_exc:
            _FILE_LOGGER.error("node resolution failed during summarize: %s", str(resolve_exc), exc_info=True)
            raise Exception(str(resolve_exc)) from resolve_exc

        result = subprocess.run(
            [node_command, str(_CLI_PATH), json.dumps(sequence)],
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
