from __future__ import annotations

# Map ISO 639-1 codes to full English language names for clearer AI prompts
LANG_NAME_MAP = {
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
}

import json
import os
from pathlib import Path
from typing import Dict, Optional
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core.db import get_pool  # unused but keeps parity with other routers
from ..core.deps import require_role
from ..services.ai_service import translate_text
from .auth import csrf_validate

router = APIRouter(prefix="/i18n-admin", tags=["i18n-admin"]) 

I18N_DIR = Path("i18n")
DEFAULT_LANG = "en"


def ensure_dir() -> None:
    I18N_DIR.mkdir(parents=True, exist_ok=True)


def read_locale(lang: str) -> Dict[str, str]:
    ensure_dir()
    p = I18N_DIR / f"{lang}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to read locale {lang}: {e}")


def write_locale(lang: str, data: Dict[str, str]) -> None:
    ensure_dir()
    p = I18N_DIR / f"{lang}.json"
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to write locale {lang}: {e}")


async def require_admin_or_mod(request: Request):
    # Allow admin OR moderator
    try:
        await require_role(request, "admin")
    except Exception:
        await require_role(request, "moderator")


@router.get("/locales")
async def list_locales(_: None = Depends(require_admin_or_mod)):
    ensure_dir()
    out = []
    for f in sorted(I18N_DIR.glob("*.json")):
        out.append({"code": f.stem})
    return out


@router.get("/keys")
async def get_keys(lang: str = Query(...), _: None = Depends(require_admin_or_mod)):
    return read_locale(lang)


@router.patch("/keys")
async def write_key(
    key: str = Query(...),
    value: str = Query(...),
    lang: str = Query(...),
    _: None = Depends(require_admin_or_mod),
    __: bool = Depends(csrf_validate),
):
    data = read_locale(lang)
    data[key] = value
    write_locale(lang, data)
    return {"ok": True}


@router.post("/import-missing")
async def import_missing(lang: str = Query(...), _: None = Depends(require_admin_or_mod), __: bool = Depends(csrf_validate)):
    en = read_locale(DEFAULT_LANG)
    dst = read_locale(lang)
    added = 0
    for k, v in en.items():
        if k not in dst:
            dst[k] = v
            added += 1
    write_locale(lang, dst)
    return {"ok": True, "added": added}


@router.post("/translate-key")
async def translate_single_key(
    payload: Dict[str, object],
    _: None = Depends(require_admin_or_mod),
    __: bool = Depends(csrf_validate),
):
    """Translate a single key from English into the target language.

    Body: {"lang": "de", "key": "toast.signed_out"}
    Returns { ok: true, key: "..." }
    """
    lang = str(payload.get("lang") or "").strip()
    key = payload.get("key")
    if not lang:
        raise HTTPException(status_code=400, detail="lang required")
    if not isinstance(key, str) or not key:
        raise HTTPException(status_code=400, detail="key must be a non-empty string")

    en = read_locale(DEFAULT_LANG)
    base = str(en.get(key, ""))
    if base == "":
        raise HTTPException(status_code=404, detail="key not found in English root")

    ph_re = re.compile(r"\{[a-zA-Z0-9_]+\}")

    def mask_placeholders(s: str):
        mapping: Dict[str, str] = {}
        idx = 0
        def _repl(m):
            nonlocal idx
            token = f"__PH_{idx}__"
            idx += 1
            mapping[token] = m.group(0)
            return token
        masked = ph_re.sub(_repl, s)
        return masked, mapping

    def unmask_placeholders(s: str, mapping: Dict[str, str]):
        for token, ph in mapping.items():
            s = s.replace(token, ph)
        return s

    masked, mp = mask_placeholders(base)
    retry_info: Dict[str, str] | None = None
    try:
        target_label = LANG_NAME_MAP.get(lang.lower(), lang)
        res = await translate_text(masked, target_label, return_prompt=True)
        out = res["output"] if isinstance(res, dict) else res
    except Exception:
        out = masked
        res = {"output": out, "prompt": "(error; fallback to masked)"}

    # Unmask placeholders first pass
    final = unmask_placeholders(out, mp)

    # Heuristic: if output equals source (ignoring case/whitespace) then retry once with stricter rule
    def _norm(s: str) -> str:
        return (s or "").strip().lower()

    if _norm(final) == _norm(base):
        try:
            stronger_rule = (
                f"- If the term has a commonly localized form in {target_label}, use that localized form. "
                "Only keep the original if it is a proper noun, brand, or acronym that is not localized."
            )
            res2 = await translate_text(masked, target_label, return_prompt=True, extra_rules=stronger_rule)
            out2 = res2["output"] if isinstance(res2, dict) else res2
            final2 = unmask_placeholders(out2, mp)
            retry_info = {"retry_prompt": res2.get("prompt", "")} if isinstance(res2, dict) else {"retry_prompt": ""}
            # Accept retry if changed
            if _norm(final2) != _norm(base):
                final = final2
        except Exception:
            pass

    # Trim trailing punctuation if source had none
    def _ends_punct(s: str) -> bool:
        return bool(re.search(r"[\.!?…]$", s.strip()))

    if not _ends_punct(base) and _ends_punct(final):
        final = re.sub(r"[\.!?…]+$", "", final).strip()

    dst = read_locale(lang)
    dst[key] = final
    write_locale(lang, dst)
    out_payload = {"ok": True, "key": key, "src": base, "dst": final}
    if isinstance(res, dict):
        out_payload["prompt"] = res.get("prompt")
    if retry_info:
        out_payload.update(retry_info)
    return out_payload


