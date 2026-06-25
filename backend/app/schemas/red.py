"""
M6 — Esquemas de la red compleja multicapa.

Define los contratos de nodos, aristas y métricas estructurales que se
construyen de forma determinística a partir de la matriz HPN (M5).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# ── Capas de la red ─────────────────────────
CAPAS = (
    "hechos",
    "pruebas",
    "normas",
    "actores",
    "tiempo",
    "elementos",
    "riesgos",
)

# ── Tipos de relación (sección 6.3 del proyecto) ──
TIPOS_RELACION = (
    "soporta",
    "contradice",
    "activa",
    "fundamenta",
    "precede",
    "riesgo",
    "participa",
)


class NodoRed(BaseModel):
    """Un nodo tipado por capa dentro de la red multicapa."""
    id: str
    capa: str = Field(..., description="hechos | pruebas | normas | actores | tiempo | elementos | riesgos")
    label: str
    estado: Optional[str] = Field(default=None, description="Estado epistémico o de soporte del nodo")
    riesgo: Optional[str] = Field(default=None, description="bajo | medio | alto | critico")
    pagina: Optional[int] = None
    fragmento_id: Optional[str] = None


class AristaRed(BaseModel):
    """Una arista dirigida y tipada entre dos nodos de la red."""
    source: str
    target: str
    tipo: str = Field(..., description="soporta | contradice | activa | fundamenta | precede | riesgo | participa")
    capa_origen: str
    capa_destino: str
    peso: float = Field(default=1.0, ge=0.0)
    evidencia: Optional[dict] = Field(default=None, description="Página/fragmento de respaldo")


class MetricaNodo(BaseModel):
    """Métricas estructurales calculadas por nodo."""
    id: str
    capa: str
    label: str
    grado: int = 0
    centralidad_intermediacion: float = 0.0
    centralidad_grado: float = 0.0
    es_punto_unico_falla: bool = False
    fragilidad: float = Field(
        default=0.0,
        description="Caída de cobertura de rutas al eliminar el nodo (solo pruebas)",
    )
    hechos_soportados: int = Field(default=0, description="Hechos que soporta (solo pruebas)")


class MetricasRed(BaseModel):
    """Métricas globales de la red compleja multicapa (sección 6 del proyecto)."""
    n_nodos: int = 0
    n_aristas: int = 0
    n_nodos_por_capa: dict = Field(default_factory=dict)
    n_aristas_por_tipo: dict = Field(default_factory=dict)
    densidad: float = 0.0
    densidad_soporte: float = Field(
        default=0.0, description="Aristas 'soporta' por hecho esencial"
    )
    cobertura_rutas_juridicas: float = Field(
        default=0.0, description="% de rutas prueba→hecho→norma→elemento completas"
    )
    indice_contradiccion: float = Field(
        default=0.0, description="Proporción de aristas 'contradice'"
    )
    redundancia_probatoria: float = Field(
        default=0.0, description="Promedio de pruebas independientes por hecho"
    )
    puntos_unicos_falla: list[str] = Field(default_factory=list)
    pruebas_criticas: list[str] = Field(
        default_factory=list, description="Pruebas con mayor fragilidad / centralidad"
    )


class RedMulticapa(BaseModel):
    """Artefacto A2 — red compleja multicapa exportable."""
    caso_id: str
    nodos: list[NodoRed] = Field(default_factory=list)
    aristas: list[AristaRed] = Field(default_factory=list)
    metricas: MetricasRed = Field(default_factory=MetricasRed)
    metricas_nodos: list[MetricaNodo] = Field(default_factory=list)
