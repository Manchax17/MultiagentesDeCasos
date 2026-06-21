"""
M0 — Esquemas para la ingesta del expediente (Intake).

Define los contratos de datos para el procesamiento del PDF:
fragmentos, índice del expediente y respuestas de la API.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class EstadoIngesta(str, Enum):
    """Estado del proceso de ingesta de un expediente."""
    PENDIENTE = "pendiente"
    EN_PROCESO = "en_proceso"
    COMPLETADO = "completado"
    ERROR = "error"


class TipoSeccion(str, Enum):
    """Tipos de sección detectables en un expediente judicial."""
    CARATULA = "caratula"
    HECHOS = "hechos"
    PRETENSIONES = "pretensiones"
    PRUEBAS = "pruebas"
    FUNDAMENTOS_DERECHO = "fundamentos_de_derecho"
    CONTESTACION = "contestacion"
    SENTENCIA = "sentencia"
    RECURSO = "recurso"
    NOTIFICACION = "notificacion"
    ACTA = "acta"
    PERITAJE = "peritaje"
    ANEXO = "anexo"
    DESCONOCIDO = "desconocido"


# ──────────────────────────────────────────────
# Fragmento de expediente
# ──────────────────────────────────────────────

class FragmentoExpediente(BaseModel):
    """
    Un fragmento trazable del expediente.
    Cada fragmento conserva su ubicación exacta en el PDF original
    para garantizar la trazabilidad exigida por el proyecto.
    """
    fragmento_id: str = Field(
        ...,
        description="Identificador único del fragmento (formato: frag-{hash_corto})"
    )
    pagina: int = Field(
        ..., ge=1,
        description="Número de página en el PDF original (1-indexed)"
    )
    pagina_fin: Optional[int] = Field(
        default=None, ge=1,
        description="Página final si el fragmento abarca múltiples páginas"
    )
    texto: str = Field(
        ..., min_length=1,
        description="Contenido textual del fragmento"
    )
    hash_contenido: str = Field(
        ...,
        description="SHA-256 del texto para verificación de integridad"
    )
    seccion: TipoSeccion = Field(
        default=TipoSeccion.DESCONOCIDO,
        description="Tipo de sección detectada semánticamente"
    )
    numero_fragmento: int = Field(
        ..., ge=0,
        description="Índice secuencial del fragmento dentro del expediente"
    )
    caracteres: int = Field(
        ..., ge=0,
        description="Número de caracteres en el fragmento"
    )

    @staticmethod
    def calcular_hash(texto: str) -> str:
        """Calcula el SHA-256 de un texto para verificación de integridad."""
        return hashlib.sha256(texto.encode("utf-8")).hexdigest()

    @staticmethod
    def generar_id(texto: str, pagina: int) -> str:
        """Genera un ID único basado en contenido y ubicación."""
        raw = f"{pagina}:{texto[:100]}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"frag-{h}"


# ──────────────────────────────────────────────
# Índice del expediente
# ──────────────────────────────────────────────

class MetadataExpediente(BaseModel):
    """Metadatos del expediente procesado."""
    nombre_archivo: str
    total_paginas: int = Field(..., ge=1)
    total_fragmentos: int = Field(..., ge=0)
    total_caracteres: int = Field(..., ge=0)
    secciones_detectadas: list[str] = Field(default_factory=list)
    fecha_procesamiento: datetime = Field(default_factory=datetime.utcnow)
    metodo_extraccion: str = Field(
        default="pymupdf",
        description="Método usado para extraer texto (pymupdf | pdfplumber | ocr)"
    )


class IndiceExpediente(BaseModel):
    """
    Índice completo del expediente procesado.
    Contiene los metadatos y todos los fragmentos producidos por la ingesta.
    """
    caso_id: str
    metadata: MetadataExpediente
    fragmentos: list[FragmentoExpediente] = Field(default_factory=list)
    estado: EstadoIngesta = Field(default=EstadoIngesta.PENDIENTE)
    errores: list[str] = Field(default_factory=list)


# ──────────────────────────────────────────────
# Respuestas de API
# ──────────────────────────────────────────────

class RespuestaSubidaPDF(BaseModel):
    """Respuesta tras subir un PDF exitosamente."""
    caso_id: str
    nombre_archivo: str
    tamano_bytes: int
    total_paginas: int
    mensaje: str = "PDF recibido y almacenado correctamente"


class RespuestaIngesta(BaseModel):
    """Respuesta tras procesar (ingestar) el expediente."""
    caso_id: str
    estado: EstadoIngesta
    total_fragmentos: int
    total_paginas: int
    total_caracteres: int
    secciones_detectadas: list[str]
    metodo_extraccion: str
    errores: list[str] = Field(default_factory=list)
    mensaje: str


class ResumenFragmento(BaseModel):
    """Vista resumida de un fragmento (sin texto completo)."""
    fragmento_id: str
    pagina: int
    seccion: TipoSeccion
    caracteres: int
    preview: str = Field(
        ...,
        description="Primeros 200 caracteres del fragmento"
    )


class RespuestaListaFragmentos(BaseModel):
    """Respuesta paginada de fragmentos."""
    caso_id: str
    total: int
    fragmentos: list[ResumenFragmento]


class RespuestaFragmentoCompleto(BaseModel):
    """Respuesta con el fragmento completo incluyendo texto."""
    caso_id: str
    fragmento: FragmentoExpediente


class EstadoCaso(BaseModel):
    """Estado general de un caso en el sistema."""
    caso_id: str
    nombre_archivo: str
    estado_ingesta: EstadoIngesta
    total_paginas: int = 0
    total_fragmentos: int = 0
    fecha_creacion: datetime
    fecha_procesamiento: Optional[datetime] = None
