"""
Aplicación principal FastAPI — Teoría del Caso Aumentada.

Backend para el sistema multiagente de análisis de expedientes judiciales.
Módulo actual: Subida y procesamiento de PDFs (M1 + M3).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import expedientes, chat, hpn

# ── Logging ─────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)

# ── App ─────────────────────────────────────
app = FastAPI(
    title="Teoría del Caso Aumentada — API",
    description=(
        "Backend del sistema multiagente para teoría del caso.\n\n"
        "**Módulos activos:**\n"
        "- M0: Esquemas y contratos de datos\n"
        "- M1: Esqueleto de backend\n"
        "- M3: Ingesta del expediente (Intake)\n"
        "- M4/M5: Agentes de Extracción y Construcción Matriz HPN\n"
        "- Chatbot: RAG Simple\n\n"
        "**Modelos soportados:**\n"
        "- Groq (Llama-3)\n"
        "- Gemini (Flash)\n"
        "- Ollama (Local)\n\n"
        "**Funcionalidades:**\n"
        "- Subida y limpieza de expedientes en PDF\n"
        "- Segmentación semántica en fragmentos trazables\n"
        "- Detección de secciones jurídicas\n"
        "- Consulta paginada de fragmentos con filtros\n"
        "- Construcción, consulta y edición de Matriz HPN\n"
        "- Chat interactivo con recuperación de contexto"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:4321",
        "http://localhost:5173",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4321",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────
app.include_router(expedientes.router)
app.include_router(chat.router)
app.include_router(hpn.router)


# ── Health Check ────────────────────────────
@app.get("/health", tags=["Sistema"])
async def healthcheck():
    """Verifica que el servidor está activo."""
    return {
        "status": "ok",
        "service": "teoria-caso-aumentada",
        "version": "0.1.0",
        "modulos_activos": ["M0-esquemas", "M1-backend", "M3-intake"],
    }
