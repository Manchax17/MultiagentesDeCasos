"""
Router de la Matriz HPN — Generación, consulta, edición y exportación.

Endpoints:
  POST   /api/expedientes/{id}/matriz              → Generar matriz HPN (M4/M5/M8)
  GET    /api/expedientes/{id}/matriz              → Obtener matriz HPN
  GET    /api/expedientes/{id}/matriz/export       → Exportar CSV o JSON
  PUT    /api/expedientes/{id}/matriz/{fila}       → Editar fila HPN
  DELETE /api/expedientes/{id}/matriz/{fila}       → Eliminar fila HPN
"""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..schemas.caso import HPNRow
from ..services.hpn_agents import audit_hpn_matrix, extract_hpn_matrix_from_fragments
from ..services.storage import caso_workspace_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/expedientes", tags=["Matriz HPN"])

ESTADOS_VALIDOS = ("probado", "controvertido", "sin_prueba", "por_evaluar")
RIESGOS_VALIDOS = ("bajo", "medio", "alto", "critico")


class GenerarMatrizRequest(BaseModel):
    model: str = "auto"  # auto | groq | ollama | gemini | huggingface
    ollama_model: str | None = None
    hf_model: str | None = None
    max_fragmentos: int | None = Field(default=None, ge=1, le=500)
    pausa_segundos: float = Field(default=1.5, ge=0.0, le=10.0)


class EditarFilaRequest(BaseModel):
    estado_epistemico: Optional[str] = None
    riesgo: Optional[str] = None
    accion_sugerida: Optional[str] = None
    notas: Optional[str] = None
    elemento_juridico: Optional[str] = None
    revision_humana: Optional[str] = None


def _get_workspace(caso_id: str) -> Path:
    return caso_workspace_dir(caso_id)


def _leer_matriz(caso_id: str) -> Optional[dict]:
    path = _get_workspace(caso_id) / "matriz_hpn.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _guardar_matriz(caso_id: str, data: dict) -> None:
    data["caso_id"] = caso_id
    path = _get_workspace(caso_id) / "matriz_hpn.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _reauditar(data: dict) -> dict:
    alerts = audit_hpn_matrix(data.get("filas_hpn", []), {
        "hechos": data.get("hechos", []),
        "pruebas": data.get("pruebas", []),
        "normas": data.get("normas", []),
    })
    data["auditoria"] = alerts
    return data


def _cargar_fragmentos(caso_id: str, max_fragmentos: int | None = None) -> list[dict]:
    ws = _get_workspace(caso_id)
    jsonl_path = ws / "fragmentos.jsonl"

    if jsonl_path.exists():
        fragmentos = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    fragmentos.append(json.loads(line))
        if fragmentos:
            if max_fragmentos is not None:
                fragmentos = fragmentos[:max_fragmentos]
            logger.info("[HPN] %s fragmentos cargados desde jsonl", len(fragmentos))
            return fragmentos

    index_path = ws / "expediente_index.json"
    if index_path.exists():
        data = json.loads(index_path.read_text(encoding="utf-8"))
        fragmentos = data.get("fragmentos", [])
        if max_fragmentos is not None:
            fragmentos = fragmentos[:max_fragmentos]
        if fragmentos:
            logger.info("[HPN] %s fragmentos cargados desde expediente_index.json", len(fragmentos))
            return fragmentos

    raise FileNotFoundError(
        "No se encontraron fragmentos para este caso. "
        "Asegúrese de haber subido y procesado el PDF primero."
    )


def _matriz_a_csv(data: dict) -> str:
    hechos = {h["hecho_id"]: h for h in data.get("hechos", []) if h.get("hecho_id")}
    pruebas = {p["prueba_id"]: p for p in data.get("pruebas", []) if p.get("prueba_id")}
    normas = {n["norma_id"]: n for n in data.get("normas", []) if n.get("norma_id")}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "fila_id", "elemento_juridico", "hecho_id", "hecho_descripcion",
        "prueba_ids", "prueba_descripciones", "norma_ids", "norma_referencias",
        "pagina", "fragmento_id", "estado_epistemico", "riesgo",
        "accion_sugerida", "contradicciones", "agente_responsable", "revision_humana", "notas",
    ])

    for fila in data.get("filas_hpn", []):
        hecho = hechos.get(fila.get("hecho_id"), {})
        proof_ids = fila.get("prueba_ids") or []
        norm_ids = fila.get("norma_ids") or []
        fuente = fila.get("fuente_expediente") or {}
        writer.writerow([
            fila.get("fila_id", ""),
            fila.get("elemento_juridico", ""),
            fila.get("hecho_id", ""),
            hecho.get("descripcion", ""),
            ";".join(proof_ids),
            ";".join(pruebas.get(pid, {}).get("descripcion", pid) for pid in proof_ids),
            ";".join(norm_ids),
            ";".join(normas.get(nid, {}).get("referencia", nid) for nid in norm_ids),
            fuente.get("pagina", hecho.get("pagina", "")),
            fuente.get("fragmento_id", hecho.get("fragmento_fuente", "")),
            fila.get("estado_epistemico", ""),
            fila.get("riesgo", ""),
            fila.get("accion_sugerida", ""),
            ";".join(fila.get("contradicciones") or []),
            fila.get("agente_responsable", ""),
            fila.get("revision_humana", ""),
            fila.get("notas", ""),
        ])

    return output.getvalue()


