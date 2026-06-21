# Diagnóstico de Recursos e Integración

## 1. Análisis de Memoria RAM
Se ejecutó el comando `free -h` para verificar la memoria disponible en el sistema. Los resultados son:
- **Total RAM:** 14Gi
- **Usado:** 10Gi
- **Disponible:** 4.6Gi
- **Swap usado:** 7.1Gi

**Conclusión:** 
La máquina tiene muy poca memoria RAM libre y ya está recurriendo agresivamente al Swap (memoria virtual en disco, lo cual es extremadamente lento). 
Cargar un modelo de 7B-8B parámetros (como `qwen2.5:7b` o `hermes3:8b`) requiere aproximadamente de 4.5 a 5 GB de RAM. Al no tener ese espacio libre en memoria física, el sistema operativo realiza una "paginación excesiva" (thrashing) hacia el disco duro. Esto es lo que causa que los ventiladores se disparen (la CPU gasta ciclos tratando de mover páginas de memoria de disco a RAM) y el proceso tarde una eternidad sin mostrar error aparente.

Por ende, **la hipótesis 1 está confirmada**. Para uso fluido en esta máquina se requiere usar modelos más pequeños, como `deepseek-r1:1.5b`.

## 2. Comportamiento de deepseek-r1:1.5b
Al probar el modelo `deepseek-r1:1.5b`, se detectó que el modelo inserta un bloque de razonamiento (pensamiento estructurado) antes de emitir la respuesta final. Por API, este bloque viene encerrado en etiquetas `<think>...</think>`.
Esto afecta la extracción de JSON si no se limpia previamente, ya que el parser se confunde con el razonamiento, que no es JSON. Se deberá agregar lógica de limpieza antes del parseo en M4/M5.

## 3. Estado de GROQ_API_KEY (Pendiente en Tarea 3)
Aún debemos confirmar la carga de la key de Groq. Se probará en los siguientes pasos de forma aislada.
