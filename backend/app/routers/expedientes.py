"""
Router de expedientes — Subida y procesamiento de PDFs.

Endpoints:
  POST   /api/expedientes/subir          → Subir un PDF
  POST   /api/expedientes/{id}/procesar  → Procesar (ingestar) el PDF
  GET    /api/expedientes/{id}/estado     → Estado del caso
  GET    /api/expedientes/{id}/fragmentos → Listar fragmentos
  GET    /api/expedientes/{id}/fragmentos/{frag_id} → Fragmento completo
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ..schemas.expediente import (
    EstadoCaso,
    EstadoIngesta,
    RespuestaFragmentoCompleto,
    RespuestaIngesta,
    RespuestaListaFragmentos,
    RespuestaSubidaPDF,
    ResumenFragmento,
    TipoSeccion,
)
from ..services.intake import procesar_pdf
from ..services.storage import caso_docs_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/expedientes", tags=["Expedientes"])

# ──────────────────────────────────────────────
# Almacén en memoria (será reemplazado por DB en futuros módulos)
# ──────────────────────────────────────────────
_casos: dict[str, dict] = {}


@router.post(
    "/subir",
    response_model=RespuestaSubidaPDF,
    status_code=201,
    summary="Subir un expediente en PDF",
    description="Recibe un archivo PDF y lo almacena en la zona /docs/ del caso.",
)
async def subir_pdf(archivo: UploadFile = File(..., description="Archivo PDF del expediente")):
    """
    Sube un expediente judicial en formato PDF.
    
    El archivo se almacena en /docs/{caso_id}/ sin modificación alguna
    (zona de solo lectura para los agentes).
    """
    # Validar tipo de archivo
    if not archivo.filename or not archivo.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan archivos PDF (.pdf)"
        )

    if archivo.content_type and archivo.content_type != "application/pdf":
        # Algunos navegadores envían content types incorrectos, solo advertir
        logger.warning(
            f"Content-Type inesperado: {archivo.content_type} "
            f"(se esperaba application/pdf)"
        )

    # Generar ID de caso
    caso_id = str(uuid.uuid4())[:8]

    # Leer contenido
    contenido = await archivo.read()
    tamano = len(contenido)

    if tamano == 0:
        raise HTTPException(status_code=400, detail="El archivo PDF está vacío")

    # Límite de tamaño: 50 MB
    if tamano > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="El archivo excede el límite de 50 MB"
        )

    # Guardar en zona /docs/ (solo lectura para agentes)
    docs_dir = caso_docs_dir(caso_id)
    ruta_pdf = docs_dir / archivo.filename
    ruta_pdf.write_bytes(contenido)

    # Contar páginas con PyMuPDF
    import fitz
    try:
        doc = fitz.open(str(ruta_pdf))
        total_paginas = len(doc)
        doc.close()
    except Exception:
        total_paginas = 0

    # Registrar caso en memoria
    _casos[caso_id] = {
        "caso_id": caso_id,
        "nombre_archivo": archivo.filename,
        "ruta_pdf": str(ruta_pdf),
        "tamano_bytes": tamano,
        "total_paginas": total_paginas,
        "estado_ingesta": EstadoIngesta.PENDIENTE,
        "fecha_creacion": datetime.utcnow(),
        "fecha_procesamiento": None,
        "indice": None,
    }

    logger.info(f"[Upload] PDF guardado: {archivo.filename} (caso: {caso_id}, {tamano} bytes, {total_paginas} págs)")

    return RespuestaSubidaPDF(
        caso_id=caso_id,
        nombre_archivo=archivo.filename,
        tamano_bytes=tamano,
        total_paginas=total_paginas,
        mensaje=f"PDF recibido correctamente. Use POST /api/expedientes/{caso_id}/procesar para iniciar la ingesta.",
    )


@router.post(
    "/{caso_id}/procesar",
    response_model=RespuestaIngesta,
    summary="Procesar (ingestar) el expediente",
    description="Segmenta el PDF en fragmentos trazables con detección semántica de secciones.",
)
async def procesar_expediente(caso_id: str):
    """
    Ejecuta la ingesta del expediente: segmentación semántica del PDF,
    detección de secciones, y generación de fragmentos trazables.
    """
    if caso_id not in _casos:
        raise HTTPException(status_code=404, detail=f"Caso {caso_id} no encontrado")

    caso = _casos[caso_id]

    if caso["estado_ingesta"] == EstadoIngesta.COMPLETADO:
        raise HTTPException(
            status_code=409,
            detail="El expediente ya fue procesado. Use GET para consultar los resultados."
        )

    # Marcar como en proceso
    caso["estado_ingesta"] = EstadoIngesta.EN_PROCESO

    try:
        ruta_pdf = Path(caso["ruta_pdf"])
        indice = procesar_pdf(ruta_pdf, caso_id)

        caso["estado_ingesta"] = indice.estado
        caso["fecha_procesamiento"] = datetime.utcnow()
        caso["indice"] = indice
        caso["total_fragmentos"] = indice.metadata.total_fragmentos

        return RespuestaIngesta(
            caso_id=caso_id,
            estado=indice.estado,
            total_fragmentos=indice.metadata.total_fragmentos,
            total_paginas=indice.metadata.total_paginas,
            total_caracteres=indice.metadata.total_caracteres,
            secciones_detectadas=indice.metadata.secciones_detectadas,
            metodo_extraccion=indice.metadata.metodo_extraccion,
            errores=indice.errores,
            mensaje=(
                f"Ingesta completada: {indice.metadata.total_fragmentos} fragmentos "
                f"extraídos de {indice.metadata.total_paginas} páginas."
                if indice.estado == EstadoIngesta.COMPLETADO
                else f"Error en la ingesta: {'; '.join(indice.errores)}"
            ),
        )

    except Exception as e:
        caso["estado_ingesta"] = EstadoIngesta.ERROR
        logger.error(f"[Intake] Error procesando caso {caso_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error en la ingesta: {str(e)}")


@router.get(
    "/{caso_id}/estado",
    response_model=EstadoCaso,
    summary="Consultar estado del caso",
)
async def obtener_estado(caso_id: str):
    """Devuelve el estado actual del caso."""
    if caso_id not in _casos:
        raise HTTPException(status_code=404, detail=f"Caso {caso_id} no encontrado")

    caso = _casos[caso_id]
    return EstadoCaso(
        caso_id=caso_id,
        nombre_archivo=caso["nombre_archivo"],
        estado_ingesta=caso["estado_ingesta"],
        total_paginas=caso.get("total_paginas", 0),
        total_fragmentos=caso.get("total_fragmentos", 0),
        fecha_creacion=caso["fecha_creacion"],
        fecha_procesamiento=caso.get("fecha_procesamiento"),
    )


@router.get(
    "/{caso_id}/fragmentos",
    response_model=RespuestaListaFragmentos,
    summary="Listar fragmentos del expediente",
)
async def listar_fragmentos(
    caso_id: str,
    seccion: Optional[TipoSeccion] = Query(None, description="Filtrar por sección"),
    pagina: Optional[int] = Query(None, ge=1, description="Filtrar por página"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Devuelve una lista paginada de fragmentos con vista previa.
    Permite filtrar por sección y/o página.
    """
    if caso_id not in _casos:
        raise HTTPException(status_code=404, detail=f"Caso {caso_id} no encontrado")

    caso = _casos[caso_id]
    if not caso.get("indice"):
        raise HTTPException(
            status_code=409,
            detail="El expediente aún no ha sido procesado"
        )

    fragmentos = caso["indice"].fragmentos

    # Aplicar filtros
    if seccion:
        fragmentos = [f for f in fragmentos if f.seccion == seccion]
    if pagina:
        fragmentos = [f for f in fragmentos if f.pagina == pagina]

    total = len(fragmentos)
    fragmentos_paginados = fragmentos[offset:offset + limit]

    return RespuestaListaFragmentos(
        caso_id=caso_id,
        total=total,
        fragmentos=[
            ResumenFragmento(
                fragmento_id=f.fragmento_id,
                pagina=f.pagina,
                seccion=f.seccion,
                caracteres=f.caracteres,
                preview=f.texto[:200] + ("..." if len(f.texto) > 200 else ""),
            )
            for f in fragmentos_paginados
        ],
    )


