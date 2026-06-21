"""
M3 — Servicio de ingesta del expediente (Intake).

Lee el PDF real, lo segmenta por señales semánticas (no por página fija)
y produce fragmentos trazables. Cada fragmento conserva:
  - Número de página de origen
  - Hash SHA-256 del contenido
  - Sección detectada semánticamente
  - Índice secuencial

Estrategia de extracción:
  1. PyMuPDF (fitz) como estrategia principal para PDF de texto puro
  2. pdfplumber como fallback si se detectan tablas o columnas
  3. OCR (futuro) solo si el PDF resulta escaneado

Control: No debe alterar el sentido del expediente; cada fragmento
debe ser reconstruible hasta la página de origen.
"""

from __future__ import annotations

import json
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from ..schemas.expediente import (
    EstadoIngesta,
    FragmentoExpediente,
    IndiceExpediente,
    MetadataExpediente,
    TipoSeccion,
)
from .storage import caso_workspace_dir, caso_audit_dir

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Patrones de detección de secciones
# ──────────────────────────────────────────────

_SECCION_PATTERNS: list[tuple[re.Pattern, TipoSeccion]] = [
    (re.compile(r"\bhechos\b", re.IGNORECASE), TipoSeccion.HECHOS),
    (re.compile(r"\bpretension(?:es)?\b", re.IGNORECASE), TipoSeccion.PRETENSIONES),
    (re.compile(r"\bprueba(?:s)?\b", re.IGNORECASE), TipoSeccion.PRUEBAS),
    (re.compile(r"\bfundamento(?:s)?\s+(?:de\s+)?derecho\b", re.IGNORECASE), TipoSeccion.FUNDAMENTOS_DERECHO),
    (re.compile(r"\bcontestaci[oó]n\b", re.IGNORECASE), TipoSeccion.CONTESTACION),
    (re.compile(r"\bsentencia\b", re.IGNORECASE), TipoSeccion.SENTENCIA),
    (re.compile(r"\brecurso\b", re.IGNORECASE), TipoSeccion.RECURSO),
    (re.compile(r"\bnotificaci[oó]n\b", re.IGNORECASE), TipoSeccion.NOTIFICACION),
    (re.compile(r"\bacta\b", re.IGNORECASE), TipoSeccion.ACTA),
    (re.compile(r"\bperit(?:aje|o|icial)\b", re.IGNORECASE), TipoSeccion.PERITAJE),
    (re.compile(r"\banexo(?:s)?\b", re.IGNORECASE), TipoSeccion.ANEXO),
    (re.compile(r"\bcar[aá]tula\b", re.IGNORECASE), TipoSeccion.CARATULA),
]


def _detectar_seccion(texto: str) -> TipoSeccion:
    """
    Detecta el tipo de sección de un fragmento basándose en señales
    semánticas del texto. Busca en las primeras líneas del fragmento
    para mayor precisión.
    """
    # Analizar las primeras 5 líneas como encabezado potencial
    lineas_encabezado = "\n".join(texto.strip().split("\n")[:5])

    for pattern, tipo in _SECCION_PATTERNS:
        if pattern.search(lineas_encabezado):
            return tipo

    # Si no se encuentra en el encabezado, buscar en todo el texto
    # pero con menor confianza (solo si hay indicadores fuertes)
    for pattern, tipo in _SECCION_PATTERNS:
        matches = pattern.findall(texto)
        if len(matches) >= 3:  # Requiere múltiples menciones
            return tipo

    return TipoSeccion.DESCONOCIDO


def _limpiar_texto(texto: str) -> str:
    """Limpia el texto extraído sin alterar su significado."""
    # Normalizar saltos de línea excesivos
    texto = re.sub(r"\n{4,}", "\n\n\n", texto)
    # Eliminar espacios al final de las líneas
    texto = re.sub(r"[ \t]+$", "", texto, flags=re.MULTILINE)
    # No eliminar espacios al inicio (pueden indicar estructura)
    return texto.strip()


