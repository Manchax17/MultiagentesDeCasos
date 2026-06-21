"""
Gestión del almacenamiento por zonas.

Implementa la separación por rutas definida en la sección 4 del plan:
  /docs/       → expedientes originales (solo lectura para agentes)
  /workspace/  → artefactos generados durante la ejecución
  /audit/      → logs y trazas (append-only)
  /scratch/    → temporales por hilo
  /memories/   → memorias validadas (futuro)
  /skills/     → skills jurídicas reutilizables (futuro)
"""

from __future__ import annotations

import os
from pathlib import Path

# Raíz del almacenamiento — configurable vía variable de entorno
_DATA_ROOT = Path(
    os.environ.get(
        "TCA_DATA_ROOT",
        Path(__file__).resolve().parent.parent.parent / "data"
    )
)


def _zone(name: str) -> Path:
    """Crea y devuelve la ruta de una zona de almacenamiento."""
    p = _DATA_ROOT / name
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Zonas públicas ──────────────────────────
DOCS_DIR      = _zone("docs")       # Expedientes originales — solo lectura
WORKSPACE_DIR = _zone("workspace")  # Artefactos generados
AUDIT_DIR     = _zone("audit")      # Logs y trazas — append-only
SCRATCH_DIR   = _zone("scratch")    # Temporales por hilo
MEMORIES_DIR  = _zone("memories")   # Memorias validadas
SKILLS_DIR    = _zone("skills")     # Skills reutilizables


def caso_docs_dir(caso_id: str) -> Path:
    """Directorio de documentos para un caso específico."""
    p = DOCS_DIR / caso_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def caso_workspace_dir(caso_id: str) -> Path:
    """Directorio de trabajo para un caso específico."""
    p = WORKSPACE_DIR / caso_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def caso_audit_dir(caso_id: str) -> Path:
    """Directorio de auditoría para un caso específico."""
    p = AUDIT_DIR / caso_id
    p.mkdir(parents=True, exist_ok=True)
    return p
