from __future__ import annotations

DEFAULT_LANGUAGE_CODE = "en"

LANGUAGE_LABELS: dict[str, str] = {
    "bg": "Bulgarian",
    "hr": "Croatian",
    "cs": "Czech",
    "da": "Danish",
    "nl": "Dutch",
    "en": "English",
    "et": "Estonian",
    "fi": "Finnish",
    "fr": "French",
    "de": "German",
    "el": "Greek",
    "hu": "Hungarian",
    "ga": "Irish",
    "it": "Italian",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "mt": "Maltese",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "es": "Spanish",
    "sv": "Swedish",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ru": "Russian",
}

SUPPORTED_LANG_CODES = set(LANGUAGE_LABELS.keys())


def normalize_code(code: str | None) -> str:
    if not code:
        return ""
    return code.strip().lower().split("-")[0]


def language_label(code: str | None) -> str:
    normalized = normalize_code(code)
    if not normalized:
        return LANGUAGE_LABELS.get(DEFAULT_LANGUAGE_CODE, "English")
    return LANGUAGE_LABELS.get(normalized, code or normalized)
