"""
M0 — Esquemas del estado canónico del caso (CaseState).

Estos esquemas se usarán más adelante cuando se implementen los demás módulos
(extracción, matriz HPN, red, simulación, auditoría). Se definen ahora como
parte del contrato global del sistema.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Entidades futuras (stubs para M4-M8)
# ──────────────────────────────────────────────

class Hecho(BaseModel):
    """Un hecho identificado en el expediente."""
    hecho_id: str
    descripcion: str
    fragmento_fuente: str = Field(..., description="ID del fragmento de origen")
    pagina: int
    actores: list[str] = Field(default_factory=list)
    fecha_hecho: Optional[str] = None
    confianza: float = Field(default=1.0, ge=0.0, le=1.0)


class Prueba(BaseModel):
    """Una prueba identificada en el expediente."""
    prueba_id: str
    tipo: str
    descripcion: str
    fragmento_fuente: str
    pagina: int
    estado: str = Field(default="admitida")
    confianza: float = Field(default=1.0, ge=0.0, le=1.0)


class Norma(BaseModel):
    """Una norma jurídica referenciada en el expediente."""
    norma_id: str
    referencia: str = Field(..., description="Artículo, ley o código referenciado")
    descripcion: str
    fragmento_fuente: Optional[str] = Field(
        default=None,
        description="None si la norma fue inferida por el sistema"
    )
    pagina: Optional[int] = None
    es_inferida: bool = Field(
        default=False,
        description="True si la norma no aparece explícitamente en el expediente"
    )


class FuenteExpediente(BaseModel):
    """Referencia trazable al fragmento del expediente."""
    pagina: Optional[int] = None
    fragmento_id: Optional[str] = None


class HPNRow(BaseModel):
    """Fila de la matriz Hecho-Prueba-Norma."""
    fila_id: str
    hecho_id: str
    prueba_ids: list[str] = Field(default_factory=list)
    norma_ids: list[str] = Field(default_factory=list)
    elemento_juridico: Optional[str] = Field(
        default=None,
        description="Pretensión, defensa, requisito o punto de decisión",
    )
    fuente_expediente: Optional[FuenteExpediente] = None
    contradicciones: list[str] = Field(default_factory=list)
    agente_responsable: str = Field(default="agente_hpn_m5")
    revision_humana: str = Field(
        default="pendiente",
        description="pendiente | revisado | corregido | aprobado | rechazado",
    )
    estado_epistemico: str = Field(
        default="por_evaluar",
        description="probado | controvertido | sin_prueba | por_evaluar"
    )
    riesgo: str = Field(default="medio", description="bajo | medio | alto | critico")
    accion_sugerida: Optional[str] = None
    notas: Optional[str] = None


class CaseState(BaseModel):
    """
    Estado canónico del caso.
    Compartido por todos los nodos del grafo de LangGraph.
    """
    caso_id: str
    expediente_index: Optional[dict] = None
    hechos: list[Hecho] = Field(default_factory=list)
    pruebas: list[Prueba] = Field(default_factory=list)
    normas: list[Norma] = Field(default_factory=list)
    matriz_hpn: list[HPNRow] = Field(default_factory=list)
    graph: Optional[dict] = None
    escenarios: list[dict] = Field(default_factory=list)
    auditoria: list[dict] = Field(default_factory=list)
    trazas: list[dict] = Field(default_factory=list)
