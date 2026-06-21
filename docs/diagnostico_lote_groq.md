# Diagnóstico de Lote con Groq (M4 -> M5 -> M8)

## Métricas de Ejecución
- **Fragmentos procesados**: 5
- **Llamadas a Groq**: 7
- **Reintentos totales**: 5
- **Tiempo total**: 81.83 segundos
- **Promedio por llamada**: 11.69 segundos
- **Filas HPN generadas**: 10
- **Alertas del Auditor M8**: 28

## Resultados del Auditor
```json
[
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_PRUEBA",
    "fila_id": "F-001",
    "mensaje": "La fila no contiene pruebas asociadas."
  },
  {
    "severidad": "alta",
    "codigo": "NORMA_NO_ENCONTRADA",
    "fila_id": "F-001",
    "norma_id": "N-FALSA-999",
    "mensaje": "La fila referencia una norma inexistente."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_PRUEBA",
    "fila_id": "F-002",
    "mensaje": "La fila no contiene pruebas asociadas."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_NORMA",
    "fila_id": "F-002",
    "mensaje": "La fila no contiene normas asociadas."
  },
  {
    "severidad": "media",
    "codigo": "FILA_DUPLICADA",
    "fila_id": "F-003",
    "mensaje": "La fila repite una combinacion ya vista."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_PRUEBA",
    "fila_id": "F-003",
    "mensaje": "La fila no contiene pruebas asociadas."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_NORMA",
    "fila_id": "F-003",
    "mensaje": "La fila no contiene normas asociadas."
  },
  {
    "severidad": "media",
    "codigo": "FILA_DUPLICADA",
    "fila_id": "F-004",
    "mensaje": "La fila repite una combinacion ya vista."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_PRUEBA",
    "fila_id": "F-004",
    "mensaje": "La fila no contiene pruebas asociadas."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_NORMA",
    "fila_id": "F-004",
    "mensaje": "La fila no contiene normas asociadas."
  },
  {
    "severidad": "media",
    "codigo": "FILA_DUPLICADA",
    "fila_id": "F-005",
    "mensaje": "La fila repite una combinacion ya vista."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_PRUEBA",
    "fila_id": "F-005",
    "mensaje": "La fila no contiene pruebas asociadas."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_NORMA",
    "fila_id": "F-005",
    "mensaje": "La fila no contiene normas asociadas."
  },
  {
    "severidad": "media",
    "codigo": "FILA_DUPLICADA",
    "fila_id": "F-006",
    "mensaje": "La fila repite una combinacion ya vista."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_PRUEBA",
    "fila_id": "F-006",
    "mensaje": "La fila no contiene pruebas asociadas."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_NORMA",
    "fila_id": "F-006",
    "mensaje": "La fila no contiene normas asociadas."
  },
  {
    "severidad": "media",
    "codigo": "FILA_DUPLICADA",
    "fila_id": "F-007",
    "mensaje": "La fila repite una combinacion ya vista."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_PRUEBA",
    "fila_id": "F-007",
    "mensaje": "La fila no contiene pruebas asociadas."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_NORMA",
    "fila_id": "F-007",
    "mensaje": "La fila no contiene normas asociadas."
  },
  {
    "severidad": "media",
    "codigo": "FILA_DUPLICADA",
    "fila_id": "F-008",
    "mensaje": "La fila repite una combinacion ya vista."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_PRUEBA",
    "fila_id": "F-008",
    "mensaje": "La fila no contiene pruebas asociadas."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_NORMA",
    "fila_id": "F-008",
    "mensaje": "La fila no contiene normas asociadas."
  },
  {
    "severidad": "media",
    "codigo": "FILA_DUPLICADA",
    "fila_id": "F-009",
    "mensaje": "La fila repite una combinacion ya vista."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_PRUEBA",
    "fila_id": "F-009",
    "mensaje": "La fila no contiene pruebas asociadas."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_NORMA",
    "fila_id": "F-009",
    "mensaje": "La fila no contiene normas asociadas."
  },
  {
    "severidad": "media",
    "codigo": "FILA_DUPLICADA",
    "fila_id": "F-010",
    "mensaje": "La fila repite una combinacion ya vista."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_PRUEBA",
    "fila_id": "F-010",
    "mensaje": "La fila no contiene pruebas asociadas."
  },
  {
    "severidad": "alta",
    "codigo": "FILA_SIN_NORMA",
    "fila_id": "F-010",
    "mensaje": "La fila no contiene normas asociadas."
  }
]
```

## Evaluación y Escalamiento
- **Control de Rate Limit**: El backoff exponencial quedó delegado al cliente M4/M5/M8 y la ejecución serial a 1 concurrente evita picos.
- **Detección M8**: El auditor pudo verificar el lote e identificar anomalías.
- **Recomendación**: Para escalar, procesar fragmentos en lotes de 5 con esperas de 2-3 segundos entre lotes y concurrencia máxima de 1-2 para Groq.

## Trazas
```json
[
  {
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",
    "action": "extract_entities",
    "source_id": "0",
    "timestamp": "2026-06-21T07:41:25.584307+00:00",
    "status_code": 200,
    "elapsed_seconds": 0.955,
    "retries": 0,
    "attempts": 1,
    "fallback_used": false,
    "counts": {
      "hechos": 8,
      "pruebas": 0,
      "normas": 0
    }
  },
  {
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",
    "action": "extract_entities",
    "source_id": "1",
    "timestamp": "2026-06-21T07:41:28.224085+00:00",
    "status_code": 200,
    "elapsed_seconds": 1.139,
    "retries": 0,
    "attempts": 1,
    "fallback_used": false,
    "counts": {
      "hechos": 4,
      "pruebas": 3,
      "normas": 3
    }
  },
  {
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",
    "action": "extract_entities",
    "source_id": "2",
    "timestamp": "2026-06-21T07:41:40.921479+00:00",
    "status_code": 200,
    "elapsed_seconds": 11.196,
    "retries": 1,
    "attempts": 2,
    "fallback_used": false,
    "counts": {
      "hechos": 6,
      "pruebas": 2,
      "normas": 2
    }
  },
  {
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",
    "action": "extract_entities",
    "source_id": "3",
    "timestamp": "2026-06-21T07:42:02.119876+00:00",
    "status_code": 200,
    "elapsed_seconds": 19.698,
    "retries": 1,
    "attempts": 2,
    "fallback_used": false,
    "counts": {
      "hechos": 8,
      "pruebas": 4,
      "normas": 4
    }
  },
  {
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",
    "action": "extract_entities",
    "source_id": "4",
    "timestamp": "2026-06-21T07:42:22.394714+00:00",
    "status_code": 200,
    "elapsed_seconds": 18.774,
    "retries": 2,
    "attempts": 3,
    "fallback_used": false,
    "counts": {
      "hechos": 7,
      "pruebas": 4,
      "normas": 6
    }
  },
  {
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",
    "action": "build_hpn_matrix",
    "source_id": null,
    "timestamp": "2026-06-21T07:42:46.457224+00:00",
    "status_code": 200,
    "elapsed_seconds": 22.562,
    "retries": 1,
    "attempts": 2,
    "fallback_used": false,
    "rows": 10
  },
  {
    "provider": "deterministic",
    "model": "rules",
    "action": "audit_hpn_matrix",
    "source_id": null,
    "timestamp": "2026-06-21T07:42:46.457906+00:00",
    "status_code": null,
    "elapsed_seconds": 0.0,
    "retries": 0,
    "attempts": 1,
    "fallback_used": false,
    "alerts": 28
  }
]
```
