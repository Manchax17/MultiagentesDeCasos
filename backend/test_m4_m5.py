import os
import sys

# Asegurar que importamos los modulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.hpn_agents import extract_entities, build_hpn_matrix

# Fragmento sintético de 3 frases
texto_sintetico = """
El día 15 de marzo de 2023, el señor Juan Pérez firmó un contrato de arrendamiento con la empresa Inmobiliaria Sur. 
Como evidencia, se presenta el documento original del contrato firmado por ambas partes con número de folio 402. 
Según el Artículo 1502 del Código Civil, para que una persona se obligue a otra por un acto o declaración de voluntad, es necesario que sea legalmente capaz y consienta en dicho acto.
"""

def test():
    print("--- INICIANDO TAREA 4: Extracción M4 (aislada) ---")
    entidades = extract_entities(texto_sintetico, model="ollama", ollama_model="deepseek-r1:1.5b")
    print("\nResultados M4:")
    import json
    print(json.dumps(entidades, indent=2, ensure_ascii=False))

    print("\n--- INICIANDO TAREA 5: Construcción M5 (aislada) ---")
    matriz = build_hpn_matrix(entidades, model="ollama", ollama_model="deepseek-r1:1.5b")
    print("\nResultados M5:")
    print(json.dumps(matriz, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test()
