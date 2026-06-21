"""
M4/M5/M8 - Extraction, HPN matrix construction and audit.

Public API expected by the rest of the project:
- extract_entities(...)
- build_hpn_matrix(...)
- audit_hpn_matrix(...)
- extract_hpn_matrix(...)           # legacy: texto completo (tests)
- extract_hpn_matrix_from_fragments(...)  # produccion: por fragmento

Groq calls use exponential backoff on 429/5xx. If a model response is not
usable, the module falls back to deterministic heuristics so the batch does not
lose a fragment.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from ..config import settings
from .ollama import call_ollama, get_default_model

logger = logging.getLogger(__name__)

GROQ_API_KEY = settings.groq_api_key
GEMINI_API_KEY = settings.gemini_api_key
HF_API_TOKEN = getattr(settings, "hf_api_token", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
HF_URL = "https://api-inference.huggingface.co/models"
GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_HF_LEGAL_MODEL = "google/flan-t5-large"

M5_JSON_SCHEMA_HINT = (
    'Devuelve un JSON con la clave "filas_hpn" (lista). Cada fila debe tener: '
    "fila_id, hecho_id, prueba_ids (lista de IDs existentes), norma_ids (lista de IDs existentes), "
    "elemento_juridico, estado_epistemico (probado|controvertido|sin_prueba|por_evaluar), "
    "riesgo (bajo|medio|alto|critico), accion_sugerida, contradicciones (lista opcional). "
    "Usa SOLO hecho_id, prueba_ids y norma_ids que existan en ENTIDADES. "
    "Si una fila no tiene prueba, deja prueba_ids vacio y estado_epistemico=sin_prueba."
)


def groq_disponible() -> bool:
    key = (GROQ_API_KEY or "").strip()
    return key.startswith("gsk_")


def resolve_effective_model(requested: str | None) -> str:
    """Resuelve 'auto' a groq si hay key valida, si no ollama."""
    normalized = (requested or settings.default_model or "auto").lower()
    if normalized == "auto":
        return "groq" if groq_disponible() else "ollama"
    if normalized == "groq" and not groq_disponible():
        logger.warning("[HPN] Groq solicitado pero GROQ_API_KEY invalida; usando ollama")
        return "ollama"
    return normalized


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def truncar_texto(texto: str, max_chars: int = 8000) -> str:
    texto = texto.strip()
    if len(texto) <= max_chars:
        return texto
    if max_chars >= 8000:
        head = 6000
        tail = 2000
    else:
        head = max_chars // 2
        tail = max_chars - head
    return texto[:head] + "\n\n[...texto truncado...]\n\n" + texto[-tail:]


def _truncate(text: str, limit: int = 8000) -> str:
    return truncar_texto(text, limit)


def _ensure_dict(value: Any, default: Optional[dict] = None) -> dict:
    if isinstance(value, dict):
        return value
    return dict(default or {})


def _ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _source_label(source: Any) -> str:
    if isinstance(source, dict):
        for key in ("fragmento_fuente", "source_id", "id", "hash", "numero_fragmento"):
            value = source.get(key)
            if value not in (None, ""):
                return str(value)
    if source is None:
        return "desconocido"
    return str(source)


def _source_page(source: Any) -> int:
    if isinstance(source, dict):
        for key in ("pagina", "page", "folio", "numero_pagina"):
            value = source.get(key)
            try:
                if value is not None:
                    return int(value)
            except Exception:
                pass
    return 0


def _extract_json(raw_text: str) -> Any:
    text = limpiar_json_response(raw_text)

    for end in range(len(text), 0, -1):
        candidate = text[:end].strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    raise ValueError("No se pudo interpretar la respuesta como JSON")


def limpiar_json_response(texto: str) -> str:
    texto = re.sub(r"```json\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"```\s*", "", texto)
    texto = texto.strip()
    for indice, caracter in enumerate(texto):
        if caracter in ("{", "["):
            return texto[indice:]
    return texto


def _normalize_hecho(item: dict[str, Any], index: int, source: Any) -> dict[str, Any]:
    return {
        "hecho_id": str(item.get("hecho_id") or item.get("id") or f"H-{index:03d}"),
        "descripcion": str(item.get("descripcion") or item.get("hecho") or item.get("texto") or "").strip(),
        "fragmento_fuente": str(item.get("fragmento_fuente") or _source_label(source)),
        "pagina": int(item.get("pagina") or item.get("page") or _source_page(source)),
        "actores": [str(v).strip() for v in _ensure_list(item.get("actores")) if str(v).strip()],
        "fecha_hecho": item.get("fecha_hecho") or item.get("fecha") or None,
        "confianza": float(item.get("confianza") or item.get("confidence") or 0.7),
    }


def _normalize_prueba(item: dict[str, Any], index: int, source: Any) -> dict[str, Any]:
    return {
        "prueba_id": str(item.get("prueba_id") or item.get("id") or f"P-{index:03d}"),
        "tipo": str(item.get("tipo") or item.get("clase") or item.get("categoria") or "documental"),
        "descripcion": str(item.get("descripcion") or item.get("prueba") or item.get("texto") or "").strip(),
        "fragmento_fuente": str(item.get("fragmento_fuente") or _source_label(source)),
        "pagina": int(item.get("pagina") or item.get("page") or _source_page(source)),
        "estado": str(item.get("estado") or "admitida"),
        "confianza": float(item.get("confianza") or item.get("confidence") or 0.7),
    }


def _normalize_norma(item: dict[str, Any], index: int, source: Any) -> dict[str, Any]:
    pagina = item.get("pagina") or item.get("page")
    try:
        pagina_val = int(pagina) if pagina is not None else None
    except Exception:
        pagina_val = None
    fragmento_fuente = item.get("fragmento_fuente")
    return {
        "norma_id": str(item.get("norma_id") or item.get("id") or f"N-{index:03d}"),
        "referencia": str(item.get("referencia") or item.get("articulo") or item.get("ley") or item.get("codigo") or "Norma sin referencia"),
        "descripcion": str(item.get("descripcion") or item.get("texto") or "").strip(),
        "fragmento_fuente": fragmento_fuente if fragmento_fuente not in (None, "") else _source_label(source),
        "pagina": pagina_val,
        "es_inferida": bool(item.get("es_inferida") or item.get("inferida") or False),
    }


def _normalize_entities(raw: Any, source: Any) -> dict[str, list[dict[str, Any]]]:
    payload = _ensure_dict(raw, {"hechos": [], "pruebas": [], "normas": []})
    hechos = [
        _normalize_hecho(item if isinstance(item, dict) else {"descripcion": str(item)}, idx + 1, source)
        for idx, item in enumerate(_ensure_list(payload.get("hechos")))
    ]
    pruebas = [
        _normalize_prueba(item if isinstance(item, dict) else {"descripcion": str(item)}, idx + 1, source)
        for idx, item in enumerate(_ensure_list(payload.get("pruebas")))
    ]
    normas = [
        _normalize_norma(item if isinstance(item, dict) else {"descripcion": str(item)}, idx + 1, source)
        for idx, item in enumerate(_ensure_list(payload.get("normas")))
    ]
    return {"hechos": hechos, "pruebas": pruebas, "normas": normas}


def _entity_dedup_key(item: dict[str, Any], desc_key: str = "descripcion") -> tuple[str, int, str]:
    desc = _clean(str(item.get(desc_key) or item.get("referencia") or "")).lower()[:200]
    pagina = int(item.get("pagina") or 0)
    fuente = str(item.get("fragmento_fuente") or "")
    return (desc, pagina, fuente)


def _deduplicate_entities(entities: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Fusiona entidades duplicadas y reasigna IDs globales unicos."""

    def _dedup_list(items: list[dict[str, Any]], id_key: str, prefix: str, desc_key: str = "descripcion") -> list[dict[str, Any]]:
        seen: dict[tuple[str, int, str], dict[str, Any]] = {}
        result: list[dict[str, Any]] = []

        for item in items:
            key = _entity_dedup_key(item, desc_key=desc_key)
            if key in seen:
                continue
            new_id = f"{prefix}-{len(result) + 1:03d}"
            normalized = dict(item)
            normalized[id_key] = new_id
            seen[key] = normalized
            result.append(normalized)

        return result

    hechos = _dedup_list(entities.get("hechos", []), "hecho_id", "H")
    pruebas = _dedup_list(entities.get("pruebas", []), "prueba_id", "P")
    normas = _dedup_list(entities.get("normas", []), "norma_id", "N", desc_key="referencia")
    return {"hechos": hechos, "pruebas": pruebas, "normas": normas}


