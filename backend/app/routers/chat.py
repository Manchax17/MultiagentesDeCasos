"""
Router de Chatbot con RAG simple.

Expone el endpoint para interactuar con el expediente procesado.
Soporta cambiar entre modelos de Groq (Llama-3) y Gemini (Flash).
Implementa un recuperador de contexto (RAG) basado en TF-IDF/BM25 simple (palabras clave).
"""

from __future__ import annotations

import logging
import re
import math
import requests
import os
from collections import Counter
from typing import Optional
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .expedientes import _casos
load_dotenv()


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# ── Configuraciones de Modelos ─────────────────

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ── Modelos de Datos ───────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" o "assistant"
    content: str

class ChatRequest(BaseModel):
    caso_id: str
    message: str
    model: str  # "gemini" o "groq"
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

def call_groq(prompt: str, history: list[ChatMessage]) -> str:
    """Llama a la API de Groq usando Llama-3."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = [
        {"role": "system", "content": "Eres un asistente jurídico experto en análisis de expedientes. Responde basándote estrictamente en el contexto proporcionado. Si no sabes la respuesta o no está en el contexto, dilo claramente."}
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
    system_prompt = "Eres un asistente jurídico experto en análisis de expedientes. Responde basándote estrictamente en el contexto proporcionado. Si no sabes la respuesta o no está en el contexto, dilo claramente.\n\n"
    
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
    else:
        respuesta_llm = call_groq(prompt, req.history)
        
    return ChatResponse(
        response=respuesta_llm,
        context_used=context_used
    )
