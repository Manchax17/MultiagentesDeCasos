import React, { useState, useRef, useEffect } from 'react';
import { Upload, FileText, CheckCircle2, XCircle, FileJson, File, X, Info, ChevronDown, ChevronRight, MessageSquare, Network, Layers, Database } from 'lucide-react';
import ChatLayout from './ChatLayout';

const API_BASE = 'http://localhost:8000';
const HF_CHAT_DEFAULT_MODEL = 'mistralai/Mistral-7B-Instruct-v0.3';
const HF_CHAT_LIGHT_MODEL = 'HuggingFaceH4/zephyr-7b-beta';
const HF_CHAT_EXTRACTION_MODEL = 'google/flan-t5-large';

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
  const [hpnData, setHpnData] = useState(null);
  const [loadingMatriz, setLoadingMatriz] = useState(false);
  const [matrizProgress, setMatrizProgress] = useState('');
  const [hpnProvider, setHpnProvider] = useState('auto');
  const [ollamaModels, setOllamaModels] = useState([]);
  const [defaultOllamaModel, setDefaultOllamaModel] = useState('llama3.2');
  const [selectedOllamaModel, setSelectedOllamaModel] = useState('');
  const [hfLegalModels, setHfLegalModels] = useState([]);
  const [selectedHfModel, setSelectedHfModel] = useState(HF_CHAT_DEFAULT_MODEL);

  useEffect(() => {
    let isMounted = true;

    const loadModels = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/chat/modelos`);
        if (!res.ok) return;
        const data = await res.json();
        const localModels = (data.local || []).map(modelo => modelo.name).filter(Boolean);
        const fallback = data.default_ollama_model || 'llama3.2';
        const hfModels = (data.huggingface || []).map(modelo => modelo.model_id).filter(Boolean);

        if (!isMounted) return;
        setOllamaModels(localModels);
        setDefaultOllamaModel(fallback);
        setSelectedOllamaModel(prev => prev || fallback);
        setHfLegalModels(hfModels);
        setSelectedHfModel(prev => prev || (hfModels[0] || HF_CHAT_DEFAULT_MODEL));
      } catch (error) {
        if (!isMounted) return;
        setOllamaModels([]);
        setDefaultOllamaModel('llama3.2');
        setSelectedOllamaModel(prev => prev || 'llama3.2');
        setHfLegalModels([]);
        setSelectedHfModel(prev => prev || HF_CHAT_DEFAULT_MODEL);
      }
    };

    loadModels();

    return () => {
      isMounted = false;
    };
  }, []);

  const fetchMatriz = async (casoId) => {
    try {
      const res = await fetch(`${API_BASE}/api/expedientes/${casoId}/matriz`);
      if (res.ok) {
        const data = await res.json();
        if (data.filas_hpn) {
          setHpnData(data);
        }
      }
    } catch (e) {
      console.error("Error fetching matriz", e);
    }
  };

  const resolveEntity = (id, tipo) => {
    if (!hpnData || !id) return id || '-';
    const list = hpnData[tipo] || [];
    const item = list.find(e => {
      if (tipo === 'hechos') return e.hecho_id === id;
      if (tipo === 'pruebas') return e.prueba_id === id;
      if (tipo === 'normas') return e.norma_id === id;
      return false;
    });
    if (!item) return id;
    if (tipo === 'normas') return item.referencia || item.descripcion || id;
    return item.descripcion || id;
  };

  const updateFila = async (filaId, updates) => {
    if (!results?.casoId) return;
    try {
      const res = await fetch(`${API_BASE}/api/expedientes/${results.casoId}/matriz/${filaId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error('Error al actualizar fila');
      const data = await res.json();
      setHpnData(prev => ({
        ...prev,
        filas_hpn: prev.filas_hpn.map(f => f.fila_id === filaId ? data.fila : f),
        auditoria: data.auditoria || prev.auditoria,
      }));
      addToast('Fila actualizada', 'success');
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const deleteFila = async (filaId) => {
    if (!results?.casoId) return;
    try {
      const res = await fetch(`${API_BASE}/api/expedientes/${results.casoId}/matriz/${filaId}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Error al eliminar fila');
      const data = await res.json();
      setHpnData(prev => ({
        ...prev,
        filas_hpn: prev.filas_hpn.filter(f => f.fila_id !== filaId),
        auditoria: data.auditoria || prev.auditoria,
      }));
      addToast('Fila eliminada', 'success');
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const generateMatriz = async () => {
    if (!results) return;
    setLoadingMatriz(true);
    setMatrizProgress('Iniciando agentes M4/M5/M8...');
    addToast('Ejecutando Agentes de Inteligencia Artificial...', 'info');
    try {
      const res = await fetch(`${API_BASE}/api/expedientes/${results.casoId}/matriz`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: hpnProvider,
          ollama_model: hpnProvider === 'ollama' ? (selectedOllamaModel || defaultOllamaModel) : null,
          hf_model: hpnProvider === 'huggingface' ? selectedHfModel : null,
          pausa_segundos: 1.5,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Error generando matriz HPN');
      }
      const data = await res.json();
      setHpnData(data);
      const alertas = data.auditoria?.length || 0;
      const filas = data.filas_hpn?.length || 0;
      addToast(`Matriz HPN generada: ${filas} filas, ${alertas} alertas de auditoría`, 'success');
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoadingMatriz(false);
      setMatrizProgress('');
    }
  };

  const exportCSV = async () => {
    if (!results?.casoId) {
      addToast('No hay caso para exportar', 'error');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/expedientes/${results.casoId}/matriz/export?format=csv`);
      if (!res.ok) throw new Error('Error al exportar CSV');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `matriz_hpn_${results.casoId}.csv`;
      link.click();
      URL.revokeObjectURL(url);
      addToast('Exportación CSV completada', 'success');
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const matriz = hpnData?.filas_hpn || null;
  const auditoria = hpnData?.auditoria || [];

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
    setHpnData(null);
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
                        
                        <div className="flex flex-col gap-3 items-stretch md:items-end">
                          <div className="flex items-center gap-2 text-xs text-text-muted flex-wrap justify-end">
                            <span className="font-semibold uppercase tracking-wider">Proveedor</span>
                            <select
                              value={hpnProvider}
                              onChange={(e) => setHpnProvider(e.target.value)}
                              className="bg-bg-input border border-border-default rounded-md px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-accent-primary transition-colors cursor-pointer"
                            >
                              <option value="auto">Auto (Groq → Ollama)</option>
                              <option value="groq">Groq</option>
                              <option value="ollama">Ollama</option>
                              <option value="gemini">Gemini</option>
                              <option value="huggingface">Hugging Face juridico</option>
                            </select>
                            {hpnProvider === 'ollama' && (
                              <>
                                <span className="font-semibold uppercase tracking-wider">Modelo</span>
                                <select
                                  value={selectedOllamaModel}
                                  onChange={(e) => setSelectedOllamaModel(e.target.value)}
                                  className="bg-bg-input border border-border-default rounded-md px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-accent-primary transition-colors cursor-pointer min-w-44"
                                >
                                  {ollamaModels.length > 0 ? (
                                    ollamaModels.map(name => (
                                      <option key={name} value={name}>{name}</option>
                                    ))
                                  ) : (
                                    <option value={defaultOllamaModel}>{defaultOllamaModel}</option>
                                  )}
                                </select>
                              </>
                            )}
                            {hpnProvider === 'huggingface' && (
                              <>
                                <span className="font-semibold uppercase tracking-wider">Modelo juridico</span>
                                <select
                                  value={selectedHfModel}
                                  onChange={(e) => setSelectedHfModel(e.target.value)}
                                  className="bg-bg-input border border-border-default rounded-md px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-accent-primary transition-colors cursor-pointer min-w-44"
                                >
                                  {(hfLegalModels.length > 0 ? hfLegalModels : [HF_CHAT_DEFAULT_MODEL, HF_CHAT_LIGHT_MODEL, HF_CHAT_EXTRACTION_MODEL]).map(name => (
                                    <option key={name} value={name}>{name}</option>
                                  ))}
                                </select>
                              </>
                            )}
                          </div>
                          <div className="flex gap-2 justify-end flex-wrap">
                          <button 
                            onClick={generateMatriz}
                            disabled={loadingMatriz}
                            className="px-6 py-2.5 bg-gradient-to-r from-accent-secondary to-accent-primary text-white font-semibold rounded-xl shadow-lg hover:shadow-accent-secondary/30 transition-all hover:-translate-y-0.5 disabled:opacity-50 flex items-center gap-2"
                          >
                            {loadingMatriz ? (
                              <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div> Procesando...</>
                            ) : (
                              <><Layers size={18} /> {matriz ? 'Regenerar Matriz HPN' : 'Generar Matriz HPN'}</>
                            )}
                          </button>
                          {matriz && matriz.length > 0 && (
                            <button 
                              onClick={exportCSV}
                              className="px-4 py-2.5 bg-bg-input border border-border-default hover:border-accent-primary text-text-primary font-semibold rounded-xl transition-all hover:-translate-y-0.5 flex items-center gap-2"
                            >
                              📥 Exportar CSV
                            </button>
                          )}
                          </div>
                          {loadingMatriz && matrizProgress && (
                            <p className="text-xs text-text-muted text-right">{matrizProgress}</p>
                          )}
                        </div>
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
                          <div className="p-12 text-center text-text-muted space-y-2">
                            <p>No se generaron filas HPN útiles.</p>
                            <p className="text-xs max-w-md mx-auto">
                              Esto no siempre significa error: a veces el expediente no deja vínculos suficientes entre hechos, pruebas y normas, o el modelo devolvió una matriz muy conservadora.
                            </p>
                          </div>
                        ) : (
                          <>
                          <div className="overflow-x-auto scrollbar-custom">
                            <table className="w-full text-sm text-left text-text-primary">
                              <thead className="text-xs text-text-secondary uppercase bg-bg-input/50 border-b border-border-subtle">
                                <tr>
                                  <th className="px-4 py-4 font-semibold">Fila</th>
                                  <th className="px-4 py-4 font-semibold">Elemento</th>
                                  <th className="px-4 py-4 font-semibold min-w-[180px]">Hecho</th>
                                  <th className="px-4 py-4 font-semibold min-w-[160px]">Pruebas</th>
                                  <th className="px-4 py-4 font-semibold min-w-[140px]">Normas</th>
                                  <th className="px-4 py-4 font-semibold">Fuente</th>
                                  <th className="px-4 py-4 font-semibold">Estado</th>
                                  <th className="px-4 py-4 font-semibold">Riesgo</th>
                                  <th className="px-4 py-4 font-semibold min-w-[140px]">Acción</th>
                                  <th className="px-4 py-4 font-semibold">Editar</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-border-subtle">
                                {matriz.map((row, idx) => (
                                  <tr key={row.fila_id || idx} className="hover:bg-bg-input/30 transition-colors group align-top">
                                    <td className="px-4 py-4 whitespace-nowrap">
                                      <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border bg-accent-primary/10 text-accent-primary-light border-accent-primary/20">
                                        {row.fila_id || `F-${String(idx + 1).padStart(3, '0')}`}
                                      </span>
                                    </td>
                                    <td className="px-4 py-4 text-xs text-text-secondary max-w-[120px]">
                                      {row.elemento_juridico || 'Por determinar'}
                                    </td>
                                    <td className="px-4 py-4">
                                      <p className="leading-relaxed text-text-primary text-xs">{resolveEntity(row.hecho_id, 'hechos')}</p>
                                      <span className="text-[10px] text-text-muted font-mono">{row.hecho_id}</span>
                                    </td>
                                    <td className="px-4 py-4">
                                      {(row.prueba_ids || []).length > 0 ? row.prueba_ids.map(id => (
                                        <p key={id} className="text-xs text-text-secondary mb-1">{resolveEntity(id, 'pruebas')}</p>
                                      )) : <span className="text-text-muted text-xs">Sin pruebas</span>}
                                    </td>
                                    <td className="px-4 py-4">
                                      {(row.norma_ids || []).length > 0 ? row.norma_ids.map(id => (
                                        <p key={id} className="text-xs text-text-secondary mb-1">{resolveEntity(id, 'normas')}</p>
                                      )) : <span className="text-text-muted text-xs">Sin normas</span>}
                                    </td>
                                    <td className="px-4 py-4 whitespace-nowrap text-xs text-text-muted">
                                      Pág. {row.fuente_expediente?.pagina ?? '-'}
                                    </td>
                                    <td className="px-4 py-4 whitespace-nowrap">
                                      <select
                                        value={row.estado_epistemico || 'por_evaluar'}
                                        onChange={(e) => updateFila(row.fila_id, { estado_epistemico: e.target.value })}
                                        className={`text-xs font-medium px-2 py-1 rounded-full border bg-transparent cursor-pointer ${
                                          (row.estado_epistemico || '').toLowerCase() === 'probado' ? 'text-accent-success border-accent-success/20' :
                                          (row.estado_epistemico || '').toLowerCase() === 'controvertido' ? 'text-accent-warning border-accent-warning/20' :
                                          (row.estado_epistemico || '').toLowerCase() === 'sin_prueba' ? 'text-accent-danger border-accent-danger/20' :
                                          'text-text-muted border-border-default'
                                        }`}
                                      >
                                        <option value="probado">probado</option>
                                        <option value="controvertido">controvertido</option>
                                        <option value="sin_prueba">sin_prueba</option>
                                        <option value="por_evaluar">por_evaluar</option>
                                      </select>
                                    </td>
                                    <td className="px-4 py-4 whitespace-nowrap">
                                      <select
                                        value={row.riesgo || 'medio'}
                                        onChange={(e) => updateFila(row.fila_id, { riesgo: e.target.value })}
                                        className="text-xs bg-bg-input border border-border-default rounded-md px-2 py-1 cursor-pointer"
                                      >
                                        <option value="bajo">bajo</option>
                                        <option value="medio">medio</option>
                                        <option value="alto">alto</option>
                                        <option value="critico">critico</option>
                                      </select>
                                    </td>
                                    <td className="px-4 py-4 text-xs text-text-secondary max-w-[160px]">
                                      {row.accion_sugerida || '-'}
                                    </td>
                                    <td className="px-4 py-4 whitespace-nowrap">
                                      <button
                                        onClick={() => deleteFila(row.fila_id)}
                                        className="text-xs text-accent-danger hover:bg-accent-danger/10 px-2 py-1 rounded-md transition-colors"
                                      >
                                        Eliminar
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>

                          {auditoria.length > 0 && (
                            <div className="p-6 border-t border-border-subtle bg-bg-input/20">
                              <h4 className="text-sm font-bold text-text-primary mb-3">
                                Auditoría M8 — {auditoria.length} alertas en {matriz.length} filas
                              </h4>
                              <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-custom">
                                {['critica', 'alta', 'media'].map(sev => {
                                  const items = auditoria.filter(a => a.severidad === sev);
                                  if (items.length === 0) return null;
                                  return (
                                    <div key={sev}>
                                      <p className="text-[10px] font-bold uppercase tracking-wider text-text-muted mb-1">{sev}</p>
                                      {items.slice(0, 15).map((alert, i) => (
                                        <div key={i} className={`text-xs px-3 py-2 rounded-lg mb-1 border ${
                                          sev === 'critica' ? 'border-accent-danger/30 bg-accent-danger/5 text-accent-danger' :
                                          sev === 'alta' ? 'border-accent-warning/30 bg-accent-warning/5 text-accent-warning' :
                                          'border-border-default bg-bg-input/50 text-text-secondary'
                                        }`}>
                                          <span className="font-mono font-bold">{alert.codigo}</span>
                                          {alert.fila_id && <span className="ml-2 opacity-70">[{alert.fila_id}]</span>}
                                          <span className="ml-2">{alert.mensaje}</span>
                                        </div>
                                      ))}
                                      {items.length > 15 && (
                                        <p className="text-[10px] text-text-muted ml-2">+{items.length - 15} alertas más...</p>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                          </>
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