def _es_separador_semantico(linea: str) -> bool:
    """
    Determina si una línea actúa como separador semántico
    (encabezado de sección, línea divisoria, etc.)
    """
    linea = linea.strip()
    if not linea:
        return False

    # Líneas de puros guiones, asteriscos, etc.
    if re.match(r"^[-=*_]{3,}$", linea):
        return True

    # Encabezados con numeración (CAPÍTULO I, Artículo 3, etc.)
    if re.match(r"^(CAP[IÍ]TULO|ART[IÍ]CULO|SECCI[OÓ]N|T[IÍ]TULO)\s", linea, re.IGNORECASE):
        return True

    # Encabezados en mayúsculas de más de 3 palabras
    if linea.isupper() and len(linea.split()) >= 3 and len(linea) < 100:
        return True

    return False


def _segmentar_pagina(
    texto_pagina: str,
    max_chars: int = 2000,
    min_chars: int = 100,
) -> list[str]:
    """
    Segmenta el texto de una página en fragmentos semánticos.

    Estrategia:
    1. Primero intenta dividir por separadores semánticos
    2. Si los fragmentos son demasiado largos, divide por párrafos
    3. Si aún son demasiado largos, divide por oraciones
    4. Nunca corta en medio de una oración
    """
    if len(texto_pagina.strip()) < min_chars:
        return [texto_pagina.strip()] if texto_pagina.strip() else []

    # Paso 1: Dividir por párrafos (doble salto de línea)
    parrafos = re.split(r"\n\s*\n", texto_pagina)
    parrafos = [p.strip() for p in parrafos if p.strip()]

    if not parrafos:
        return []

    # Paso 2: Agrupar párrafos en fragmentos respetando max_chars
    fragmentos: list[str] = []
    buffer = ""

    for parrafo in parrafos:
        # Si el párrafo solo es un separador, forzar corte
        if _es_separador_semantico(parrafo):
            if buffer.strip():
                fragmentos.append(buffer.strip())
            buffer = parrafo + "\n\n"
            continue

        # Si añadir el párrafo excede el máximo, guardar el buffer actual
        if buffer and len(buffer) + len(parrafo) > max_chars:
            fragmentos.append(buffer.strip())
            buffer = parrafo + "\n\n"
        else:
            buffer += parrafo + "\n\n"

    if buffer.strip():
        fragmentos.append(buffer.strip())

    return fragmentos


