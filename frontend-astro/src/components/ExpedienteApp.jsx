import React, { useState, useRef, useEffect } from 'react';
import { Upload, FileText, CheckCircle2, XCircle, FileJson, File, X, Info, ChevronDown, ChevronRight, MessageSquare, Network, Layers, Database } from 'lucide-react';
import ChatLayout from './ChatLayout';

const API_BASE = 'http://localhost:8000';

// Format utility
const formatBytes = (bytes) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};
const formatNum = (n) => new Intl.NumberFormat('es-CO').format(n);

const SECTION_LABELS = {
  caratula: 'Carátula',
  hechos: 'Hechos',
  pretensiones: 'Pretensiones',
  pruebas: 'Pruebas',
  fundamentos_de_derecho: 'Fundamentos de Derecho',
  contestacion: 'Contestación',
  sentencia: 'Sentencia',
  recurso: 'Recurso',
  notificacion: 'Notificación',
  acta: 'Acta',
  peritaje: 'Peritaje',
  anexo: 'Anexo',
  desconocido: 'Sin clasificar',
};

const Toast = ({ message, type, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div className={`flex items-center gap-3 p-4 rounded-xl border glass-effect animate-[slideIn_0.3s_ease] ${
      type === 'success' ? 'border-accent-success/30' : type === 'error' ? 'border-accent-danger/30' : 'border-border-default'
    }`}>
      {type === 'success' ? <CheckCircle2 className="text-accent-success" size={20} /> :
       type === 'error' ? <XCircle className="text-accent-danger" size={20} /> :
       <Info className="text-accent-primary" size={20} />}
      <span className="text-sm font-medium">{message}</span>
    </div>
  );
};

