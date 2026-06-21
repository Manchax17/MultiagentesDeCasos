"""
Router de Chatbot con RAG simple.

Expone endpoints para interactuar con el expediente procesado.
Soporta cambiar entre modelos de Ollama (local, default), Groq (Llama-3), Gemini (Flash).
Implementa un recuperador de contexto (RAG) basado en TF-IDF/BM25 simple (palabras clave).

Incluye endpoint para listar modelos disponibles (incluyendo modelos locales de Ollama).
"""

from __future__ import annotations

import logging
import re
import math
import requests
from collections import Counter
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from .expedientes import _casos
from ..services.ollama import ollama_disponible, listar_modelos_locales, call_ollama, get_default_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

HF_CHAT_DEFAULT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
HF_CHAT_LIGHT_MODEL = "HuggingFaceH4/zephyr-7b-beta"
HF_CHAT_EXTRACTION_MODEL = "google/flan-t5-large"

# ── Configuraciones de Modelos ─────────────────

GROQ_API_KEY = settings.groq_api_key
GEMINI_API_KEY = settings.gemini_api_key

# ── Modelos de Datos ───────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" o "assistant"
    content: str

class ChatRequest(BaseModel):
    caso_id: str
    message: str
    model: str = "ollama"  # "ollama" (default), "gemini", "groq", "huggingface"
    ollama_model: str | None = None  # None = auto-detectar
    hf_model: str | None = None
    history: list[ChatMessage] = []

class ContextFragment(BaseModel):
    fragmento_id: str
    pagina: int
    seccion: str
    texto: str
    score: float

class ChatResponse(BaseModel):
    response: str
    context_used: list[ContextFragment] = []

# ── Lógica de Recuperación (RAG Simple) ─────────

def tokenize(text: str) -> list[str]:
    """Tokeniza el texto en palabras minúsculas, ignorando puntuación."""
    return re.findall(r'\b[a-záéíóúñ]+\b', text.lower())

def simple_rag_search(query: str, fragmentos: list, top_k: int = 3) -> list[dict]:
    """
    Realiza una búsqueda simple basada en frecuencia de términos (similar a TF-IDF)
    para encontrar los fragmentos más relevantes a la pregunta.
    """
    if not fragmentos:
        return []

    query_tokens = set(tokenize(query))
    if not query_tokens:
        return []

    scored_fragments = []
    
    for frag in fragmentos:
        texto = frag.texto
        frag_tokens = tokenize(texto)
        if not frag_tokens:
            continue
            
        frag_counts = Counter(frag_tokens)
        score = 0.0
        
        # Puntuación simple: tf * idf (simplificado)
        for q_token in query_tokens:
            if q_token in frag_counts:
                # Frecuencia del término en el documento
                tf = frag_counts[q_token] / len(frag_tokens)
                score += tf
                
        if score > 0:
            scored_fragments.append({
                "fragmento": frag,
                "score": score
            })
            
    # Ordenar por puntuación descendente
    scored_fragments.sort(key=lambda x: x["score"], reverse=True)
    return scored_fragments[:top_k]

# ── Integraciones de LLMs (usando requests) ──────

SYSTEM_PROMPT_CHAT = (
    "Eres un asistente jurídico experto en análisis de expedientes. "
    "Responde basándote estrictamente en el contexto proporcionado. "
    "Si no sabes la respuesta o no está en el contexto, dilo claramente."
)

def call_groq(prompt: str, history: list[ChatMessage]) -> str:
    """Llama a la API de Groq usando Llama-3."""
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY no configurada. Use Ollama (modelo local) en su lugar."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_CHAT}
    ]
    
    # Remover el primer saludo del asistente para no romper el orden (user->assistant)
    if history and history[0].role == "assistant" and len(history) == 1:
        history = []
    elif history and history[0].role == "assistant":
        history = history[1:]
        
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
        
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": "llama-3.3-70b-versatile", 
        "messages": messages,
        "temperature": 0.2,
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"[Groq API Error] {e}")
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
            error_detail = e.response.text
            logger.error(f"Response: {error_detail}")
        return f"Error al contactar a Groq:\n{error_detail}"