@router.post("/translate-missing/keys")
async def translate_missing_keys(
    payload: Dict[str, object],
    _: None = Depends(require_admin_or_mod),
    __: bool = Depends(csrf_validate),
):
    """Translate a provided list of English keys into target lang.

    Body example: {"lang": "de", "keys": ["nav.home", "dashboard.title"]}
    Returns { ok: true, added: N }
    """
    lang = str(payload.get("lang") or "").strip()
    keys = payload.get("keys") or []
    if not lang:
        raise HTTPException(status_code=400, detail="lang required")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise HTTPException(status_code=400, detail="keys must be a string array")

    en = read_locale(DEFAULT_LANG)
    dst = read_locale(lang)

    ph_re = re.compile(r"\{[a-zA-Z0-9_]+\}")

    def mask_placeholders(s: str):
        mapping: Dict[str,str] = {}
        idx = 0
        def _repl(m):
            nonlocal idx
            token = f"__PH_{idx}__"
            idx += 1
            mapping[token] = m.group(0)
            return token
        masked = ph_re.sub(_repl, s)
        return masked, mapping

    def unmask_placeholders(s: str, mapping: Dict[str,str]):
        for token, ph in mapping.items():
            s = s.replace(token, ph)
        return s

    added = 0
    for k in keys:
        if k in dst:
            continue
        base = str(en.get(k, ""))
        if not base:
            continue
        masked, mp = mask_placeholders(base)
        try:
            out = await translate_text(masked, lang)
        except Exception:
            out = masked
        final = unmask_placeholders(out, mp)
        dst[k] = final
        added += 1

    write_locale(lang, dst)
    return {"ok": True, "added": added}


@router.post("/translate-missing")
async def translate_missing(lang: str = Query(...), _: None = Depends(require_admin_or_mod), __: bool = Depends(csrf_validate)):
    en = read_locale(DEFAULT_LANG)
    dst = read_locale(lang)

    # Placeholder preservation: {name}, {count}, etc.
    ph_re = re.compile(r"\{[a-zA-Z0-9_]+\}")

    def mask_placeholders(s: str):
        mapping: Dict[str,str] = {}
        idx = 0
        def _repl(m):
            nonlocal idx
            token = f"__PH_{idx}__"
            idx += 1
            mapping[token] = m.group(0)
            return token
        masked = ph_re.sub(_repl, s)
        return masked, mapping

    def unmask_placeholders(s: str, mapping: Dict[str,str]):
        for token, ph in mapping.items():
            s = s.replace(token, ph)
        return s

    added = 0
    for k, v in en.items():
        if k in dst:
            continue
        base = str(v)
        masked, mp = mask_placeholders(base)
        try:
            # Use existing AI client; prompt inside service handles translation
            out = await translate_text(masked, lang)
        except Exception:
            # fallback: copy english
            out = masked
        final = unmask_placeholders(out, mp)
        dst[k] = final
        added += 1

    write_locale(lang, dst)
    return {"ok": True, "added": added}