@router.get(
    "/{caso_id}/fragmentos/{fragmento_id}",
    response_model=RespuestaFragmentoCompleto,
    summary="Obtener fragmento completo",
)
async def obtener_fragmento(caso_id: str, fragmento_id: str):
    """Devuelve un fragmento completo con todo su texto."""
    if caso_id not in _casos:
        raise HTTPException(status_code=404, detail=f"Caso {caso_id} no encontrado")

    caso = _casos[caso_id]
    if not caso.get("indice"):
        raise HTTPException(
            status_code=409,
            detail="El expediente aún no ha sido procesado"
        )

    for frag in caso["indice"].fragmentos:
        if frag.fragmento_id == fragmento_id:
            return RespuestaFragmentoCompleto(
                caso_id=caso_id,
                fragmento=frag,
            )

    raise HTTPException(
        status_code=404,
        detail=f"Fragmento {fragmento_id} no encontrado en el caso {caso_id}"
    )


@router.get(
    "",
    summary="Listar todos los casos",
)
async def listar_casos():
    """Devuelve la lista de todos los casos registrados."""
    return [
        EstadoCaso(
            caso_id=c["caso_id"],
            nombre_archivo=c["nombre_archivo"],
            estado_ingesta=c["estado_ingesta"],
            total_paginas=c.get("total_paginas", 0),
            total_fragmentos=c.get("total_fragmentos", 0),
            fecha_creacion=c["fecha_creacion"],
            fecha_procesamiento=c.get("fecha_procesamiento"),
        )
        for c in _casos.values()
    ]