def _fuente_from_hecho(hecho: dict[str, Any] | None) -> dict[str, Any]:
    if not hecho:
        return {"pagina": None, "fragmento_id": None}
    return {
        "pagina": hecho.get("pagina"),
        "fragmento_id": hecho.get("fragmento_fuente"),
    }


def _normalize_row(
    fila: dict[str, Any],
    idx: int,
    entities: dict[str, list[dict[str, Any]]],
    *,
    agente: str = "agente_hpn_m5",
) -> dict[str, Any]:
    facts = _entities_by_id(entities.get("hechos", []), "hecho_id")
    hecho_id = str(fila.get("hecho_id") or "")
    hecho = facts.get(hecho_id)
    proof_ids = [str(v) for v in _ensure_list(fila.get("prueba_ids")) if v]
    norm_ids = [str(v) for v in _ensure_list(fila.get("norma_ids")) if v]
    contradicciones = [str(v) for v in _ensure_list(fila.get("contradicciones")) if v]

    estado = str(fila.get("estado_epistemico") or "por_evaluar")
    riesgo = str(fila.get("riesgo") or "medio")

    return {
        "fila_id": str(fila.get("fila_id") or f"F-{idx:03d}"),
        "hecho_id": hecho_id,
        "prueba_ids": proof_ids,
        "norma_ids": norm_ids,
        "elemento_juridico": str(fila.get("elemento_juridico") or fila.get("elemento") or "Por determinar").strip(),
        "fuente_expediente": fila.get("fuente_expediente") or _fuente_from_hecho(hecho),
        "contradicciones": contradicciones,
        "agente_responsable": str(fila.get("agente_responsable") or agente),
        "revision_humana": str(fila.get("revision_humana") or "pendiente"),
        "estado_epistemico": estado,
        "riesgo": riesgo,
        "accion_sugerida": fila.get("accion_sugerida") or None,
        "notas": fila.get("notas") or None,
    }


def _match_by_page(items: list[dict[str, Any]], pagina: int) -> list[dict[str, Any]]:
    if not pagina:
        return []
    return [item for item in items if int(item.get("pagina") or 0) == pagina]