@router.post("/{caso_id}/matriz")
async def generar_matriz_hpn(caso_id: str, req: GenerarMatrizRequest = GenerarMatrizRequest()):
    """
    Ejecuta M4 (por fragmento) -> M5 -> M8 para generar la Matriz HPN.
    """
    try:
        fragmentos = _cargar_fragmentos(caso_id, req.max_fragmentos)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not fragmentos:
        raise HTTPException(status_code=400, detail="No hay fragmentos procesables en el expediente.")

    try:
        resultado = extract_hpn_matrix_from_fragments(
            fragmentos,
            caso_id=caso_id,
            model=req.model,
            ollama_model=req.ollama_model,
            hf_model=req.hf_model,
            pausa_segundos=req.pausa_segundos,
        )
        _guardar_matriz(caso_id, resultado)

        logger.info(
            "[HPN] Matriz generada para caso %s: %s hechos, %s pruebas, %s normas, %s filas, %s alertas",
            caso_id,
            len(resultado.get("hechos", [])),
            len(resultado.get("pruebas", [])),
            len(resultado.get("normas", [])),
            len(resultado.get("filas_hpn", [])),
            len(resultado.get("auditoria", [])),
        )
        return {"status": "success", **resultado}

    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("[HPN] Error generando matriz: %s", e)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/{caso_id}/matriz")
async def obtener_matriz_hpn(caso_id: str):
    """Obtiene la Matriz HPN si ya fue generada."""
    data = _leer_matriz(caso_id)
    if data is None:
        return {
            "hechos": None,
            "pruebas": None,
            "normas": None,
            "filas_hpn": None,
            "auditoria": None,
        }
    return data


@router.get("/{caso_id}/matriz/export")
async def exportar_matriz_hpn(
    caso_id: str,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
):
    """Exporta la matriz HPN en CSV o JSON (entregable E4)."""
    data = _leer_matriz(caso_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Matriz HPN no encontrada")

    if format == "json":
        return data

    csv_content = _matriz_a_csv(data)
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="matriz_hpn_{caso_id}.csv"'},
    )


@router.put("/{caso_id}/matriz/{fila_id}")
async def editar_fila_hpn(caso_id: str, fila_id: str, req: EditarFilaRequest):
    """Edita una fila específica y re-ejecuta auditoría M8."""
    data = _leer_matriz(caso_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Matriz HPN no encontrada")

    fila_encontrada = None
    for fila in data.get("filas_hpn", []):
        if fila.get("fila_id") == fila_id:
            fila_encontrada = fila
            break

    if not fila_encontrada:
        raise HTTPException(status_code=404, detail=f"Fila {fila_id} no encontrada")

    if req.estado_epistemico is not None:
        if req.estado_epistemico not in ESTADOS_VALIDOS:
            raise HTTPException(status_code=400, detail="estado_epistemico inválido")
        fila_encontrada["estado_epistemico"] = req.estado_epistemico

    if req.riesgo is not None:
        if req.riesgo not in RIESGOS_VALIDOS:
            raise HTTPException(status_code=400, detail="riesgo inválido")
        fila_encontrada["riesgo"] = req.riesgo

    if req.accion_sugerida is not None:
        fila_encontrada["accion_sugerida"] = req.accion_sugerida
    if req.notas is not None:
        fila_encontrada["notas"] = req.notas
    if req.elemento_juridico is not None:
        fila_encontrada["elemento_juridico"] = req.elemento_juridico

    fila_encontrada["revision_humana"] = req.revision_humana or "corregido"

    try:
        HPNRow.model_validate(fila_encontrada)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fila inválida: {e}")

    data = _reauditar(data)
    _guardar_matriz(caso_id, data)
    return {"status": "updated", "fila": fila_encontrada, "auditoria": data.get("auditoria", [])}


@router.delete("/{caso_id}/matriz/{fila_id}")
async def eliminar_fila_hpn(caso_id: str, fila_id: str):
    """Elimina una fila y re-ejecuta auditoría M8."""
    data = _leer_matriz(caso_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Matriz HPN no encontrada")

    filas = data.get("filas_hpn", [])
    nuevas_filas = [f for f in filas if f.get("fila_id") != fila_id]

    if len(nuevas_filas) == len(filas):
        raise HTTPException(status_code=404, detail=f"Fila {fila_id} no encontrada")

    data["filas_hpn"] = nuevas_filas
    data = _reauditar(data)
    _guardar_matriz(caso_id, data)
    return {"status": "deleted", "fila_id": fila_id, "auditoria": data.get("auditoria", [])}