def call_gemini(prompt: str, history: list[ChatMessage]) -> str:
    """Llama a la API de Gemini (Google) usando Gemini 1.5 Flash."""
    if not GEMINI_API_KEY:
        return "Error: GEMINI_API_KEY no configurada. Use Ollama (modelo local) en su lugar."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    headers = {
        "Content-Type": "application/json"
    }
    
    # Remover el primer saludo del asistente para no romper el orden
    if history and history[0].role == "assistant" and len(history) == 1:
        history = []
    elif history and history[0].role == "assistant":
        history = history[1:]
        
    contents = []
    system_prompt = SYSTEM_PROMPT_CHAT + "\n\n"
    
    for i, msg in enumerate(history):
        role = "user" if msg.role == "user" else "model"
        text = msg.content
        if i == 0 and role == "user":
            text = system_prompt + text
            
        contents.append({
            "role": role,
            "parts": [{"text": text}]
        })
        
    # Si no había historial, aseguramos de inyectar el system prompt
    final_text = prompt
    if not history:
        final_text = system_prompt + prompt
        
    contents.append({
        "role": "user",
        "parts": [{"text": final_text}]
    })
    
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return "El modelo no devolvió una respuesta válida."
    except Exception as e:
        logger.error(f"[Gemini API Error] {e}")
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
            error_detail = e.response.text
            logger.error(f"Response: {error_detail}")
        return f"Error al contactar a Gemini:\n{error_detail}"