def _enriquecer_vinculos(
    entities: dict[str, list[dict[str, Any]]],
    matrix: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rellena prueba_ids/norma_ids faltantes usando coincidencia por fuente/pagina."""
    hechos = entities.get("hechos", [])
    pruebas = entities.get("pruebas", [])
    normas = entities.get("normas", [])
    facts = _entities_by_id(hechos, "hecho_id")
    enriched: list[dict[str, Any]] = []

    for idx, row in enumerate(matrix, start=1):
        normalized = _normalize_row(row, idx, entities)
        hecho = facts.get(normalized["hecho_id"])
        if not hecho:
            enriched.append(normalized)
            continue

        source_label = str(hecho.get("fragmento_fuente") or "")
        pagina = int(hecho.get("pagina") or 0)

        if not normalized["prueba_ids"]:
            by_source = [p.get("prueba_id") for p in _match_by_source(pruebas, source_label) if p.get("prueba_id")]
            by_page = [p.get("prueba_id") for p in _match_by_page(pruebas, pagina) if p.get("prueba_id")]
            candidates = by_source or by_page
            if not candidates and pruebas:
                best = _best_match(str(hecho.get("descripcion", "")), pruebas, "prueba_id")
                if best:
                    candidates = [best]
            normalized["prueba_ids"] = [str(v) for v in candidates if v]

        if not normalized["norma_ids"]:
            by_source = [n.get("norma_id") for n in _match_by_source(normas, source_label) if n.get("norma_id")]
            by_page = [n.get("norma_id") for n in _match_by_page(normas, pagina) if n.get("norma_id")]
            candidates = by_source or by_page
            if not candidates and normas:
                best = _best_match(str(hecho.get("descripcion", "")), normas, "norma_id")
                if best:
                    candidates = [best]
            normalized["norma_ids"] = [str(v) for v in candidates if v]

        if not normalized.get("fuente_expediente") or not normalized["fuente_expediente"].get("fragmento_id"):
            normalized["fuente_expediente"] = _fuente_from_hecho(hecho)

        has_proof = bool(normalized["prueba_ids"])
        has_norm = bool(normalized["norma_ids"])
        if normalized["estado_epistemico"] == "por_evaluar":
            if has_proof and has_norm:
                normalized["estado_epistemico"] = "probado"
                normalized["riesgo"] = "bajo"
            elif has_proof or has_norm:
                normalized["estado_epistemico"] = "controvertido"
                normalized["riesgo"] = "medio"
            else:
                normalized["estado_epistemico"] = "sin_prueba"
                normalized["riesgo"] = "alto"
        if not normalized.get("accion_sugerida"):
            if has_proof and has_norm:
                normalized["accion_sugerida"] = "Mantener y reforzar esta linea argumental"
            elif has_proof or has_norm:
                normalized["accion_sugerida"] = "Completar soporte antes de presentar como concluyente"
            else:
                normalized["accion_sugerida"] = "Buscar soporte probatorio o retirar esta fila"

        enriched.append(normalized)

    covered_hechos = {row["hecho_id"] for row in enriched if row.get("hecho_id")}
    for hecho in hechos:
        hid = str(hecho.get("hecho_id") or "")
        if hid and hid not in covered_hechos:
            heuristic_rows = _heuristic_matrix({"hechos": [hecho], "pruebas": pruebas, "normas": normas})
            for hrow in heuristic_rows:
                enriched.append(_normalize_row(hrow, len(enriched) + 1, entities, agente="heuristica"))

    return enriched


def _heuristic_entities(text: str, source: Any) -> dict[str, list[dict[str, Any]]]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    source_label = _source_label(source)
    hechos: list[dict[str, Any]] = []
    pruebas: list[dict[str, Any]] = []
    normas: list[dict[str, Any]] = []

    for sentence in sentences:
        lowered = sentence.lower()
        if re.search(r"\b(\d{1,2} de \w+ de \d{4}|\d{1,2}/\d{1,2}/\d{2,4})\b", sentence):
            hechos.append({
                "hecho_id": f"H-{len(hechos) + 1:03d}",
                "descripcion": _clean(sentence[:300]),
                "fragmento_fuente": source_label,
                "pagina": _source_page(source),
                "actores": [],
                "fecha_hecho": None,
                "confianza": 0.5,
            })
        if any(token in lowered for token in ("prueba", "documento", "folio", "acta", "sentencia", "oficio", "informe", "registro")):
            pruebas.append({
                "prueba_id": f"P-{len(pruebas) + 1:03d}",
                "tipo": "documental",
                "descripcion": _clean(sentence[:300]),
                "fragmento_fuente": source_label,
                "pagina": _source_page(source),
                "estado": "admitida",
                "confianza": 0.5,
            })
        if any(token in lowered for token in ("articulo", "art.", "ley", "codigo", "constitucion", "sentencia", "decreto", "norma")):
            normas.append({
                "norma_id": f"N-{len(normas) + 1:03d}",
                "referencia": _clean(sentence[:120]),
                "descripcion": _clean(sentence[:300]),
                "fragmento_fuente": source_label,
                "pagina": _source_page(source) or None,
                "es_inferida": False,
            })

    if not hechos and sentences:
        hechos.append({
            "hecho_id": "H-001",
            "descripcion": _clean(sentences[0][:300]),
            "fragmento_fuente": source_label,
            "pagina": _source_page(source),
            "actores": [],
            "fecha_hecho": None,
            "confianza": 0.4,
        })

    return {"hechos": hechos, "pruebas": pruebas, "normas": normas}


def _synthetic_anchor_entities(entities: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, list[dict[str, Any]]], str]:
    hecho_anchor = entities.get("hechos", [])[:1]
    prueba_anchor = entities.get("pruebas", [])[:1]
    norma_anchor = entities.get("normas", [])[:1]

    if hecho_anchor:
        return entities, "hecho"

    synthetic = dict(entities)
    if prueba_anchor or norma_anchor:
        synthetic["hechos"] = [{
            "hecho_id": "H-SIN-001",
            "descripcion": "Hecho sintetico generado para preservar trazabilidad cuando el texto no produjo un hecho claro.",
            "fragmento_fuente": (prueba_anchor or norma_anchor)[0].get("fragmento_fuente") if (prueba_anchor or norma_anchor) else "desconocido",
            "pagina": _source_page((prueba_anchor or norma_anchor)[0]) if (prueba_anchor or norma_anchor) else 0,
            "actores": [],
            "fecha_hecho": None,
            "confianza": 0.2,
        }]
        return synthetic, "sintetico"

    synthetic["hechos"] = [{
        "hecho_id": "H-SIN-001",
        "descripcion": "No se pudo extraer un hecho especifico; se conserva una fila sintetica para revisar el documento o el modelo usado.",
        "fragmento_fuente": "desconocido",
        "pagina": 0,
        "actores": [],
        "fecha_hecho": None,
        "confianza": 0.1,
    }]
    return synthetic, "vacío"


def _post_with_backoff(url: str, headers: dict[str, str], payload: dict[str, Any], *, action: str, source_id: Optional[str] = None, timeout: int = 120, max_retries: int = 3) -> tuple[requests.Response, int, int]:
    retries = 0
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if response.status_code not in (429, 500, 502, 503, 504):
                return response, attempt + 1, retries
            if attempt >= max_retries:
                return response, attempt + 1, retries
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after is not None else 2 ** attempt
            except Exception:
                delay = 2 ** attempt
            logger.warning("[%s] status=%s intento=%s source=%s", action, response.status_code, attempt + 1, source_id)
            retries += 1
            time.sleep(min(delay, 20))
        except requests.RequestException as exc:
            if attempt >= max_retries:
                raise
            delay = 2 ** attempt
            logger.warning("[%s] error=%s intento=%s source=%s", action, exc, attempt + 1, source_id)
            retries += 1
            time.sleep(min(delay, 20))
    raise RuntimeError(f"No se pudo completar la llamada a {action}")


def _extract_json_with_groq(prompt: str, *, action: str, source_id: Optional[str] = None, temperature: float = 0.1, model: str = GROQ_MODEL) -> tuple[Any, dict[str, Any]]:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY no configurada")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Responde solo con JSON valido, sin markdown ni texto adicional."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    started = time.time()
    response, attempts, retries = _post_with_backoff(GROQ_URL, headers, payload, action=action, source_id=source_id)
    meta = {
        "provider": "groq",
        "model": model,
        "action": action,
        "source_id": source_id,
        "timestamp": _utc_now(),
        "status_code": response.status_code,
        "elapsed_seconds": round(time.time() - started, 3),
        "retries": retries,
        "attempts": attempts,
        "fallback_used": False,
    }
    if not response.ok:
        raise RuntimeError(f"Groq devolvio {response.status_code}: {response.text}")
    content = response.json()["choices"][0]["message"]["content"]
    logger.info("[HPN] Respuesta cruda del LLM (%s/%s): %s", action, meta["provider"], content[:500])
    return _extract_json(content), meta


def _extract_json_with_gemini(prompt: str, *, action: str, source_id: Optional[str] = None, temperature: float = 0.1, model: str = "gemini-1.5-flash") -> tuple[Any, dict[str, Any]]:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY no configurada")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    headers = {"Content-Type": "application/json"}
    started = time.time()
    response, attempts, retries = _post_with_backoff(url, headers, payload, action=action, source_id=source_id)
    meta = {
        "provider": "gemini",
        "model": model,
        "action": action,
        "source_id": source_id,
        "timestamp": _utc_now(),
        "status_code": response.status_code,
        "elapsed_seconds": round(time.time() - started, 3),
        "retries": retries,
        "attempts": attempts,
        "fallback_used": False,
    }
    if not response.ok:
        raise RuntimeError(f"Gemini devolvio {response.status_code}: {response.text}")
    body = response.json()
    parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts)
    logger.info("[HPN] Respuesta cruda del LLM (%s/%s): %s", action, meta["provider"], text[:500])
    return _extract_json(text), meta


def _extract_json_with_hf(prompt: str, *, action: str, source_id: Optional[str] = None, temperature: float = 0.1, model: str = DEFAULT_HF_LEGAL_MODEL) -> tuple[Any, dict[str, Any]]:
    headers = {"Content-Type": "application/json"}
    if HF_API_TOKEN:
        headers["Authorization"] = f"Bearer {HF_API_TOKEN}"

    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": temperature,
            "max_new_tokens": 1024,
            "return_full_text": False,
        },
        "options": {
            "wait_for_model": True,
            "use_cache": False,
        },
    }

    started = time.time()
    response, attempts, retries = _post_with_backoff(f"{HF_URL}/{model}", headers, payload, action=action, source_id=source_id, timeout=180)
    meta = {
        "provider": "huggingface",
        "model": model,
        "action": action,
        "source_id": source_id,
        "timestamp": _utc_now(),
        "status_code": response.status_code,
        "elapsed_seconds": round(time.time() - started, 3),
        "retries": retries,
        "attempts": attempts,
        "fallback_used": False,
    }
    if not response.ok:
        raise RuntimeError(f"HuggingFace devolvio {response.status_code}: {response.text}")

    data = response.json()
    if isinstance(data, list) and data:
        text = data[0].get("generated_text") or data[0].get("summary_text") or ""
    elif isinstance(data, dict):
        text = data.get("generated_text") or data.get("summary_text") or data.get("text") or ""
    else:
        text = ""
    logger.info("[HPN] Respuesta cruda del LLM (%s/%s): %s", action, meta["provider"], text[:500])
    return _extract_json(str(text)), meta


def _run_json_model(prompt: str, *, model: str, action: str, source_id: Optional[str] = None, ollama_model: Optional[str] = None, hf_model: Optional[str] = None, temperature: float = 0.1) -> tuple[Any, dict[str, Any]]:
    normalized = resolve_effective_model(model)
    if normalized == "groq":
        try:
            return _extract_json_with_groq(prompt, action=action, source_id=source_id, temperature=temperature)
        except Exception as exc:
            logger.warning("[HPN] Groq fallo en %s: %s", action, exc)
    elif normalized == "gemini":
        try:
            return _extract_json_with_gemini(prompt, action=action, source_id=source_id, temperature=temperature)
        except Exception as exc:
            logger.warning("[HPN] Gemini fallo en %s: %s", action, exc)
    elif normalized in ("hf", "huggingface", "huggingface-legal"):
        hf_model = hf_model or DEFAULT_HF_LEGAL_MODEL
        try:
            return _extract_json_with_hf(prompt, action=action, source_id=source_id, temperature=temperature, model=hf_model)
        except Exception as exc:
            logger.warning("[HPN] Hugging Face fallo en %s: %s", action, exc)

    fallback_model = ollama_model or get_default_model()
    raw = call_ollama(
        prompt,
        model=fallback_model,
        temperature=temperature,
        system_prompt="Responde solo con JSON valido, sin markdown ni texto adicional.",
    )
    return _extract_json(raw), {
        "provider": "ollama",
        "model": fallback_model,
        "action": action,
        "source_id": source_id,
        "timestamp": _utc_now(),
        "status_code": None,
        "elapsed_seconds": 0.0,
        "retries": 0,
        "attempts": 1,
        "fallback_used": normalized != "ollama",
        "requested_model": model,
    }


def _source_context(source: Any) -> dict[str, Any]:
    if isinstance(source, dict):
        return {k: v for k, v in source.items() if v not in (None, "")}
    if source is None:
        return {}
    return {"fragmento_fuente": str(source)}


def extract_entities(
    text: str,
    model: str = "ollama",
    ollama_model: str | None = None,
    hf_model: str | None = None,
    source: Any = None,
    return_meta: bool = False,
) -> dict[str, list[dict[str, Any]]] | tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Extract hechos, pruebas and normas from a fragment of text."""

    logger.info("[HPN] extract_entities texto=%s chars source=%s", len(text), _source_label(source))

    prompt = (
        "Analiza el fragmento de expediente y extrae hechos, pruebas y normas.\n\n"
        f"SOURCE_CONTEXT: {json.dumps(_source_context(source), ensure_ascii=False)}\n\n"
        f"TEXTO:\n{truncar_texto(text)}\n\n"
        "Devuelve un JSON con las claves hechos, pruebas y normas."
    )
    try:
        raw, meta = _run_json_model(prompt, model=model, action="extract_entities", source_id=_source_label(source), ollama_model=ollama_model, hf_model=hf_model, temperature=0.05)
        result = _normalize_entities(raw, source)
    except Exception as exc:
        logger.warning("[HPN] Extraccion por modelo fallo, usando heuristica: %s", exc)
        result = _heuristic_entities(text, source)
        meta = {
            "provider": "heuristic",
            "model": "heuristic",
            "action": "extract_entities",
            "source_id": _source_label(source),
            "timestamp": _utc_now(),
            "status_code": None,
            "elapsed_seconds": 0.0,
            "retries": 0,
            "attempts": 1,
            "fallback_used": True,
            "error": str(exc),
        }

    meta["counts"] = {k: len(v) for k, v in result.items()}
    logger.info(
        "[HPN] extract_entities resultado hechos=%s pruebas=%s normas=%s",
        meta["counts"].get("hechos", 0),
        meta["counts"].get("pruebas", 0),
        meta["counts"].get("normas", 0),
    )
    if return_meta:
        return result, meta
    return result


def _match_by_source(items: list[dict[str, Any]], source_label: str) -> list[dict[str, Any]]:
    return [item for item in items if str(item.get("fragmento_fuente") or "") == source_label]


def _best_match(description: str, candidates: list[dict[str, Any]], key: str) -> Optional[str]:
    desc_tokens = set(re.findall(r"\w+", description.lower()))
    best_score = -1
    best_id = None
    for item in candidates:
        item_text = str(item.get("descripcion") or item.get("referencia") or "")
        score = len(desc_tokens & set(re.findall(r"\w+", item_text.lower())))
        if score > best_score:
            best_score = score
            best_id = item.get(key)
    return str(best_id) if best_id is not None else None


def _heuristic_matrix(entities: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    hechos = entities.get("hechos", [])
    pruebas = entities.get("pruebas", [])
    normas = entities.get("normas", [])
    matrix: list[dict[str, Any]] = []

    for idx, hecho in enumerate(hechos, start=1):
        source_label = str(hecho.get("fragmento_fuente") or "")
        proof_ids = [item.get("prueba_id") for item in _match_by_source(pruebas, source_label) if item.get("prueba_id")]
        norm_ids = [item.get("norma_id") for item in _match_by_source(normas, source_label) if item.get("norma_id")]

        if not proof_ids and pruebas:
            best = _best_match(str(hecho.get("descripcion", "")), pruebas, "prueba_id")
            if best:
                proof_ids = [best]
        if not norm_ids and normas:
            best = _best_match(str(hecho.get("descripcion", "")), normas, "norma_id")
            if best:
                norm_ids = [best]

        if proof_ids and norm_ids:
            estado, riesgo, accion = "probado", "bajo", "Mantener y reforzar esta linea argumental"
        elif proof_ids or norm_ids:
            estado, riesgo, accion = "controvertido", "medio", "Completar soporte antes de presentar como concluyente"
        else:
            estado, riesgo, accion = "sin_prueba", "alto", "Buscar soporte probatorio o retirar esta fila"

        matrix.append({
            "fila_id": f"F-{idx:03d}",
            "hecho_id": str(hecho.get("hecho_id")),
            "prueba_ids": [str(v) for v in proof_ids if v],
            "norma_ids": [str(v) for v in norm_ids if v],
            "elemento_juridico": "Hecho procesal identificado",
            "fuente_expediente": _fuente_from_hecho(hecho),
            "contradicciones": [],
            "agente_responsable": "heuristica",
            "revision_humana": "pendiente",
            "estado_epistemico": estado,
            "riesgo": riesgo,
            "accion_sugerida": accion,
            "notas": f"Fuente principal: {source_label or 'desconocida'}",
        })

    return matrix


def build_hpn_matrix(
    entities: dict[str, list[dict[str, Any]]],
    model: str = "ollama",
    ollama_model: str | None = None,
    hf_model: str | None = None,
    return_meta: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the HPN matrix from extracted entities."""

    logger.info(
        "[HPN] build_hpn_matrix entrada hechos=%s pruebas=%s normas=%s",
        len(entities.get("hechos", [])),
        len(entities.get("pruebas", [])),
        len(entities.get("normas", [])),
    )

    prompt = (
        "Construye la matriz HPN a partir de este JSON de entidades.\n\n"
        f"ENTIDADES:\n{json.dumps(entities, ensure_ascii=False)}\n\n"
        f"{M5_JSON_SCHEMA_HINT}"
    )
    try:
        raw, meta = _run_json_model(prompt, model=model, action="build_hpn_matrix", ollama_model=ollama_model, hf_model=hf_model, temperature=0.1)
        filas = _ensure_list(_ensure_dict(raw, {}).get("filas_hpn"))
        matrix = []
        for idx, fila in enumerate(filas, start=1):
            if not isinstance(fila, dict):
                continue
            matrix.append(_normalize_row(fila, idx, entities))
        if not matrix:
            raise ValueError("La respuesta no contiene filas_hpn")
        matrix = _enriquecer_vinculos(entities, matrix)
        meta["agente_responsable"] = "agente_hpn_m5"
    except Exception as exc:
        logger.warning("[HPN] Construccion de matriz fallo, usando heuristica: %s", exc)
        matrix = _enriquecer_vinculos(entities, _heuristic_matrix(entities))
        meta = {
            "provider": "heuristic",
            "model": "heuristic",
            "action": "build_hpn_matrix",
            "source_id": None,
            "timestamp": _utc_now(),
            "status_code": None,
            "elapsed_seconds": 0.0,
            "retries": 0,
            "attempts": 1,
            "fallback_used": True,
            "error": str(exc),
        }

    if not matrix:
        anchored_entities, anchor_kind = _synthetic_anchor_entities(entities)
        matrix = _enriquecer_vinculos(anchored_entities, _heuristic_matrix(anchored_entities))
        if not matrix:
            matrix = [_normalize_row({
                "fila_id": "F-001",
                "hecho_id": "H-SIN-001",
                "prueba_ids": [],
                "norma_ids": [],
                "elemento_juridico": "Revision manual requerida",
                "estado_epistemico": "por_evaluar",
                "riesgo": "alto",
                "accion_sugerida": "Revisar el documento o cambiar de modelo/proveedor.",
                "notas": f"Fallback sintetico activado ({anchor_kind}).",
                "agente_responsable": "heuristica",
            }, 1, entities, agente="heuristica")]
            meta["fallback_used"] = True

    meta["rows"] = len(matrix)
    logger.info("[HPN] build_hpn_matrix filas=%s", len(matrix))
    if return_meta:
        return matrix, meta
    return matrix


def _entities_by_id(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(item.get(key)): item for item in items if item.get(key)}


def _audit_rules(matrix: list[dict[str, Any]], entities: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    facts = _entities_by_id(entities.get("hechos", []), "hecho_id")
    proofs = _entities_by_id(entities.get("pruebas", []), "prueba_id")
    norms = _entities_by_id(entities.get("normas", []), "norma_id")
    alerts: list[dict[str, Any]] = []
    seen = set()
    seen_hecho_desc: dict[str, str] = {}

    for hecho in entities.get("hechos", []):
        hid = str(hecho.get("hecho_id") or "")
        desc = _clean(str(hecho.get("descripcion") or "")).lower()
        if not hecho.get("fragmento_fuente") and not hecho.get("pagina"):
            alerts.append({
                "severidad": "alta",
                "codigo": "SIN_FUENTE",
                "hecho_id": hid,
                "mensaje": "El hecho no tiene fragmento_fuente ni pagina.",
            })
        if desc and desc in seen_hecho_desc and seen_hecho_desc[desc] != hid:
            alerts.append({
                "severidad": "media",
                "codigo": "ENTIDAD_DUPLICADA",
                "hecho_id": hid,
                "mensaje": f"Descripcion duplicada con hecho {seen_hecho_desc[desc]}.",
            })
        elif desc:
            seen_hecho_desc[desc] = hid

    for prueba in entities.get("pruebas", []):
        pid = str(prueba.get("prueba_id") or "")
        if not prueba.get("fragmento_fuente") and not prueba.get("pagina"):
            alerts.append({
                "severidad": "alta",
                "codigo": "SIN_FUENTE",
                "prueba_id": pid,
                "mensaje": "La prueba no tiene fragmento_fuente ni pagina.",
            })

    for norma in entities.get("normas", []):
        nid = str(norma.get("norma_id") or "")
        if not norma.get("fragmento_fuente") and not norma.get("pagina") and not norma.get("es_inferida"):
            alerts.append({
                "severidad": "alta",
                "codigo": "SIN_FUENTE",
                "norma_id": nid,
                "mensaje": "La norma no tiene fragmento_fuente ni pagina.",
            })

    for row in matrix:
        row_id = str(row.get("fila_id") or "sin_id")
        hecho_id = str(row.get("hecho_id") or "")
        proof_ids = [str(v) for v in _ensure_list(row.get("prueba_ids")) if v]
        norm_ids = [str(v) for v in _ensure_list(row.get("norma_ids")) if v]
        estado = str(row.get("estado_epistemico") or "")
        signature = (hecho_id, tuple(sorted(proof_ids)), tuple(sorted(norm_ids)))
        if signature in seen:
            alerts.append({"severidad": "media", "codigo": "FILA_DUPLICADA", "fila_id": row_id, "mensaje": "La fila repite una combinacion ya vista."})
        seen.add(signature)

        if hecho_id and hecho_id not in facts:
            alerts.append({"severidad": "alta", "codigo": "HECHO_NO_ENCONTRADO", "fila_id": row_id, "hecho_id": hecho_id, "mensaje": "La fila referencia un hecho inexistente."})
        if not proof_ids:
            alerts.append({"severidad": "alta", "codigo": "FILA_SIN_PRUEBA", "fila_id": row_id, "mensaje": "La fila no contiene pruebas asociadas."})
        if not norm_ids:
            alerts.append({"severidad": "alta", "codigo": "FILA_SIN_NORMA", "fila_id": row_id, "mensaje": "La fila no contiene normas asociadas."})
        if estado == "probado" and not proof_ids:
            alerts.append({
                "severidad": "alta",
                "codigo": "ESTADO_INCONSISTENTE",
                "fila_id": row_id,
                "mensaje": "Estado probado pero la fila no tiene pruebas asociadas.",
            })

        for proof_id in proof_ids:
            if proof_id not in proofs:
                alerts.append({"severidad": "alta", "codigo": "PRUEBA_NO_ENCONTRADA", "fila_id": row_id, "prueba_id": proof_id, "mensaje": "La fila referencia una prueba inexistente."})

        for norm_id in norm_ids:
            norma = norms.get(norm_id)
            if norma is None:
                alerts.append({"severidad": "alta", "codigo": "NORMA_NO_ENCONTRADA", "fila_id": row_id, "norma_id": norm_id, "mensaje": "La fila referencia una norma inexistente."})
                continue
            if norma.get("es_inferida"):
                alerts.append({
                    "severidad": "media",
                    "codigo": "NORMA_INFERIDA",
                    "fila_id": row_id,
                    "norma_id": norm_id,
                    "mensaje": "La norma referenciada fue inferida y requiere verificacion.",
                })
            fuente = str(norma.get("fragmento_fuente") or "").strip().lower()
            if norma.get("es_inferida") and not fuente:
                alerts.append({"severidad": "alta", "codigo": "NORMA_SIN_FUENTE", "fila_id": row_id, "norma_id": norm_id, "mensaje": "La norma esta marcada como inferida o sin fuente explicitada."})
            if fuente.startswith("inventad"):
                alerts.append({"severidad": "critica", "codigo": "NORMA_INVENTADA", "fila_id": row_id, "norma_id": norm_id, "mensaje": "Se detecto una fuente declarada como inventada."})

    return alerts


def audit_hpn_matrix(
    matrix: list[dict[str, Any]],
    entities: dict[str, list[dict[str, Any]]],
    model: str = "ollama",
    ollama_model: str | None = None,
    return_meta: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
    """Audit the HPN matrix and return actionable alerts."""

    alerts = _audit_rules(matrix, entities)
    meta = {
        "provider": "deterministic",
        "model": "rules",
        "action": "audit_hpn_matrix",
        "source_id": None,
        "timestamp": _utc_now(),
        "status_code": None,
        "elapsed_seconds": 0.0,
        "retries": 0,
        "attempts": 1,
        "fallback_used": False,
        "alerts": len(alerts),
    }
    if return_meta:
        return alerts, meta
    return alerts


def extract_hpn_matrix_from_fragments(
    fragmentos: list[dict[str, Any]],
    *,
    caso_id: str | None = None,
    model: str = "auto",
    ollama_model: str | None = None,
    hf_model: str | None = None,
    pausa_segundos: float = 1.5,
    return_meta: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    """Pipeline M4 -> M5 -> M8 procesando cada fragmento del expediente."""

    effective_model = resolve_effective_model(model)
    logger.info(
        "[HPN] extract_hpn_matrix_from_fragments fragmentos=%s model=%s effective=%s caso=%s",
        len(fragmentos),
        model,
        effective_model,
        caso_id,
    )

    entidades_totales: dict[str, list[dict[str, Any]]] = {"hechos": [], "pruebas": [], "normas": []}
    trazas_m4: list[dict[str, Any]] = []

    for idx, frag in enumerate(fragmentos):
        texto = str(frag.get("texto") or "").strip()
        if len(texto) < 20:
            continue
        source = frag if isinstance(frag, dict) else {"fragmento_fuente": f"frag-{idx}"}
        logger.info("[HPN] M4 fragmento %s/%s (%s chars)", idx + 1, len(fragmentos), len(texto))

        res, meta = extract_entities(
            texto,
            model=model,
            ollama_model=ollama_model,
            hf_model=hf_model,
            source=source,
            return_meta=True,
        )
        trazas_m4.append(meta)
        entidades_totales["hechos"].extend(res.get("hechos", []))
        entidades_totales["pruebas"].extend(res.get("pruebas", []))
        entidades_totales["normas"].extend(res.get("normas", []))

        if effective_model == "groq" and pausa_segundos > 0 and idx < len(fragmentos) - 1:
            time.sleep(pausa_segundos)

    entities = _deduplicate_entities(entidades_totales)
    matrix, meta_m5 = build_hpn_matrix(
        entities,
        model=model,
        ollama_model=ollama_model,
        hf_model=hf_model,
        return_meta=True,
    )
    alerts, meta_m8 = audit_hpn_matrix(matrix, entities, return_meta=True)

    result = {
        "hechos": entities.get("hechos", []),
        "pruebas": entities.get("pruebas", []),
        "normas": entities.get("normas", []),
        "filas_hpn": matrix,
        "auditoria": alerts,
        "trazas": {"m4": trazas_m4, "m5": meta_m5, "m8": meta_m8},
        "caso_id": caso_id or str(uuid.uuid4())[:8],
        "fragmentos_procesados": len(fragmentos),
        "modelo_solicitado": model,
        "modelo_efectivo": effective_model,
    }

    logger.info(
        "[HPN] extract_hpn_matrix_from_fragments fin hechos=%s pruebas=%s normas=%s filas=%s alertas=%s",
        len(result["hechos"]),
        len(result["pruebas"]),
        len(result["normas"]),
        len(result["filas_hpn"]),
        len(result["auditoria"]),
    )

    if return_meta:
        return result, {"m4": trazas_m4, "m5": meta_m5, "m8": meta_m8}
    return result


def extract_hpn_matrix(
    text: str,
    model: str = "ollama",
    ollama_model: str | None = None,
    hf_model: str | None = None,
    source: Any = None,
    return_meta: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    """Full M4 -> M5 -> M8 pipeline for a case or a fragment bundle."""

    logger.info("[HPN] extract_hpn_matrix inicio chars=%s model=%s source=%s", len(text), model, _source_label(source))

    if source is None:
        source = {"fragmento_fuente": f"texto-{_short_hash(text)}"}

    entities, meta_m4 = extract_entities(text, model=model, ollama_model=ollama_model, hf_model=hf_model, source=source, return_meta=True)
    entities = _deduplicate_entities(entities)
    matrix, meta_m5 = build_hpn_matrix(entities, model=model, ollama_model=ollama_model, hf_model=hf_model, return_meta=True)
    alerts, meta_m8 = audit_hpn_matrix(matrix, entities, model=model, ollama_model=ollama_model, return_meta=True)

    result = {
        "hechos": entities.get("hechos", []),
        "pruebas": entities.get("pruebas", []),
        "normas": entities.get("normas", []),
        "filas_hpn": matrix,
        "auditoria": alerts,
        "trazas": [meta_m4, meta_m5, meta_m8],
        "caso_id": str(uuid.uuid4())[:8],
        "modelo_solicitado": model,
        "modelo_efectivo": resolve_effective_model(model),
    }

    logger.info(
        "[HPN] extract_hpn_matrix fin hechos=%s pruebas=%s normas=%s filas=%s alertas=%s",
        len(result["hechos"]),
        len(result["pruebas"]),
        len(result["normas"]),
        len(result["filas_hpn"]),
        len(result["auditoria"]),
    )

    if return_meta:
        return result, {"m4": meta_m4, "m5": meta_m5, "m8": meta_m8}
    return result