const FragmentCard = ({ frag, casoId }) => {
  const [expanded, setExpanded] = useState(false);
  const [fullText, setFullText] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const toggleExpand = async () => {
    if (!expanded && !fullText) {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/expedientes/${casoId}/fragmentos/${frag.fragmento_id}`);
        if (!res.ok) throw new Error('Error al cargar');
        const data = await res.json();
        setFullText(data.fragmento.texto);
      } catch (err) {
        setError('Error al cargar el texto completo');
      } finally {
        setLoading(false);
      }
    }
    setExpanded(!expanded);
  };

  return (
    <div 
      className={`bg-bg-input border rounded-xl p-5 cursor-pointer transition-all duration-250 ${
        expanded ? 'border-accent-primary bg-bg-card' : 'border-border-subtle hover:border-border-default hover:bg-bg-card'
      }`}
      onClick={toggleExpand}
    >
      <div className="flex items-center gap-3 mb-3">
        {expanded ? <ChevronDown size={16} className="text-text-muted" /> : <ChevronRight size={16} className="text-text-muted" />}
        <span className="font-mono text-xs text-accent-primary-light bg-accent-primary/10 px-2 py-0.5 rounded-md">
          {frag.fragmento_id}
        </span>
        <span className="text-xs text-text-secondary">📄 Pág. {frag.pagina}</span>
        <span className="text-xs px-2 py-0.5 rounded-full bg-accent-secondary/10 text-accent-secondary border border-accent-secondary/20 ml-auto font-medium">
          {SECTION_LABELS[frag.seccion] || frag.seccion}
        </span>
      </div>
      
      {!expanded ? (
        <p className="text-sm text-text-secondary leading-relaxed line-clamp-2">{frag.preview}</p>
      ) : (
        <div className="mt-4">
          <div className="p-4 bg-bg-primary rounded-lg border border-border-subtle text-sm leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto scrollbar-custom">
            {loading ? (
              <div className="flex items-center gap-2 text-text-muted">
                <div className="w-4 h-4 border-2 border-border-default border-t-accent-primary rounded-full animate-spin"></div>
                Cargando texto completo...
              </div>
            ) : error ? (
              <span className="text-accent-danger">{error}</span>
            ) : (
              fullText
            )}
          </div>
          <div className="flex items-center gap-4 mt-4 pt-4 border-t border-border-subtle text-xs text-text-muted">
            <span>🔤 {formatNum(frag.caracteres)} caracteres</span>
            <span>📄 Página {frag.pagina}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default function DashboardLayout() {
  const [currentView, setCurrentView] = useState('intake'); // 'intake', 'network', 'chat'
  const [theme, setTheme] = useState('dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Intake State
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [steps, setSteps] = useState({ upload: null, process: null, fragments: null });
  const [results, setResults] = useState(null);
  const [fragments, setFragments] = useState([]);
  const [activeSection, setActiveSection] = useState(null);
  
  const [toasts, setToasts] = useState([]);
  const [matriz, setMatriz] = useState(null);
  const [loadingMatriz, setLoadingMatriz] = useState(false);

  const fetchMatriz = async (casoId) => {
    try {
      const res = await fetch(`${API_BASE}/api/expedientes/${casoId}/matriz`);
      if (res.ok) {
        const data = await res.json();
        setMatriz(data.matriz);
      }
    } catch (e) {
      console.error("Error fetching matriz", e);
    }
  };

  const generateMatriz = async () => {
    if (!results) return;
    setLoadingMatriz(true);
    addToast('Ejecutando Agentes de Inteligencia Artificial...', 'info');
    try {
      const res = await fetch(`${API_BASE}/api/expedientes/${results.casoId}/matriz`, { method: 'POST' });
      if (!res.ok) throw new Error('Error generando matriz HPN');
      const data = await res.json();
      setMatriz(data.matriz);
      addToast('Matriz HPN generada exitosamente', 'success');
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoadingMatriz(false);
    }
  };

  const addToast = (message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
  };

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const validateAndSetFile = (selectedFile) => {
    if (!selectedFile) return;
    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      addToast('Solo se aceptan archivos PDF (.pdf)', 'error');
      return;
    }
    if (selectedFile.size > 50 * 1024 * 1024) {
      addToast('El archivo excede el límite de 50 MB', 'error');
      return;
    }
    setFile(selectedFile);
    setResults(null);
    setProgress(0);
    setSteps({ upload: null, process: null, fragments: null });
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleProcess = async () => {
    if (!file) return;
    setProcessing(true);
    setResults(null);
    
    try {
      setSteps(s => ({ ...s, upload: 'active' }));
      setProgress(15);
      const formData = new FormData();
      formData.append('archivo', file);
      
      const uploadRes = await fetch(`${API_BASE}/api/expedientes/subir`, { method: 'POST', body: formData });
      if (!uploadRes.ok) throw new Error('Error al subir PDF');
      const uploadData = await uploadRes.json();
      const casoId = uploadData.caso_id;
      
      setSteps(s => ({ ...s, upload: 'done' }));
      setProgress(35);
      
      setSteps(s => ({ ...s, process: 'active' }));
      setProgress(50);
      const processRes = await fetch(`${API_BASE}/api/expedientes/${casoId}/procesar`, { method: 'POST' });
      if (!processRes.ok) throw new Error('Error en la ingesta del PDF');
      const processData = await processRes.json();
      
      setSteps(s => ({ ...s, process: 'done' }));
      setProgress(75);
      
      setSteps(s => ({ ...s, fragments: 'active' }));
      const fragsRes = await fetch(`${API_BASE}/api/expedientes/${casoId}/fragmentos?limit=200`);
      if (!fragsRes.ok) throw new Error('Error al cargar fragmentos');
      const fragsData = await fragsRes.json();
      
      setSteps(s => ({ ...s, fragments: 'done' }));
      setProgress(100);
      
      setFragments(fragsData.fragmentos);
      setResults({ casoId, stats: processData });
      addToast('Ingesta completada exitosamente', 'success');
      fetchMatriz(casoId);
      
    } catch (err) {
      addToast(err.message, 'error');
      setSteps(s => {
        const newSteps = { ...s };
        Object.keys(newSteps).forEach(k => { if (newSteps[k] === 'active') newSteps[k] = 'error' });
        return newSteps;
      });
    } finally {
      setProcessing(false);
    }
  };

  const filteredFragments = activeSection 
    ? fragments.filter(f => f.seccion === activeSection) 
    : fragments;

  const NavItem = ({ id, label, icon: Icon, disabled }) => (
    <button
      onClick={() => !disabled && setCurrentView(id)}
      disabled={disabled}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-left ${
        currentView === id 
          ? 'bg-gradient-primary text-white shadow-lg shadow-accent-primary/20' 
          : disabled 
            ? 'opacity-50 cursor-not-allowed text-text-muted hover:bg-transparent'
            : 'text-text-secondary hover:bg-bg-input hover:text-text-primary'
      }`}
    >
      <Icon size={18} className={currentView === id ? 'text-white' : ''} />
      <span className="font-medium text-sm">{label}</span>
    </button>
  );

  return (
    <div className="flex h-screen w-full bg-bg-primary overflow-hidden text-text-primary">
      
      {/* Sidebar Fija */}
      <aside className="w-72 bg-bg-card border-r border-border-subtle flex flex-col flex-shrink-0 z-20">
        <div className="p-6 border-b border-border-subtle">
          <div className="inline-flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-gradient-primary rounded-xl flex items-center justify-center text-xl shadow-[0_0_20px_rgba(99,102,241,0.2)]">
              ⚖️
            </div>
            <div>
              <h1 className="text-base font-bold text-gradient leading-tight">
                Teoría del Caso
              </h1>
              <p className="text-[10px] text-text-muted tracking-wider uppercase font-semibold mt-0.5">
                Sistema Multiagente
              </p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          <div className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4 ml-2 mt-2">Módulos del Sistema</div>
          
          <NavItem id="intake" label="Ingesta y Matriz HPN" icon={Database} />
          
          <NavItem 
            id="network" 
            label="Grafo de Red Nodal" 
            icon={Network} 
            disabled={!results} 
          />
          
          <NavItem 
            id="chat" 
            label="Asistente Interactivo" 
            icon={MessageSquare} 
            disabled={!results} 
          />
        </nav>

        <div className="p-4 border-t border-border-subtle bg-bg-input/50">
          <div className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3 ml-1">Apariencia</div>
          <div className="flex items-center gap-2 mb-4">
            <button 
              onClick={() => setTheme('dark')}
              className={`w-8 h-8 rounded-full bg-[#0a0e1a] border-2 transition-all ${theme === 'dark' ? 'border-accent-primary scale-110' : 'border-transparent hover:scale-105'} flex items-center justify-center`}
              title="Dark"
            >
              {theme === 'dark' && <div className="w-2 h-2 rounded-full bg-accent-primary"></div>}
            </button>
            <button 
              onClick={() => setTheme('midnight')}
              className={`w-8 h-8 rounded-full bg-[#050517] border-2 transition-all ${theme === 'midnight' ? 'border-[#a855f7] scale-110' : 'border-transparent hover:scale-105'} flex items-center justify-center`}
              title="Midnight Purple"
            >
              {theme === 'midnight' && <div className="w-2 h-2 rounded-full bg-[#a855f7]"></div>}
            </button>
            <button 
              onClick={() => setTheme('ocean')}
              className={`w-8 h-8 rounded-full bg-[#021422] border-2 transition-all ${theme === 'ocean' ? 'border-[#0ea5e9] scale-110' : 'border-transparent hover:scale-105'} flex items-center justify-center`}
              title="Deep Ocean"
            >
              {theme === 'ocean' && <div className="w-2 h-2 rounded-full bg-[#0ea5e9]"></div>}
            </button>
            <button 
              onClick={() => setTheme('catppuccin')}
              className={`w-8 h-8 rounded-full bg-[#24273a] border-2 transition-all ${theme === 'catppuccin' ? 'border-[#c6a0f6] scale-110' : 'border-transparent hover:scale-105'} flex items-center justify-center`}
              title="Catppuccin"
            >
              {theme === 'catppuccin' && <div className="w-2 h-2 rounded-full bg-[#c6a0f6]"></div>}
            </button>
            <button 
              onClick={() => setTheme('tokyo-night')}
              className={`w-8 h-8 rounded-full bg-[#1a1b26] border-2 transition-all ${theme === 'tokyo-night' ? 'border-[#7aa2f7] scale-110' : 'border-transparent hover:scale-105'} flex items-center justify-center`}
              title="Tokyo Night"
            >
              {theme === 'tokyo-night' && <div className="w-2 h-2 rounded-full bg-[#7aa2f7]"></div>}
            </button>
          </div>
          <div className="text-[10px] text-text-muted text-center mt-2">
            Teoría del Caso Aumentada v0.1.0
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 relative overflow-hidden flex flex-col">
        {/* Glow de fondo */}
        <div className="absolute inset-0 bg-gradient-glow pointer-events-none opacity-50 z-0"></div>

        <div className="flex-1 overflow-y-auto p-8 relative z-10 scrollbar-custom">
          <div className="max-w-5xl mx-auto h-full flex flex-col">
            
            {/* VISTA 1: Ingesta (M3, M4, M5) */}
            {currentView === 'intake' && (
              <div className="w-full space-y-8 pb-12 animate-[fadeIn_0.3s_ease]">
                <header className="mb-8">
                  <h2 className="text-2xl font-bold mb-2">Módulo de Ingesta (M3)</h2>
                  <p className="text-text-secondary">Sube el expediente en PDF para segmentarlo y prepararlo para la Matriz HPN.</p>
                </header>

                <div className="bg-bg-card rounded-2xl border border-border-subtle p-6 relative overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-card pointer-events-none"></div>
                  
                  <div 
                    className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-250 bg-bg-input relative z-10 ${
                      dragActive ? 'border-accent-primary bg-accent-primary/5 scale-[1.01]' : 
                      file ? 'border-accent-success/50 bg-accent-success/5' : 'border-border-default hover:border-accent-primary hover:bg-accent-primary/5'
                    }`}
                    onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}
                    onClick={() => inputRef.current?.click()}
                  >
                    <input type="file" ref={inputRef} className="hidden" accept=".pdf" onChange={(e) => validateAndSetFile(e.target.files[0])} />
                    <Upload size={40} className={`mx-auto mb-4 ${file ? 'text-accent-success' : 'text-text-muted'} transition-transform duration-300 ${dragActive ? '-translate-y-2' : ''}`} />
                    <p className="text-base font-semibold mb-2">Arrastre su PDF aquí o haga clic</p>
                    <p className="text-xs text-text-secondary">Máx. 50 MB. Se procesará sin modificar el original.</p>
                  </div>

                  {file && (
                    <div className="mt-6 flex items-center gap-4 p-4 bg-accent-success/10 border border-accent-success/20 rounded-xl relative z-10">
                      <div className="w-10 h-10 rounded-lg bg-accent-success/20 flex items-center justify-center text-accent-success">
                        <File size={20} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-sm truncate">{file.name}</p>
                        <p className="text-xs text-text-secondary">{formatBytes(file.size)}</p>
                      </div>
                      <button 
                        onClick={() => { setFile(null); setResults(null); }}
                        className="w-8 h-8 rounded-md bg-accent-danger/10 text-accent-danger hover:bg-accent-danger/20 flex items-center justify-center"
                        disabled={processing}
                      >
                        <X size={16} />
                      </button>
                    </div>
                  )}

                  <div className="mt-6 relative z-10">
                    <button 
                      className="w-full py-3 px-6 rounded-xl font-semibold bg-gradient-primary text-white shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                      disabled={!file || processing || progress === 100}
                      onClick={handleProcess}
                    >
                      {processing && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>}
                      {processing ? 'Procesando expediente...' : progress === 100 ? 'Completado' : 'Subir y procesar'}
                    </button>
                  </div>

                  {/* Progreso */}
                  {(processing || progress > 0) && (
                    <div className="mt-8 relative z-10">
                      <div className="h-1.5 bg-bg-input rounded-full overflow-hidden mb-6 relative">
                        <div className="h-full bg-gradient-primary transition-all duration-500 ease-out" style={{ width: `${progress}%` }}></div>
                      </div>
                      <div className="flex flex-col gap-3">
                        {[
                          { key: 'upload', text: 'Subiendo expediente...' },
                          { key: 'process', text: 'Segmentando PDF...' },
                          { key: 'fragments', text: 'Generando fragmentos...' }
                        ].map((step, i) => (
                          <div key={step.key} className={`flex items-center gap-3 text-sm transition-colors ${
                            steps[step.key] === 'active' ? 'text-text-primary' : 
                            steps[step.key] === 'done' ? 'text-accent-success' : 'text-text-muted'
                          }`}>
                            <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center text-[10px] ${
                              steps[step.key] === 'active' ? 'border-accent-primary bg-accent-primary/20 animate-pulse' :
                              steps[step.key] === 'done' ? 'border-accent-success bg-accent-success/20' : 'border-border-subtle bg-bg-input'
                            }`}>
                              {steps[step.key] === 'done' ? '✓' : i + 1}
                            </div>
                            <span>{step.text}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {results && (
                  <div className="animate-[fadeIn_0.5s_ease] space-y-8">
                    {/* Stats Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {[
                        { label: 'Fragmentos', value: results.stats.total_fragmentos },
                        { label: 'Páginas', value: results.stats.total_paginas },
                        { label: 'Caracteres', value: results.stats.total_caracteres },
                        { label: 'Secciones', value: results.stats.secciones_detectadas.length }
                      ].map(stat => (
                        <div key={stat.label} className="bg-bg-input border border-border-subtle rounded-xl p-5 text-center">
                          <div className="text-3xl font-bold text-gradient mb-1">{formatNum(stat.value)}</div>
                          <div className="text-xs font-medium text-text-secondary uppercase">{stat.label}</div>
                        </div>
                      ))}
                    </div>

                    {/* Matriz HPN (M4 / M5) */}
                    <div className="bg-bg-card border border-border-default rounded-2xl overflow-hidden mt-8">
                      <div className="p-6 border-b border-border-subtle flex flex-col md:flex-row items-center justify-between gap-4">
                        <div>
                          <h3 className="text-xl font-bold text-text-primary flex items-center gap-2">
                            <Database size={20} className="text-accent-secondary" />
                            Matriz HPN (Agentes de Extracción)
                          </h3>
                          <p className="text-sm text-text-secondary mt-1">
                            Hechos, Pruebas y Normas extraídos automáticamente del expediente (Módulos M4 y M5).
                          </p>
                        </div>
                        
                        {!matriz && (
                          <button 
                            onClick={generateMatriz}
                            disabled={loadingMatriz}
                            className="px-6 py-2.5 bg-gradient-to-r from-accent-secondary to-accent-primary text-white font-semibold rounded-xl shadow-lg hover:shadow-accent-secondary/30 transition-all hover:-translate-y-0.5 disabled:opacity-50 flex items-center gap-2"
                          >
                            {loadingMatriz ? (
                              <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div> Procesando...</>
                            ) : (
                              <><Layers size={18} /> Generar Matriz HPN</>
                            )}
                          </button>
                        )}
                      </div>

                      <div className="p-0">
                        {!matriz ? (
                          <div className="p-12 text-center text-text-muted bg-bg-input/30">
                            <Layers size={48} className="mx-auto mb-4 opacity-50 text-accent-secondary" />
                            <p className="max-w-md mx-auto text-sm">
                              Aún no has generado la Matriz HPN para este expediente. Haz clic en el botón de arriba para que los agentes inteligentes analicen el documento.
                            </p>
                          </div>
                        ) : matriz.length === 0 ? (
                          <div className="p-12 text-center text-text-muted">No se extrajeron elementos relevantes.</div>
                        ) : (
                          <div className="overflow-x-auto scrollbar-custom">
                            <table className="w-full text-sm text-left text-text-primary">
                              <thead className="text-xs text-text-secondary uppercase bg-bg-input/50 border-b border-border-subtle">
                                <tr>
                                  <th className="px-6 py-4 font-semibold">Tipo</th>
                                  <th className="px-6 py-4 font-semibold w-1/2">Descripción Extrída</th>
                                  <th className="px-6 py-4 font-semibold">Relevancia</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-border-subtle">
                                {matriz.map((row, idx) => (
                                  <tr key={idx} className="hover:bg-bg-input/30 transition-colors group">
                                    <td className="px-6 py-4 whitespace-nowrap">
                                      <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                                        row.tipo === 'HECHO' ? 'bg-accent-primary/10 text-accent-primary-light border-accent-primary/20' :
                                        row.tipo === 'PRUEBA' ? 'bg-accent-secondary/10 text-accent-secondary border-accent-secondary/20' :
                                        row.tipo === 'NORMA' ? 'bg-accent-success/10 text-accent-success border-accent-success/20' :
                                        'bg-bg-input text-text-muted border-border-default'
                                      }`}>
                                        {row.tipo}
                                      </span>
                                    </td>
                                    <td className="px-6 py-4">
                                      <p className="leading-relaxed text-text-primary">{row.descripcion}</p>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                      <span className={`text-xs font-medium ${
                                        row.relevancia?.toLowerCase() === 'alta' ? 'text-accent-danger' : 
                                        row.relevancia?.toLowerCase() === 'media' ? 'text-accent-warning' : 'text-text-muted'
                                      }`}>
                                        {row.relevancia || 'Normal'}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* VISTA 2: Grafo M6 (Placeholder) */}
            {currentView === 'network' && (
              <div className="w-full h-full flex flex-col items-center justify-center animate-[fadeIn_0.3s_ease] text-center">
                <div className="w-24 h-24 rounded-full bg-accent-secondary/10 flex items-center justify-center mb-6 border-2 border-accent-secondary/20">
                  <Network size={40} className="text-accent-secondary" />
                </div>
                <h2 className="text-2xl font-bold mb-3">Red de Nodos Complejos (M6)</h2>
                <p className="text-text-secondary max-w-md">
                  Aquí se visualizará el grafo interactivo de relaciones basado en la Matriz HPN. Podrás explorar gráficamente cómo se conectan los actores, los hechos y las pruebas.
                </p>
                <div className="mt-8 px-4 py-2 bg-bg-input border border-border-subtle rounded-full text-xs font-mono text-text-muted">
                  En desarrollo...
                </div>
              </div>
            )}

            {/* VISTA 3: Chatbot RAG */}
            {currentView === 'chat' && results && (
              <div className="w-full h-full animate-[fadeIn_0.3s_ease] pb-6 flex flex-col">
                <header className="mb-6 flex-shrink-0">
                  <h2 className="text-2xl font-bold mb-2">Asistente Interactivo</h2>
                  <p className="text-text-secondary text-sm">Consulta el expediente a través de recuperación semántica (RAG).</p>
                </header>
                <div className="flex-1 min-h-0">
                  <ChatLayout casoId={results.casoId} />
                </div>
              </div>
            )}

          </div>
        </div>
      </main>

      {/* Toasts */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3">
        {toasts.map(t => <Toast key={t.id} message={t.message} type={t.type} onClose={() => removeToast(t.id)} />)}
      </div>

    </div>
  );
}
