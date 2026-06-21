"""
M6 — Router de la Red compleja multicapa.

Endpoints:
  POST   /api/expedientes/{id}/red              → Generar red + métricas
  GET    /api/expedientes/{id}/red              → Obtener red generada
  GET    /api/expedientes/{id}/red/metricas     → Solo métricas
  GET    /api/expedientes/{id}/red/export       → Exportar GraphML | GEXF | JSON
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from ..services.red_multicapa import exportar_grafo, generar_red_completa
from ..services.storage import caso_workspace_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/expedientes", tags=["Red Multicapa"])


def _workspace(caso_id: str) -> Path:
    return caso_workspace_dir(caso_id)


def _leer_matriz(caso_id: str) -> Optional[dict]:
    path = _workspace(caso_id) / "matriz_hpn.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _leer_red(caso_id: str) -> Optional[dict]:
    path = _workspace(caso_id) / "red_multicapa.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _guardar_red(caso_id: str, data: dict) -> None:
    path = _workspace(caso_id) / "red_multicapa.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@router.post("/{caso_id}/red")
async def generar_red(caso_id: str):
    """Construye la red multicapa desde la matriz HPN y calcula sus métricas."""
    matriz = _leer_matriz(caso_id)
    if matriz is None:
        raise HTTPException(
            status_code=400,
            detail="No existe matriz HPN para este caso. Genere la Matriz HPN primero.",
        )
    if not matriz.get("filas_hpn"):
        raise HTTPException(status_code=400, detail="La matriz HPN no tiene filas.")

    try:
        red = generar_red_completa(matriz, caso_id)
    except Exception as e:
        logger.error("[RED] Error generando red: %s", e)
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")

    _guardar_red(caso_id, red)
    logger.info(
        "[RED] caso %s: %s nodos, %s aristas, cobertura=%s",
        caso_id, red["metricas"]["n_nodos"], red["metricas"]["n_aristas"],
        red["metricas"]["cobertura_rutas_juridicas"],
    )
    return {"status": "success", **red}


@router.get("/{caso_id}/red")
async def obtener_red(caso_id: str):
    """Obtiene la red multicapa si ya fue generada."""
    red = _leer_red(caso_id)
    if red is None:
        return {"nodos": None, "aristas": None, "metricas": None, "metricas_nodos": None}
    return red


@router.get("/{caso_id}/red/metricas")
async def obtener_metricas(caso_id: str):
    """Devuelve solo las métricas de la red (global y por nodo)."""
    red = _leer_red(caso_id)
    if red is None:
        raise HTTPException(status_code=404, detail="Red no generada")
    return {
        "metricas": red.get("metricas"),
        "metricas_nodos": red.get("metricas_nodos"),
    }


@router.get("/{caso_id}/red/export")
async def exportar_red(
    caso_id: str,
    format: str = Query(default="json", pattern="^(json|graphml|gexf)$"),
):
    """Exporta la red multicapa (entregable E5) en JSON, GraphML o GEXF."""
    red = _leer_red(caso_id)
    if red is None:
        raise HTTPException(status_code=404, detail="Red no generada")

    if format == "json":
        return red

    content = exportar_grafo(red, format)
    ext = "graphml" if format == "graphml" else "gexf"
    media = "application/xml; charset=utf-8"
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="red_multicapa_{caso_id}.{ext}"'},
    )
