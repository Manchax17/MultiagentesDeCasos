"""
Servicio de integración con Ollama (modelos locales).

Detecta automáticamente los modelos instalados en la máquina local
a través de la API REST de Ollama (http://localhost:11434).
No requiere API key — Ollama corre como servicio local.
"""

from __future__ import annotations

import logging
import time
import re
from typing import Optional

import requests

from ..config import settings

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = settings.ollama_base_url
OLLAMA_TIMEOUT = 180 # Reducido para depuración
OLLAMA_NUM_CTX = settings.ollama_num_ctx


def ollama_disponible() -> bool:
    """Verifica si Ollama está corriendo localmente."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def listar_modelos_locales() -> list[dict]:
    """
    Detecta todos los modelos instalados en Ollama.
    
    Returns:
        Lista de dicts con {name, size, modified_at, details} por modelo.
        Lista vacía si Ollama no está disponible.
    """
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        r.raise_for_status()
        data = r.json()
        modelos = data.get("models", [])
        return [
            {
                "name": m.get("name", ""),
                "size": m.get("size", 0),
                "modified_at": m.get("modified_at", ""),
                "family": m.get("details", {}).get("family", "desconocido"),
                "parameter_size": m.get("details", {}).get("parameter_size", ""),
                "quantization": m.get("details", {}).get("quantization_level", ""),
            }
            for m in modelos
        ]
    except Exception as e:
        logger.warning(f"[Ollama] No disponible o error al listar modelos: {e}")
        return []


def get_default_model() -> str:
    """
    Detecta el mejor modelo disponible en Ollama.
    Prioridad: el configurado en settings > llama3.2 > cualquiera disponible.
    """
    modelos = listar_modelos_locales()
    if not modelos:
        return settings.default_ollama_model

    nombres = [m["name"] for m in modelos]

    # Prioridad 1: el modelo configurado
    if settings.default_ollama_model in nombres:
        return settings.default_ollama_model

    # Prioridad 2: buscar variantes comunes
    preferidos = ["deepseek-r1:1.5b", "deepseek-r1", "llama3.2", "llama3.2:latest", "llama3.1", "llama3",
                  "mistral", "mistral:latest", "hermes3:8b", "qwen2.5"]
    for pref in preferidos:
        for nombre in nombres:
            if pref in nombre:
                return nombre

    # Prioridad 3: el primero disponible
    return nombres[0]


def call_ollama(
    prompt: str,
    history: list[dict] | None = None,
    model: str | None = None,
    temperature: float = 0.05,
    system_prompt: str | None = None,
    num_ctx: int | None = None,
) -> str:
    """
    Llama a un modelo local de Ollama usando la API de chat.
    
    Args:
        prompt: Mensaje del usuario.
        history: Lista de dicts con {role, content} del historial.
        model: Nombre del modelo de Ollama a usar. None = auto-detectar.
        temperature: Temperatura de generación.
        system_prompt: Prompt de sistema opcional.
        num_ctx: Tamaño de ventana de contexto. None = usar config.
    
    Returns:
        Respuesta del modelo como string.
    """
    if model is None:
        model = get_default_model()
    if num_ctx is None:
        num_ctx = OLLAMA_NUM_CTX

    url = f"{OLLAMA_BASE_URL}/api/chat"
    
    messages = []
    
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    if history:
        # Filtrar primer mensaje si es del asistente (saludo)
        filtered = history
        if filtered and filtered[0].get("role") == "assistant" and len(filtered) == 1:
            filtered = []
        elif filtered and filtered[0].get("role") == "assistant":
            filtered = filtered[1:]
        
        for msg in filtered:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })
    
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_predict": 2048,  # Aumentado a 2048 (los modelos R1 piensan mucho antes de responder)
        },
    }
    
    try:
        logger.info(f"[Ollama] Llamando modelo '{model}' (ctx={num_ctx}, temp={temperature})...")
        start_time = time.time()
        r = requests.post(url, json=payload, timeout=OLLAMA_TIMEOUT)
        r.raise_for_status()
        elapsed = time.time() - start_time
        data = r.json()
        response = data.get("message", {}).get("content", "Sin respuesta del modelo.")
        
        # Limpiar bloque <think> de DeepSeek R1
        if "<think>" in response:
            logger.info(f"[Ollama] Detectado bloque <think>. Longitud original: {len(response)}")
            if "</think>" in response:
                response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
            else:
                # Si el modelo no cerró el bloque think (ej. se cortó por num_predict)
                # Borramos desde <think> hasta el final
                logger.warning("[Ollama] El modelo no cerró el bloque <think>. Truncando el resto.")
                response = re.sub(r'<think>.*', '', response, flags=re.DOTALL).strip()
            
        logger.info(f"[Ollama] Respuesta recibida en {elapsed:.2f}s ({len(response)} chars útiles)")
        return response
    except requests.exceptions.ConnectionError:
        return "Error: Ollama no está corriendo. Inicia el servicio con 'ollama serve'."
    except requests.exceptions.Timeout:
        return f"Error: Ollama tardó demasiado en responder (timeout {OLLAMA_TIMEOUT}s). Intenta con un modelo más pequeño."
    except Exception as e:
        logger.error(f"[Ollama API Error] {e}")
        return f"Error al contactar a Ollama: {str(e)}"