def procesar_pdf(
    ruta_pdf: Path,
    caso_id: str,
    max_chars_fragmento: int = 2000,
    min_chars_fragmento: int = 50,
) -> IndiceExpediente:
    """
    Procesa un PDF y genera un índice de fragmentos trazables.

    Args:
        ruta_pdf: Ruta absoluta al archivo PDF.
        caso_id: Identificador del caso.
        max_chars_fragmento: Máximo de caracteres por fragmento.
        min_chars_fragmento: Mínimo de caracteres para considerar un fragmento válido.

    Returns:
        IndiceExpediente con todos los fragmentos y metadatos.

    Raises:
        FileNotFoundError: Si el PDF no existe.
        ValueError: Si el PDF no contiene texto extraíble.
    """
    if not ruta_pdf.exists():
        raise FileNotFoundError(f"PDF no encontrado: {ruta_pdf}")

    logger.info(f"[Intake] Procesando PDF: {ruta_pdf.name} (caso: {caso_id})")

    errores: list[str] = []
    fragmentos: list[FragmentoExpediente] = []
    total_caracteres = 0
    metodo = "pymupdf"
    idx_fragmento = 0

    try:
        doc = fitz.open(str(ruta_pdf))
    except Exception as e:
        logger.error(f"[Intake] Error al abrir PDF: {e}")
        return IndiceExpediente(
            caso_id=caso_id,
            metadata=MetadataExpediente(
                nombre_archivo=ruta_pdf.name,
                total_paginas=0,
                total_fragmentos=0,
                total_caracteres=0,
                metodo_extraccion=metodo,
            ),
            estado=EstadoIngesta.ERROR,
            errores=[f"Error al abrir PDF: {str(e)}"],
        )

    total_paginas = len(doc)
    paginas_sin_texto = 0

    for num_pagina in range(total_paginas):
        page = doc[num_pagina]
        texto_pagina = page.get_text("text")

        if not texto_pagina or len(texto_pagina.strip()) < 10:
            paginas_sin_texto += 1
            if paginas_sin_texto == total_paginas:
                errores.append(
                    "El PDF parece ser escaneado (sin texto extraíble). "
                    "Se requiere OCR para procesarlo."
                )
            continue

        texto_limpio = _limpiar_texto(texto_pagina)
        segmentos = _segmentar_pagina(
            texto_limpio,
            max_chars=max_chars_fragmento,
            min_chars=min_chars_fragmento,
        )

        for segmento in segmentos:
            if len(segmento.strip()) < min_chars_fragmento:
                continue

            frag = FragmentoExpediente(
                fragmento_id=FragmentoExpediente.generar_id(segmento, num_pagina + 1),
                pagina=num_pagina + 1,
                texto=segmento,
                hash_contenido=FragmentoExpediente.calcular_hash(segmento),
                seccion=_detectar_seccion(segmento),
                numero_fragmento=idx_fragmento,
                caracteres=len(segmento),
            )
            fragmentos.append(frag)
            total_caracteres += len(segmento)
            idx_fragmento += 1

    doc.close()

    # Detectar secciones únicas
    secciones = sorted(set(f.seccion.value for f in fragmentos))

    # Si hubo demasiadas páginas sin texto, advertir
    if paginas_sin_texto > 0 and paginas_sin_texto < total_paginas:
        errores.append(
            f"{paginas_sin_texto} de {total_paginas} páginas no contienen "
            f"texto extraíble (podrían ser imágenes o estar escaneadas)."
        )

    indice = IndiceExpediente(
        caso_id=caso_id,
        metadata=MetadataExpediente(
            nombre_archivo=ruta_pdf.name,
            total_paginas=total_paginas,
            total_fragmentos=len(fragmentos),
            total_caracteres=total_caracteres,
            secciones_detectadas=secciones,
            metodo_extraccion=metodo,
        ),
        fragmentos=fragmentos,
        estado=EstadoIngesta.COMPLETADO if fragmentos else EstadoIngesta.ERROR,
        errores=errores,
    )

    # Persistir artefactos en workspace
    _guardar_artefactos(caso_id, indice)

    # Registrar en audit
    _registrar_audit(caso_id, indice)

    logger.info(
        f"[Intake] Completado: {len(fragmentos)} fragmentos, "
        f"{total_paginas} páginas, {total_caracteres} caracteres"
    )

    return indice


def _guardar_artefactos(caso_id: str, indice: IndiceExpediente) -> None:
    """Persiste los artefactos de la ingesta en el workspace del caso."""
    workspace = caso_workspace_dir(caso_id)

    # Guardar índice completo
    indice_path = workspace / "expediente_index.json"
    with open(indice_path, "w", encoding="utf-8") as f:
        json.dump(indice.model_dump(mode="json"), f, ensure_ascii=False, indent=2, default=str)

    # Guardar fragmentos en JSONL (formato eficiente para procesamiento posterior)
    fragmentos_path = workspace / "fragmentos.jsonl"
    with open(fragmentos_path, "w", encoding="utf-8") as f:
        for frag in indice.fragmentos:
            f.write(json.dumps(frag.model_dump(mode="json"), ensure_ascii=False) + "\n")

    logger.info(f"[Intake] Artefactos guardados en {workspace}")


def _registrar_audit(caso_id: str, indice: IndiceExpediente) -> None:
    """Registra la operación de ingesta en el log de auditoría (append-only)."""
    audit_dir = caso_audit_dir(caso_id)
    audit_path = audit_dir / "intake.log"

    registro = {
        "timestamp": datetime.utcnow().isoformat(),
        "operacion": "ingesta_pdf",
        "caso_id": caso_id,
        "archivo": indice.metadata.nombre_archivo,
        "total_paginas": indice.metadata.total_paginas,
        "total_fragmentos": indice.metadata.total_fragmentos,
        "total_caracteres": indice.metadata.total_caracteres,
        "estado": indice.estado.value,
        "errores": indice.errores,
        "metodo": indice.metadata.metodo_extraccion,
    }

    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
