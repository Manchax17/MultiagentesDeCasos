"""
M6 — Red compleja multicapa y métricas.

Construye, de forma determinística (sin LLM), una red multicapa a partir de la
matriz HPN (M5) y calcula métricas estructurales con NetworkX.

Capas:        hechos, pruebas, normas, actores, tiempo, elementos, riesgos
Relaciones:   soporta, contradice, activa, fundamenta, precede, riesgo, participa
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

# Pesos por defecto según tipo de relación
PESOS_TIPO = {
    "soporta": 0.8,
    "contradice": 0.6,
    "activa": 0.7,
    "fundamenta": 0.7,
    "precede": 0.5,
    "riesgo": 0.6,
    "participa": 0.4,
}

_RIESGOS_FUERTES = ("alto", "critico")


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return texto[:40] or "x"


def _label(texto: str, n: int = 80) -> str:
    texto = str(texto or "").strip()
    return texto[: n - 1] + "…" if len(texto) > n else texto


def _peso_soporta(prueba: dict[str, Any]) -> float:
    base = PESOS_TIPO["soporta"]
    conf = prueba.get("confianza")
    if isinstance(conf, (int, float)):
        return round(min(1.0, max(0.1, float(conf))), 2)
    if str(prueba.get("estado", "")).lower() in ("inadmisible", "faltante", "no_admitida"):
        return 0.3
    return base


# ──────────────────────────────────────────────
# Construcción de la red
# ──────────────────────────────────────────────

def construir_red(matriz: dict[str, Any], caso_id: str) -> dict[str, Any]:
    """Transforma la matriz HPN en nodos y aristas tipados por capa."""
    hechos = {h["hecho_id"]: h for h in matriz.get("hechos", []) if h.get("hecho_id")}
    pruebas = {p["prueba_id"]: p for p in matriz.get("pruebas", []) if p.get("prueba_id")}
    normas = {n["norma_id"]: n for n in matriz.get("normas", []) if n.get("norma_id")}
    filas = matriz.get("filas_hpn", []) or []

    nodos: dict[str, dict[str, Any]] = {}
    aristas: list[dict[str, Any]] = []

    def add_nodo(node_id: str, capa: str, label: str, **extra: Any) -> None:
        if node_id and node_id not in nodos:
            nodos[node_id] = {
                "id": node_id,
                "capa": capa,
                "label": _label(label),
                "estado": extra.get("estado"),
                "riesgo": extra.get("riesgo"),
                "pagina": extra.get("pagina"),
                "fragmento_id": extra.get("fragmento_id"),
            }

    def add_arista(source: str, target: str, tipo: str, capa_o: str, capa_d: str,
                   peso: float | None = None, evidencia: dict | None = None) -> None:
        if source in nodos and target in nodos and source != target:
            aristas.append({
                "source": source,
                "target": target,
                "tipo": tipo,
                "capa_origen": capa_o,
                "capa_destino": capa_d,
                "peso": round(peso if peso is not None else PESOS_TIPO.get(tipo, 0.5), 2),
                "evidencia": evidencia,
            })

    # Estado epistémico/riesgo del hecho tomado de la primera fila que lo referencia
    estado_por_hecho: dict[str, str] = {}
    riesgo_por_hecho: dict[str, str] = {}
    for fila in filas:
        hid = fila.get("hecho_id")
        if hid and hid not in estado_por_hecho:
            estado_por_hecho[hid] = fila.get("estado_epistemico")
            riesgo_por_hecho[hid] = fila.get("riesgo")

    # 1) Nodos de hechos, pruebas, normas
    for hid, h in hechos.items():
        add_nodo(hid, "hechos", h.get("descripcion", hid),
                 estado=estado_por_hecho.get(hid), riesgo=riesgo_por_hecho.get(hid),
                 pagina=h.get("pagina"), fragmento_id=h.get("fragmento_fuente"))
    for pid, p in pruebas.items():
        add_nodo(pid, "pruebas", p.get("descripcion", pid),
                 estado=p.get("estado"), pagina=p.get("pagina"),
                 fragmento_id=p.get("fragmento_fuente"))
    for nid, n in normas.items():
        add_nodo(nid, "normas", n.get("referencia") or n.get("descripcion", nid),
                 estado="inferida" if n.get("es_inferida") else "expediente",
                 pagina=n.get("pagina"), fragmento_id=n.get("fragmento_fuente"))

    # 2) Nodos de actores, tiempo, elementos, riesgos + aristas
    fechas_hechos: list[tuple[str, str]] = []  # (fecha, hecho_id) para precedencia
    for hid, h in hechos.items():
        for actor in h.get("actores", []) or []:
            aid = f"ACT-{_slug(actor)}"
            add_nodo(aid, "actores", actor)
            add_arista(aid, hid, "participa", "actores", "hechos")
        fecha = h.get("fecha_hecho")
        if fecha:
            tid = f"T-{_slug(str(fecha))}"
            add_nodo(tid, "tiempo", str(fecha))
            add_arista(tid, hid, "precede", "tiempo", "hechos")
            fechas_hechos.append((str(fecha), hid))

    # Precedencia temporal entre hechos con fecha ordenable
    fechas_ordenadas = sorted(fechas_hechos, key=lambda t: t[0])
    for (_, h_prev), (_, h_next) in zip(fechas_ordenadas, fechas_ordenadas[1:]):
        add_arista(h_prev, h_next, "precede", "hechos", "hechos")

    # 3) Aristas desde la matriz HPN
    for fila in filas:
        hid = fila.get("hecho_id")
        if hid not in nodos:
            continue
        evidencia = fila.get("fuente_expediente") or None

        # Elemento jurídico (pretensión / defensa / requisito)
        elemento = fila.get("elemento_juridico")
        ej_id = None
        if elemento:
            ej_id = f"EJ-{_slug(elemento)}"
            add_nodo(ej_id, "elementos", elemento)

        # prueba → hecho (soporta)
        for pid in fila.get("prueba_ids", []) or []:
            if pid in pruebas:
                add_arista(pid, hid, "soporta", "pruebas", "hechos",
                           peso=_peso_soporta(pruebas[pid]), evidencia=evidencia)

        # contradicción → hecho (contradice)
        for cid in fila.get("contradicciones", []) or []:
            capa_o = "pruebas" if cid in pruebas else "hechos" if cid in hechos else None
            if capa_o and cid in nodos:
                add_arista(cid, hid, "contradice", capa_o, "hechos", evidencia=evidencia)

        # hecho → norma (activa) ; norma → elemento (fundamenta)
        for nid in fila.get("norma_ids", []) or []:
            if nid in normas:
                add_arista(hid, nid, "activa", "hechos", "normas", evidencia=evidencia)
                if ej_id:
                    add_arista(nid, ej_id, "fundamenta", "normas", "elementos")

        # nodo de riesgo para filas alto/crítico
        riesgo = str(fila.get("riesgo", "")).lower()
        if riesgo in _RIESGOS_FUERTES:
            rid = f"R-{fila.get('fila_id', hid)}"
            add_nodo(rid, "riesgos", f"Riesgo {riesgo}: {fila.get('accion_sugerida') or hid}",
                     riesgo=riesgo)
            add_arista(rid, hid, "riesgo", "riesgos", "hechos")

    logger.info("[RED] caso %s: %s nodos, %s aristas", caso_id, len(nodos), len(aristas))
    return {"caso_id": caso_id, "nodos": list(nodos.values()), "aristas": aristas}


# ──────────────────────────────────────────────
# Métricas estructurales
# ──────────────────────────────────────────────

def _build_digraph(nodos: list[dict], aristas: list[dict]) -> nx.DiGraph:
    g = nx.DiGraph()
    for n in nodos:
        g.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
    for a in aristas:
        g.add_edge(a["source"], a["target"], tipo=a["tipo"], peso=a.get("peso", 0.5))
    return g


def _score_cobertura(g: nx.DiGraph, hechos_ids: set[str]) -> int:
    """Score = nº de hechos que reciben al menos una arista 'soporta'."""
    soportados = 0
    for h in hechos_ids:
        if any(d.get("tipo") == "soporta" for _, _, d in g.in_edges(h, data=True)):
            soportados += 1
    return soportados


def calcular_metricas(red: dict[str, Any]) -> dict[str, Any]:
    """Calcula métricas globales y por nodo con NetworkX."""
    nodos = red.get("nodos", [])
    aristas = red.get("aristas", [])
    g = _build_digraph(nodos, aristas)

    capa_de = {n["id"]: n["capa"] for n in nodos}
    label_de = {n["id"]: n["label"] for n in nodos}
    hechos_ids = {n["id"] for n in nodos if n["capa"] == "hechos"}
    pruebas_ids = {n["id"] for n in nodos if n["capa"] == "pruebas"}
    elementos_ids = {n["id"] for n in nodos if n["capa"] == "elementos"}
    normas_ids = {n["id"] for n in nodos if n["capa"] == "normas"}

    n_nodos = g.number_of_nodes()
    n_aristas = g.number_of_edges()

    # Conteos por capa / tipo
    n_por_capa: dict[str, int] = {}
    for n in nodos:
        n_por_capa[n["capa"]] = n_por_capa.get(n["capa"], 0) + 1
    n_por_tipo: dict[str, int] = {}
    for a in aristas:
        n_por_tipo[a["tipo"]] = n_por_tipo.get(a["tipo"], 0) + 1

    # Centralidades
    if n_nodos > 0:
        betweenness = nx.betweenness_centrality(g, weight="peso", normalized=True)
        degree_cent = nx.degree_centrality(g)
    else:
        betweenness, degree_cent = {}, {}
    densidad = nx.density(g) if n_nodos > 1 else 0.0

    # Puntos únicos de falla = puntos de articulación (grafo no dirigido)
    puntos_falla: list[str] = []
    if n_nodos > 2:
        ug = g.to_undirected()
        for comp in nx.connected_components(ug):
            sub = ug.subgraph(comp)
            if sub.number_of_nodes() > 2:
                puntos_falla.extend(nx.articulation_points(sub))
    puntos_falla = sorted(set(puntos_falla))

    # Fragilidad probatoria F(p) = Score(G) - Score(G - p)
    score_full = _score_cobertura(g, hechos_ids)
    fragilidad: dict[str, float] = {}
    hechos_soportados: dict[str, int] = {}
    for pid in pruebas_ids:
        hechos_soportados[pid] = sum(
            1 for _, _, d in g.out_edges(pid, data=True) if d.get("tipo") == "soporta"
        )
        g2 = g.copy()
        g2.remove_node(pid)
        fragilidad[pid] = float(score_full - _score_cobertura(g2, hechos_ids - {pid}))

    # Redundancia probatoria = promedio de pruebas independientes por hecho
    pruebas_por_hecho = []
    for h in hechos_ids:
        cnt = sum(1 for s, _, d in g.in_edges(h, data=True)
                  if d.get("tipo") == "soporta" and capa_de.get(s) == "pruebas")
        pruebas_por_hecho.append(cnt)
    redundancia = round(sum(pruebas_por_hecho) / len(pruebas_por_hecho), 2) if pruebas_por_hecho else 0.0

    # Densidad de soporte = aristas 'soporta' / nº de hechos
    n_soporta = n_por_tipo.get("soporta", 0)
    densidad_soporte = round(n_soporta / len(hechos_ids), 2) if hechos_ids else 0.0

    # Índice de contradicción = proporción de aristas 'contradice'
    indice_contradiccion = round(n_por_tipo.get("contradice", 0) / n_aristas, 3) if n_aristas else 0.0

    # Cobertura de rutas jurídicas: rutas prueba→hecho→norma→elemento completas
    cobertura = _cobertura_rutas(g, hechos_ids, normas_ids, elementos_ids)

    # Métricas por nodo
    metricas_nodos = []
    for n in nodos:
        nid = n["id"]
        metricas_nodos.append({
            "id": nid,
            "capa": n["capa"],
            "label": n["label"],
            "grado": g.degree(nid),
            "centralidad_intermediacion": round(betweenness.get(nid, 0.0), 4),
            "centralidad_grado": round(degree_cent.get(nid, 0.0), 4),
            "es_punto_unico_falla": nid in puntos_falla,
            "fragilidad": round(fragilidad.get(nid, 0.0), 3),
            "hechos_soportados": hechos_soportados.get(nid, 0),
        })

    # Pruebas críticas: mayor fragilidad, desempate por hechos soportados
    pruebas_criticas = sorted(
        pruebas_ids,
        key=lambda p: (fragilidad.get(p, 0.0), hechos_soportados.get(p, 0)),
        reverse=True,
    )
    pruebas_criticas = [p for p in pruebas_criticas if fragilidad.get(p, 0.0) > 0][:10]

    metricas = {
        "n_nodos": n_nodos,
        "n_aristas": n_aristas,
        "n_nodos_por_capa": n_por_capa,
        "n_aristas_por_tipo": n_por_tipo,
        "densidad": round(densidad, 4),
        "densidad_soporte": densidad_soporte,
        "cobertura_rutas_juridicas": cobertura,
        "indice_contradiccion": indice_contradiccion,
        "redundancia_probatoria": redundancia,
        "puntos_unicos_falla": puntos_falla,
        "pruebas_criticas": pruebas_criticas,
    }
    return {"metricas": metricas, "metricas_nodos": metricas_nodos}


def _cobertura_rutas(g: nx.DiGraph, hechos_ids: set[str], normas_ids: set[str],
                     elementos_ids: set[str]) -> float:
    """% de hechos con ruta completa prueba→hecho→norma(→elemento)."""
    if not hechos_ids:
        return 0.0
    completas = 0
    for h in hechos_ids:
        tiene_prueba = any(d.get("tipo") == "soporta" for _, _, d in g.in_edges(h, data=True))
        normas_h = [t for _, t, d in g.out_edges(h, data=True)
                    if d.get("tipo") == "activa" and t in normas_ids]
        tiene_norma = bool(normas_h)
        # Si hay capa de elementos, exigir que la norma fundamente un elemento
        if elementos_ids:
            tiene_elemento = any(
                any(d.get("tipo") == "fundamenta" and tt in elementos_ids
                    for _, tt, d in g.out_edges(nid, data=True))
                for nid in normas_h
            )
            if tiene_prueba and tiene_norma and tiene_elemento:
                completas += 1
        elif tiene_prueba and tiene_norma:
            completas += 1
    return round(completas / len(hechos_ids), 3)


def generar_red_completa(matriz: dict[str, Any], caso_id: str) -> dict[str, Any]:
    """Construye la red y calcula sus métricas en un solo paso."""
    red = construir_red(matriz, caso_id)
    red.update(calcular_metricas(red))
    return red


# ──────────────────────────────────────────────
# Exportación (E5)
# ──────────────────────────────────────────────

def exportar_grafo(red: dict[str, Any], formato: str) -> str:
    """Exporta la red en GraphML o GEXF (string)."""
    g = nx.MultiDiGraph()
    for n in red.get("nodos", []):
        attrs = {k: ("" if v is None else v) for k, v in n.items() if k != "id"}
        g.add_node(n["id"], **attrs)
    for a in red.get("aristas", []):
        g.add_edge(
            a["source"], a["target"],
            tipo=a["tipo"], peso=a.get("peso", 0.5),
            capa_origen=a["capa_origen"], capa_destino=a["capa_destino"],
        )
    import io
    buf = io.BytesIO()
    if formato == "graphml":
        nx.write_graphml(g, buf, encoding="utf-8")
    elif formato == "gexf":
        nx.write_gexf(g, buf, encoding="utf-8")
    else:
        raise ValueError(f"Formato no soportado: {formato}")
    return buf.getvalue().decode("utf-8")
