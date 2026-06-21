import os
import json
import requests
import logging
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def extract_hpn_matrix(texto: str) -> list:
    """Utiliza Groq Llama-3 para extraer la Matriz HPN del texto del expediente."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Truncamos el texto a aprox 30,000 caracteres para asegurar velocidad y no exceder límites de contexto en este prototipo.
    truncated_text = texto[:30000]
    
    prompt = f"""
Actúa como un experto analista jurídico. Lee el siguiente extracto del expediente y genera una Matriz HPN (Hechos, Pruebas y Normas).
Debes extraer los puntos más críticos y relevantes.

FORMATO DE SALIDA ESTRICTO:
Debes responder ÚNICAMENTE con un objeto JSON válido con la clave "matriz", que contenga un array de objetos. No uses markdown de bloques de código (```json), responde directamente con el texto en formato JSON crudo, empezando con {{ y terminando con }}.

Estructura requerida:
{{
  "matriz": [
    {{"tipo": "HECHO", "descripcion": "Descripción del hecho fáctico", "relevancia": "Alta"}},
    {{"tipo": "PRUEBA", "descripcion": "Documento o evidencia mencionada", "relevancia": "Media"}},
    {{"tipo": "NORMA", "descripcion": "Artículo o ley invocada", "relevancia": "Alta"}}
  ]
}}

Extracto del Expediente:
{truncated_text}
"""
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        
        # Limpiar posibles bloques markdown si el modelo los añade a pesar de la instrucción
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        result = json.loads(content)
        return result.get("matriz", [])
        
    except Exception as e:
        logger.error(f"[HPN Agent Error] {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response: {e.response.text}")
        raise ValueError(f"Error extrayendo matriz: {str(e)}")
