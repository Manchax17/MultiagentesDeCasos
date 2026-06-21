import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import cytoscape from 'cytoscape';
import { Network, Download, RefreshCw, AlertTriangle, Crosshair, Layers, Info } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

// Colores por capa (sección "Red compleja multicapa" del proyecto)
const LAYER_COLORS = {
  hechos: '#6366f1',
  pruebas: '#22c55e',
  normas: '#eab308',
  actores: '#06b6d4',
  tiempo: '#a855f7',
  elementos: '#f97316',
  riesgos: '#ef4444',
};

const LAYER_LABELS = {
  hechos: 'Hechos',
  pruebas: 'Pruebas',
  normas: 'Normas',
  actores: 'Actores',
  tiempo: 'Tiempo',
  elementos: 'Elementos jurídicos',
  riesgos: 'Riesgos',
};

const EDGE_COLORS = {
  soporta: '#22c55e',
  contradice: '#ef4444',
  activa: '#eab308',
  fundamenta: '#f97316',
  precede: '#a855f7',
  riesgo: '#f43f5e',
  participa: '#06b6d4',
};

const EDGE_LABELS = {
  soporta: 'Soporta',
  contradice: 'Contradice',
  activa: 'Activa',
  fundamenta: 'Fundamenta',
  precede: 'Precede',
  riesgo: 'Riesgo',
  participa: 'Participa',
};

const pct = (v) => `${Math.round((v || 0) * 100)}%`;

const MetricCard = ({ label, value, hint, tone = 'default' }) => (
  <div className="bg-bg-input border border-border-subtle rounded-xl p-4">
    <div className="text-[10px] uppercase tracking-wider text-text-muted font-semibold mb-1">{label}</div>
    <div className={`text-2xl font-bold ${
      tone === 'danger' ? 'text-accent-danger' : tone === 'success' ? 'text-accent-success' : 'text-text-primary'
    }`}>{value}</div>
    {hint && <div className="text-[11px] text-text-secondary mt-1 leading-snug">{hint}</div>}
  </div>
);