def call_huggingface(prompt: str, history: list[ChatMessage], hf_model: str | None) -> str:
    """Llama a un modelo juridico de Hugging Face Inference API."""
    model_id = hf_model or HF_CHAT_DEFAULT_MODEL
    url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Content-Type": "application/json"}
    hf_token = getattr(settings, "hf_api_token", "")
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    hist = [{"role": m.role, "content": m.content} for m in history] if history else []
    prompt_lines = [SYSTEM_PROMPT_CHAT]
    for msg in hist:
        prompt_lines.append(f"{msg['role'].upper()}: {msg['content']}")
    prompt_lines.append(f"USER: {prompt}")
    final_prompt = "\n".join(prompt_lines)

    payload = {
        "inputs": final_prompt,
        "parameters": {
            "temperature": 0.2,
            "max_new_tokens": 1024,
            "return_full_text": False,
        },
        "options": {
            "wait_for_model": True,
            "use_cache": False,
        },
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            return data[0].get("generated_text") or data[0].get("summary_text") or "El modelo no devolvio una respuesta valida."
        if isinstance(data, dict):
            return data.get("generated_text") or data.get("summary_text") or data.get("text") or "El modelo no devolvio una respuesta valida."
        return "El modelo no devolvio una respuesta valida."
    except Exception as e:
        logger.error(f"[HuggingFace API Error] {e}")
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
            error_detail = e.response.text
            logger.error(f"Response: {error_detail}")
        return f"Error al contactar a Hugging Face:\n{error_detail}"


def _call_ollama_chat(prompt: str, history: list[ChatMessage], ollama_model: str | None) -> str:
    """Llama a Ollama para el chat."""
    if ollama_model is None:
        ollama_model = get_default_model()
    hist = [{"role": m.role, "content": m.content} for m in history] if history else None
    return call_ollama(
        prompt=prompt,
        history=hist,
        model=ollama_model,
        temperature=0.2,
        system_prompt=SYSTEM_PROMPT_CHAT,
    )


# ── Endpoint de Modelos Disponibles ────────────

@router.get("/modelos")
async def listar_modelos():
    """
    Lista todos los modelos disponibles para el chat.
    Incluye proveedores cloud (Groq, Gemini) y modelos locales de Ollama.
    """
    modelos = {
        "cloud": [
            {
                "provider": "groq",
                "name": "Llama 3.3 70B",
                "model_id": "llama-3.3-70b-versatile",
                "available": bool(GROQ_API_KEY),
                "requires_key": True,
            },
            {
                "provider": "gemini",
                "name": "Gemini 1.5 Flash",
                "model_id": "gemini-1.5-flash-latest",
                "available": bool(GEMINI_API_KEY),
                "requires_key": True,
            },
        ],
        "huggingface": [
            {
                "provider": "huggingface",
                "name": "Mistral 7B Instruct v0.3",
                "model_id": HF_CHAT_DEFAULT_MODEL,
                "available": True,
                "requires_key": bool(getattr(settings, "hf_api_token", "")),
            },
            {
                "provider": "huggingface",
                "name": "Zephyr 7B Beta",
                "model_id": HF_CHAT_LIGHT_MODEL,
                "available": True,
                "requires_key": bool(getattr(settings, "hf_api_token", "")),
            },
            {
                "provider": "huggingface",
                "name": "Flan-T5 Large",
                "model_id": HF_CHAT_EXTRACTION_MODEL,
                "available": True,
                "requires_key": bool(getattr(settings, "hf_api_token", "")),
            },
        ],
        "local": [],
        "ollama_available": False,
        "default_model": settings.default_model,
        "default_ollama_model": settings.default_ollama_model,
    }

    # Detectar modelos locales de Ollama
    if ollama_disponible():
        modelos["ollama_available"] = True
        modelos["local"] = listar_modelos_locales()
        modelos["default_ollama_model"] = get_default_model()

    return modelos


# ── Endpoint Principal ─────────────────────────

@router.post("", response_model=ChatResponse)
async def chat_with_document(req: ChatRequest):
    """
    Recibe un mensaje, busca fragmentos relevantes en el expediente (RAG),
    y devuelve la respuesta del modelo seleccionado.
    """
    if req.caso_id not in _casos:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
        
    caso = _casos[req.caso_id]
    indice = caso.get("indice")
    
    if not indice or not indice.fragmentos:
        raise HTTPException(status_code=400, detail="El expediente aún no ha sido procesado o no tiene fragmentos.")

    # 1. Recuperar contexto (RAG)
    top_fragments = simple_rag_search(req.message, indice.fragmentos, top_k=5)
    
    context_text = ""
    context_used = []
    
    if top_fragments:
        for i, item in enumerate(top_fragments):
            frag = item["fragmento"]
            score = item["score"]
            context_text += f"\n--- Fragmento {i+1} (Pág. {frag.pagina}, {frag.seccion}) ---\n{frag.texto}\n"
            
            context_used.append(ContextFragment(
                fragmento_id=frag.fragmento_id,
                pagina=frag.pagina,
                seccion=frag.seccion.value,
                texto=frag.texto,
                score=score
            ))
            
    # 2. Construir el prompt con el contexto
    prompt = f"Pregunta del usuario: {req.message}\n"
    if context_text:
        prompt += f"\nContexto del expediente encontrado:\n{context_text}\n"
        prompt += "\nPor favor, responde a la pregunta basándote únicamente en los fragmentos anteriores. Si los fragmentos no contienen la respuesta, indícalo."
    else:
        prompt += "\n(No se encontró contexto directamente relevante en el expediente, pero responde según el historial si aplica)."

    # 3. Llamar al modelo
    if req.model.lower() == "gemini":
        respuesta_llm = call_gemini(prompt, req.history)
    elif req.model.lower() == "groq":
        respuesta_llm = call_groq(prompt, req.history)
    elif req.model.lower() in {"huggingface", "hf"}:
        respuesta_llm = call_huggingface(prompt, req.history, req.hf_model)
    else:
        # Default: Ollama
        respuesta_llm = _call_ollama_chat(prompt, req.history, req.ollama_model)
        
    return ChatResponse(
        response=respuesta_llm,
        context_used=context_used
    )
