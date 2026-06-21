import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, FileText, ChevronRight, ChevronDown, Layers, Loader2 } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

const ChatMessage = ({ msg }) => {
  const isUser = msg.role === 'user';
  const [showContext, setShowContext] = useState(false);

  return (
    <div className={`flex gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'} mb-6 animate-[fadeIn_0.3s_ease]`}>
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
        isUser ? 'bg-gradient-primary text-white shadow-lg' : 'bg-bg-input border border-border-default text-accent-primary'
      }`}>
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>
      
      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[80%]`}>
        <div className={`p-4 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
          isUser 
            ? 'bg-bg-input border border-border-subtle text-text-primary rounded-tr-sm' 
            : 'bg-bg-card border border-border-default shadow-sm rounded-tl-sm'
        }`}>
          {msg.content}
        </div>

        {/* Contexto usado (Solo para mensajes del asistente que tengan contexto) */}
        {!isUser && msg.context_used && msg.context_used.length > 0 && (
          <div className="mt-2 w-full max-w-md">
            <button 
              onClick={() => setShowContext(!showContext)}
              className="flex items-center gap-1.5 text-xs text-text-muted hover:text-accent-primary transition-colors"
            >
              {showContext ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <FileText size={14} />
              Ver contexto del expediente ({msg.context_used.length} fragmentos)
            </button>
            
            {showContext && (
              <div className="mt-2 space-y-2">
                {msg.context_used.map((ctx, idx) => (
                  <div key={idx} className="bg-bg-input border border-border-subtle rounded-lg p-3 text-xs text-text-secondary">
                    <div className="flex items-center justify-between mb-1 text-text-muted font-medium">
                      <span>Pág. {ctx.pagina}</span>
                      <span className="uppercase text-[10px] bg-bg-card px-1.5 py-0.5 rounded border border-border-subtle">{ctx.seccion}</span>
                    </div>
                    <div className="line-clamp-3 hover:line-clamp-none transition-all">{ctx.texto}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default function ChatLayout({ casoId, onBack }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: '¡Hola! He analizado el expediente judicial. ¿Qué te gustaría saber o consultar sobre el caso?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [model, setModel] = useState('ollama'); // ollama, gemini o groq
  const [ollamaModels, setOllamaModels] = useState([]);
  const [defaultOllamaModel, setDefaultOllamaModel] = useState('llama3.2');
  const [selectedOllamaModel, setSelectedOllamaModel] = useState('');
  const [hfLegalModels, setHfLegalModels] = useState([]);
  const [selectedHfModel, setSelectedHfModel] = useState('ayushhh1662309/legal-chatbot-llama3-8b-Q5-K_M-gguf');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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
        setSelectedHfModel(prev => prev || (hfModels[0] || 'ayushhh1662309/legal-chatbot-llama3-8b-Q5-K_M-gguf'));
      } catch (error) {
        if (!isMounted) return;
        setOllamaModels([]);
        setDefaultOllamaModel('llama3.2');
        setSelectedOllamaModel(prev => prev || 'llama3.2');
        setHfLegalModels([]);
        setSelectedHfModel(prev => prev || 'ayushhh1662309/legal-chatbot-llama3-8b-Q5-K_M-gguf');
      }
    };

    loadModels();

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = { role: 'user', content: input.trim() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      // Filtrar el historial (solo enviamos contenido y rol al backend)
      const history = messages
        .filter(m => m.role !== 'system') // Si hubiera system
        .map(m => ({ role: m.role, content: m.content }));

      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          caso_id: casoId,
          message: userMessage.content,
          model: model,
          ollama_model: model === 'ollama' ? (selectedOllamaModel || defaultOllamaModel) : null,
          hf_model: model === 'huggingface' ? selectedHfModel : null,
          history: history
        })
      });

      if (!res.ok) throw new Error('Error al procesar la pregunta');
      const data = await res.json();

      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: data.response,
        context_used: data.context_used
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Hubo un error al conectar con el servidor. Por favor, intenta de nuevo.' 
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-bg-card relative w-full rounded-2xl border border-border-subtle overflow-hidden">
      
      {/* Top Header */}
      <div className="flex items-center justify-between p-4 border-b border-border-subtle bg-bg-input">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent-primary/10 flex items-center justify-center text-accent-primary">
            <Bot size={18} />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Asistente Interactivo</h2>
            <p className="text-[10px] text-text-secondary">Conectado al expediente</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Layers size={14} className="text-text-muted" />
          <select 
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="bg-bg-card border border-border-default rounded-md px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-accent-primary transition-colors cursor-pointer"
          >
            <option value="ollama">Ollama (Local)</option>
            <option value="huggingface">Hugging Face juridico</option>
            <option value="groq">Llama-3 70B (Groq)</option>
            <option value="gemini">Gemini 1.5 Flash (Google)</option>
          </select>
        </div>
        {model === 'ollama' && (
          <div className="mt-3 flex items-center gap-2 justify-end">
            <span className="text-[10px] uppercase tracking-wider text-text-muted font-semibold">Modelo local</span>
            <select
              value={selectedOllamaModel}
              onChange={(e) => setSelectedOllamaModel(e.target.value)}
              className="bg-bg-card border border-border-default rounded-md px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-accent-primary transition-colors cursor-pointer min-w-44"
            >
              {ollamaModels.length > 0 ? (
                ollamaModels.map(name => (
                  <option key={name} value={name}>{name}</option>
                ))
              ) : (
                <option value={defaultOllamaModel}>{defaultOllamaModel}</option>
              )}
            </select>
          </div>
        )}
        {model === 'huggingface' && (
          <div className="mt-3 flex items-center gap-2 justify-end">
            <span className="text-[10px] uppercase tracking-wider text-text-muted font-semibold">Modelo juridico</span>
            <select
              value={selectedHfModel}
              onChange={(e) => setSelectedHfModel(e.target.value)}
              className="bg-bg-card border border-border-default rounded-md px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-accent-primary transition-colors cursor-pointer min-w-44"
            >
              {(hfLegalModels.length > 0 ? hfLegalModels : ['ayushhh1662309/legal-chatbot-llama3-8b-Q5-K_M-gguf', 'starxicn/LAW-GPT', 'Dorado607/LawGPT_zh']).map(name => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative min-h-0">
        <div className="absolute inset-0 bg-gradient-card pointer-events-none opacity-50"></div>
        
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-custom relative z-10">
          {messages.map((msg, idx) => (
            <ChatMessage key={idx} msg={msg} />
          ))}
          {loading && (
            <div className="flex gap-4 mb-6 animate-[fadeIn_0.3s_ease]">
              <div className="w-10 h-10 rounded-xl bg-bg-input border border-border-default text-accent-primary flex items-center justify-center">
                <Bot size={20} />
              </div>
              <div className="p-4 rounded-2xl bg-bg-card border border-border-default shadow-sm rounded-tl-sm flex items-center gap-2">
                <Loader2 size={16} className="animate-spin text-accent-primary" />
                <span className="text-sm text-text-muted">Analizando expediente...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-border-subtle bg-bg-card/80 backdrop-blur-md relative z-10">
          <form 
            onSubmit={handleSend}
            className="flex items-end gap-2 bg-bg-input border border-border-default focus-within:border-accent-primary rounded-xl p-2 transition-colors max-w-4xl mx-auto"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Pregunta sobre los hechos, normas, o actores del caso..."
              className="flex-1 bg-transparent border-none focus:ring-0 resize-none max-h-32 min-h-[44px] py-3 px-3 text-sm text-text-primary scrollbar-custom outline-none"
              rows="1"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="p-3 rounded-lg bg-gradient-primary text-white disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-md hover:shadow-accent-primary/20 transition-all flex-shrink-0 mb-0.5"
            >
              <Send size={18} />
            </button>
          </form>
          <div className="text-center mt-2 text-[10px] text-text-muted">
            El asistente usa el expediente extraído como contexto principal, pero puede cometer errores. Verifica siempre la información.
          </div>
        </div>
      </div>
    </div>
  );
}