export default function RedMulticapaView({ casoId, hasMatriz }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  const [red, setRed] = useState(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [activeLayers, setActiveLayers] = useState(() => new Set(Object.keys(LAYER_COLORS)));
  const [activeEdges, setActiveEdges] = useState(() => new Set(Object.keys(EDGE_COLORS)));
  const [selected, setSelected] = useState(null);

  const metricsById = useMemo(() => {
    const map = {};
    (red?.metricas_nodos || []).forEach((m) => { map[m.id] = m; });
    return map;
  }, [red]);

  const labelById = useMemo(() => {
    const map = {};
    (red?.nodos || []).forEach((n) => { map[n.id] = n.label; });
    return map;
  }, [red]);

  // Carga la red existente al montar / cambiar de caso
  useEffect(() => {
    if (!casoId) return;
    let alive = true;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/expedientes/${casoId}/red`)
      .then((r) => r.json())
      .then((data) => {
        if (!alive) return;
        setRed(data && data.nodos ? data : null);
      })
      .catch(() => { if (alive) setError('No se pudo cargar la red.'); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [casoId]);

  const generarRed = useCallback(async () => {
    if (!casoId) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/expedientes/${casoId}/red`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Error generando la red');
      }
      const data = await res.json();
      setRed(data);
      setSelected(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  }, [casoId]);

  const elements = useMemo(() => {
    if (!red?.nodos) return [];
    const nodeIds = new Set();
    const nodes = red.nodos
      .filter((n) => activeLayers.has(n.capa))
      .map((n) => {
        nodeIds.add(n.id);
        const m = metricsById[n.id] || {};
        return {
          data: {
            id: n.id,
            label: n.label,
            capa: n.capa,
            color: LAYER_COLORS[n.capa] || '#94a3b8',
            grado: m.grado || 1,
            spof: m.es_punto_unico_falla ? 1 : 0,
          },
        };
      });
    const edges = red.aristas
      .filter((a) => activeEdges.has(a.tipo) && nodeIds.has(a.source) && nodeIds.has(a.target))
      .map((a, i) => ({
        data: {
          id: `e${i}`,
          source: a.source,
          target: a.target,
          tipo: a.tipo,
          color: EDGE_COLORS[a.tipo] || '#64748b',
          peso: a.peso || 0.5,
          dashed: a.tipo === 'contradice' ? 1 : 0,
        },
      }));
    return [...nodes, ...edges];
  }, [red, activeLayers, activeEdges, metricsById]);

  // Inicializa / actualiza Cytoscape
  useEffect(() => {
    if (!containerRef.current || !red?.nodos) return;
    if (!cyRef.current) {
      cyRef.current = cytoscape({
        container: containerRef.current,
        elements: [],
        wheelSensitivity: 0.2,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': 'data(color)',
              label: 'data(label)',
              color: '#e2e8f0',
              'font-size': '7px',
              'text-wrap': 'wrap',
              'text-max-width': '80px',
              'text-valign': 'bottom',
              'text-margin-y': 3,
              width: 'mapData(grado, 1, 12, 16, 52)',
              height: 'mapData(grado, 1, 12, 16, 52)',
              'border-width': 0,
            },
          },
          {
            selector: 'node[spof = 1]',
            style: { 'border-width': 3, 'border-color': '#ef4444', 'border-style': 'double' },
          },
          {
            selector: 'node:selected',
            style: { 'border-width': 4, 'border-color': '#ffffff' },
          },
          {
            selector: 'edge',
            style: {
              width: 'mapData(peso, 0, 1, 1, 4)',
              'line-color': 'data(color)',
              'target-arrow-color': 'data(color)',
              'target-arrow-shape': 'triangle',
              'arrow-scale': 0.7,
              'curve-style': 'bezier',
              opacity: 0.7,
            },
          },
          {
            selector: 'edge[dashed = 1]',
            style: { 'line-style': 'dashed' },
          },
          {
            selector: 'edge:selected',
            style: { opacity: 1, width: 4 },
          },
        ],
      });
      cyRef.current.on('tap', 'node', (evt) => {
        const d = evt.target.data();
        setSelected({ kind: 'node', ...d, metrics: metricsById[d.id] });
      });
      cyRef.current.on('tap', (evt) => {
        if (evt.target === cyRef.current) setSelected(null);
      });
    }
    const cy = cyRef.current;
    cy.json({ elements });
    cy.layout({ name: 'cose', animate: false, nodeRepulsion: 8000, idealEdgeLength: 90, padding: 30 }).run();
    cy.fit(undefined, 40);
  }, [elements, red, metricsById]);

  useEffect(() => () => { if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null; } }, []);

  const toggle = (setFn) => (key) => setFn((prev) => {
    const next = new Set(prev);
    next.has(key) ? next.delete(key) : next.add(key);
    return next;
  });
  const toggleLayer = toggle(setActiveLayers);
  const toggleEdge = toggle(setActiveEdges);

  const exportar = async (format) => {
    try {
      const res = await fetch(`${API_BASE}/api/expedientes/${casoId}/red/export?format=${format}`);
      if (!res.ok) throw new Error('Error exportando');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `red_multicapa_${casoId}.${format === 'json' ? 'json' : format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    }
  };

  const m = red?.metricas;

  // ── Estado: sin matriz / sin red generada ──
  if (!hasMatriz) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center text-center animate-[fadeIn_0.3s_ease]">
        <div className="w-24 h-24 rounded-full bg-accent-secondary/10 flex items-center justify-center mb-6 border-2 border-accent-secondary/20">
          <Network size={40} className="text-accent-secondary" />
        </div>
        <h2 className="text-2xl font-bold mb-3">Red de Nodos Complejos (M6)</h2>
        <p className="text-text-secondary max-w-md">
          Primero genera la <strong>Matriz HPN</strong> en el módulo de Ingesta. La red multicapa se construye a partir de ella.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full animate-[fadeIn_0.3s_ease] pb-12">
      <header className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold mb-1">Red Compleja Multicapa (M6)</h2>
          <p className="text-text-secondary text-sm max-w-2xl">
            Grafo dirigido por capas construido desde la Matriz HPN. Nodos por capa, aristas tipadas y métricas estructurales calculadas con NetworkX.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={generarRed}
            disabled={generating}
            className="py-2 px-4 rounded-xl font-semibold text-sm bg-gradient-primary text-white shadow-md hover:shadow-lg disabled:opacity-50 flex items-center gap-2"
          >
            <RefreshCw size={16} className={generating ? 'animate-spin' : ''} />
            {generating ? 'Construyendo...' : red ? 'Regenerar red' : 'Generar red'}
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 p-3 rounded-xl border border-accent-danger/30 bg-accent-danger/10 text-sm text-accent-danger flex items-center gap-2">
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {loading && !red && (
        <div className="text-text-muted text-sm flex items-center gap-2"><RefreshCw size={16} className="animate-spin" /> Cargando red...</div>
      )}

      {!loading && !red && !error && (
        <div className="bg-bg-card border border-border-subtle rounded-2xl p-10 text-center">
          <Network size={36} className="mx-auto mb-4 text-accent-secondary" />
          <p className="text-text-secondary mb-6">Aún no se ha construido la red para este caso.</p>
          <button onClick={generarRed} disabled={generating}
            className="py-2.5 px-6 rounded-xl font-semibold bg-gradient-primary text-white shadow-md hover:shadow-lg disabled:opacity-50 inline-flex items-center gap-2">
            <Network size={16} /> {generating ? 'Construyendo...' : 'Generar red multicapa'}
          </button>
        </div>
      )}

      {red && (
        <>
          {/* Métricas globales */}
          {m && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              <MetricCard label="Nodos / Aristas" value={`${m.n_nodos} / ${m.n_aristas}`} hint="Tamaño de la red" />
              <MetricCard label="Cobertura rutas jurídicas" value={pct(m.cobertura_rutas_juridicas)}
                hint="Hechos con ruta prueba→hecho→norma→elemento"
                tone={m.cobertura_rutas_juridicas >= 0.6 ? 'success' : 'default'} />
              <MetricCard label="Redundancia probatoria" value={m.redundancia_probatoria}
                hint="Pruebas independientes por hecho (promedio)" />
              <MetricCard label="Índice de contradicción" value={pct(m.indice_contradiccion)}
                hint="Proporción de aristas que contradicen"
                tone={m.indice_contradiccion > 0.15 ? 'danger' : 'default'} />
              <MetricCard label="Densidad de soporte" value={m.densidad_soporte}
                hint="Aristas 'soporta' por hecho" />
              <MetricCard label="Densidad de red" value={m.densidad} hint="Conectividad global del grafo" />
              <MetricCard label="Puntos únicos de falla" value={(m.puntos_unicos_falla || []).length}
                hint="Nodos críticos de articulación"
                tone={(m.puntos_unicos_falla || []).length > 0 ? 'danger' : 'success'} />
              <MetricCard label="Pruebas críticas" value={(m.pruebas_criticas || []).length}
                hint="Pruebas cuya pérdida rompe rutas" tone="danger" />
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
            {/* Grafo + filtros */}
            <div className="bg-bg-card border border-border-subtle rounded-2xl overflow-hidden">
              {/* Filtros de capas */}
              <div className="p-3 border-b border-border-subtle flex flex-wrap items-center gap-2">
                <span className="text-[10px] uppercase tracking-wider text-text-muted font-semibold flex items-center gap-1 mr-1">
                  <Layers size={12} /> Capas
                </span>
                {Object.keys(LAYER_COLORS).map((capa) => (
                  <button key={capa} onClick={() => toggleLayer(capa)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-all flex items-center gap-1.5 ${
                      activeLayers.has(capa) ? 'border-border-default bg-bg-input text-text-primary' : 'border-border-subtle text-text-muted opacity-50'
                    }`}>
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: LAYER_COLORS[capa] }} />
                    {LAYER_LABELS[capa]}
                    <span className="text-text-muted">{m?.n_nodos_por_capa?.[capa] || 0}</span>
                  </button>
                ))}
              </div>
              {/* Filtros de relaciones */}
              <div className="p-3 border-b border-border-subtle flex flex-wrap items-center gap-2">
                <span className="text-[10px] uppercase tracking-wider text-text-muted font-semibold mr-1">Relaciones</span>
                {Object.keys(EDGE_COLORS).map((tipo) => (
                  <button key={tipo} onClick={() => toggleEdge(tipo)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-all flex items-center gap-1.5 ${
                      activeEdges.has(tipo) ? 'border-border-default bg-bg-input text-text-primary' : 'border-border-subtle text-text-muted opacity-50'
                    }`}>
                    <span className="w-4 h-0.5 rounded" style={{ backgroundColor: EDGE_COLORS[tipo] }} />
                    {EDGE_LABELS[tipo]}
                    <span className="text-text-muted">{m?.n_aristas_por_tipo?.[tipo] || 0}</span>
                  </button>
                ))}
              </div>
              <div ref={containerRef} className="w-full h-[60vh] bg-bg-primary" />
              {/* Exportación */}
              <div className="p-3 border-t border-border-subtle flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-wider text-text-muted font-semibold mr-1 flex items-center gap-1">
                  <Download size={12} /> Exportar (E5)
                </span>
                {['json', 'graphml', 'gexf'].map((f) => (
                  <button key={f} onClick={() => exportar(f)}
                    className="text-xs px-3 py-1 rounded-lg border border-border-subtle bg-bg-input hover:border-border-default text-text-secondary hover:text-text-primary uppercase font-mono">
                    {f}
                  </button>
                ))}
              </div>
            </div>

            {/* Panel lateral: detalle de nodo + listas críticas */}
            <div className="space-y-4">
              <div className="bg-bg-card border border-border-subtle rounded-2xl p-4 min-h-[140px]">
                <div className="text-[10px] uppercase tracking-wider text-text-muted font-semibold mb-2 flex items-center gap-1">
                  <Info size={12} /> Detalle del nodo
                </div>
                {selected?.kind === 'node' ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full" style={{ backgroundColor: LAYER_COLORS[selected.capa] }} />
                      <span className="text-xs font-mono text-text-muted">{selected.id}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-bg-input border border-border-subtle">{LAYER_LABELS[selected.capa]}</span>
                    </div>
                    <p className="text-sm text-text-primary leading-snug">{selected.label}</p>
                    {selected.metrics && (
                      <div className="grid grid-cols-2 gap-2 pt-2 text-xs">
                        <div className="text-text-muted">Grado: <span className="text-text-primary font-semibold">{selected.metrics.grado}</span></div>
                        <div className="text-text-muted">Intermediación: <span className="text-text-primary font-semibold">{selected.metrics.centralidad_intermediacion}</span></div>
                        {selected.capa === 'pruebas' && (
                          <>
                            <div className="text-text-muted">Fragilidad: <span className="text-text-primary font-semibold">{selected.metrics.fragilidad}</span></div>
                            <div className="text-text-muted">Soporta: <span className="text-text-primary font-semibold">{selected.metrics.hechos_soportados}</span> hechos</div>
                          </>
                        )}
                        {selected.metrics.es_punto_unico_falla && (
                          <div className="col-span-2 text-accent-danger flex items-center gap-1"><AlertTriangle size={12} /> Punto único de falla</div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-text-muted">Haz clic en un nodo del grafo para ver sus métricas.</p>
                )}
              </div>

              {m?.pruebas_criticas?.length > 0 && (
                <div className="bg-bg-card border border-border-subtle rounded-2xl p-4">
                  <div className="text-[10px] uppercase tracking-wider text-text-muted font-semibold mb-2 flex items-center gap-1">
                    <Crosshair size={12} /> Pruebas críticas
                  </div>
                  <ul className="space-y-1.5">
                    {m.pruebas_criticas.map((id) => (
                      <li key={id} className="text-xs flex items-start gap-2">
                        <span className="font-mono text-accent-success mt-0.5">{id}</span>
                        <span className="text-text-secondary leading-snug">{labelById[id] || ''}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {m?.puntos_unicos_falla?.length > 0 && (
                <div className="bg-bg-card border border-border-subtle rounded-2xl p-4">
                  <div className="text-[10px] uppercase tracking-wider text-text-muted font-semibold mb-2 flex items-center gap-1">
                    <AlertTriangle size={12} className="text-accent-danger" /> Puntos únicos de falla
                  </div>
                  <ul className="space-y-1.5">
                    {m.puntos_unicos_falla.map((id) => (
                      <li key={id} className="text-xs flex items-start gap-2">
                        <span className="font-mono text-accent-danger mt-0.5">{id}</span>
                        <span className="text-text-secondary leading-snug">{labelById[id] || ''}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
