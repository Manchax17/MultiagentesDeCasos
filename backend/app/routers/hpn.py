from fastapi import APIRouter, HTTPException
import json
from pathlib import Path
from ..services.hpn_agents import extract_hpn_matrix

router = APIRouter(prefix="/api/expedientes", tags=["Matriz HPN"])
WORKSPACE_DIR = Path("data/workspace")

@router.post("/{caso_id}/matriz")
async def generar_matriz_hpn(caso_id: str):
    """Ejecuta los agentes M4/M5 para generar la matriz HPN a partir del texto del expediente."""
    caso_dir = WORKSPACE_DIR / caso_id
    if not caso_dir.exists():
        raise HTTPException(status_code=404, detail="Caso no encontrado")
        
    text_file = caso_dir / "documento_completo.txt"
    if not text_file.exists():
        raise HTTPException(status_code=400, detail="Documento completo no disponible para este caso")
        
    texto = text_file.read_text(encoding="utf-8")
    
    try:
        matriz = extract_hpn_matrix(texto)
        
        # Guardar en el workspace
        out_file = caso_dir / "matriz_hpn.json"
        out_file.write_text(json.dumps({"matriz": matriz}, indent=2, ensure_ascii=False), encoding="utf-8")
        
        return {"status": "success", "matriz": matriz}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{caso_id}/matriz")
async def obtener_matriz_hpn(caso_id: str):
    """Obtiene la matriz HPN si ya fue generada."""
    caso_dir = WORKSPACE_DIR / caso_id
    out_file = caso_dir / "matriz_hpn.json"
    
    if not out_file.exists():
        return {"matriz": None} # Devolvemos None si no existe aún, para que el front sepa que debe generarla
        
    data = json.loads(out_file.read_text(encoding="utf-8"))
    return {"matriz": data.get("matriz", [])}
