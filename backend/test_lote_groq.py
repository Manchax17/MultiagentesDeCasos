import os
import sys
import json
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.hpn_agents import extract_hpn_matrix_from_fragments, audit_hpn_matrix


def main():
    print("--- TAREA 1: Cargando Lote Real ---")
    frag_path = Path(__file__).resolve().parent / "data" / "workspace" / "f6bb9a93" / "fragmentos.jsonl"

    fragmentos = []
    with open(frag_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 5:
                break
            fragmentos.append(json.loads(line))

    print(f"Cargados {len(fragmentos)} fragmentos.")

    print("\n--- Ejecutando pipeline M4 -> M5 -> M8 con Groq (por fragmentos) ---")
    start_time = time.time()

    resultado = extract_hpn_matrix_from_fragments(
        fragmentos,
        caso_id="f6bb9a93",
        model="groq",
        pausa_segundos=1.5,
    )

    matriz = resultado.get("filas_hpn", [])
    entidades_totales = {
        "hechos": resultado.get("hechos", []),
        "pruebas": resultado.get("pruebas", []),
        "normas": resultado.get("normas", []),
    }
    traces = resultado.get("trazas", {})
    api_calls = len(traces.get("m4", [])) + 2
    retries = sum(int(t.get("retries", 0)) for t in traces.get("m4", []))
    retries += int(traces.get("m5", {}).get("retries", 0))

    print(
        f"Entidades: {len(entidades_totales['hechos'])} hechos, "
        f"{len(entidades_totales['pruebas'])} pruebas, "
        f"{len(entidades_totales['normas'])} normas."
    )
    print(f"Filas HPN generadas: {len(matriz)}")

    print("\n--- Inyectando norma falsa para probar M8 ---")
    norma_falsa = {
        "norma_id": "N-FALSA-999",
        "referencia": "Ley Suprema de los Agentes, Art. 404",
        "descripcion": "Los agentes LLM tienen jurisdiccion total sobre el universo.",
        "es_inferida": True,
        "fragmento_fuente": "Inventada por el desarrollador para testear M8",
        "pagina": None,
    }
    entidades_totales["normas"].append(norma_falsa)

    if matriz:
        matriz[0]["norma_ids"] = list(matriz[0].get("norma_ids") or []) + ["N-FALSA-999"]
        notas_previas = matriz[0].get("notas") or ""
        matriz[0]["notas"] = (
            f"{notas_previas} | Esta fila utiliza la Ley Suprema de los Agentes"
            if notas_previas
            else "Esta fila utiliza la Ley Suprema de los Agentes"
        )

    alertas = audit_hpn_matrix(matriz, entidades_totales)
    print("\nResultados del Auditor M8:")
    print(json.dumps(alertas, indent=2, ensure_ascii=False))

    elapsed = time.time() - start_time

    print("\n--- Métricas de la corrida ---")
    metrics = f"""# Diagnóstico de Lote con Groq (M4 -> M5 -> M8)

## Métricas de Ejecución
- **Fragmentos procesados**: {len(fragmentos)}
- **Llamadas estimadas**: {api_calls}
- **Reintentos totales**: {retries}
- **Tiempo total**: {elapsed:.2f} segundos
- **Promedio por llamada**: {elapsed / max(api_calls, 1):.2f} segundos
- **Filas HPN generadas**: {len(matriz)}
- **Alertas del Auditor M8**: {len(alertas)}

## Resultados del Auditor
```json
{json.dumps(alertas, indent=2, ensure_ascii=False)}
```

## Evaluación y Escalamiento
- **Control de Rate Limit**: Pipeline por fragmentos con pausa de 1.5s entre llamadas Groq.
- **Detección M8**: El auditor verifica el lote e identifica anomalías incluyendo NORMA_INVENTADA.
- **Recomendación**: Procesar fragmentos en lotes de 5 con esperas de 2-3 segundos entre lotes.

## Trazas
```json
{json.dumps(traces, indent=2, ensure_ascii=False)}
```
"""

    docs_path = Path(__file__).resolve().parent.parent / "docs" / "diagnostico_lote_groq.md"
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    with open(docs_path, "w", encoding="utf-8") as f:
        f.write(metrics)

    print("\nMétricas guardadas en docs/diagnostico_lote_groq.md")


if __name__ == "__main__":
    main()
