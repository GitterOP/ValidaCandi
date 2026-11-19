---
name: local-llm-expert
description: Optimiza inferencia local, gestiona modelos vía CLI (LM Studio), aplica políticas de reintento y valida/repara salidas JSON rígidamente. Úsalo para configurar hiperparámetros explícitos, cargar modelos en memoria, diseñar prompts NLI y generar validaciones rápidas/baratas.
---

# Habilidad: Experto en LLMs Locales y Generación Sintética

Esta habilidad se centra en la orquestación y optimización de LLMs de código abierto ejecutados localmente para tareas de generación de datos deterministas y evaluación NLI, con un fuerte enfoque en resiliencia, validación y gestión de hardware.

## Cuándo usar esta habilidad
- Al interactuar con la API de LM Studio/Ollama para inferencia.
- Para cambiar o gestionar dinámicamente qué modelo está cargado en memoria.
- Para diseñar *system prompts* que obliguen al LLM a devolver estructuras de datos.
- Para establecer robustez en el código mediante políticas de reintento y validaciones de formato/lógica.

## Cómo utilizar esta habilidad

### 1. Gestión de Carga/Descarga de Modelos (CLI LM Studio)
Nunca asumas que el modelo está cargado. Siempre gestiona activamente la VRAM usando la interfaz de línea de comandos de LM Studio (`lms`).
Usa el siguiente patrón en Python:

```python
import subprocess
import time

def manage_model_loading(target_model: str, context_length: int = 16000):
    """ Gestiona la carga del modelo usando la CLI 'lms' de LM Studio. """
    print(f"🔧 Configurando modelo: {target_model} (ctx={context_length})...")
    try:
        print("   Descargando modelos previos...")
        subprocess.run(["lms", "unload", "--all"], check=False, capture_output=True)
        if target_model == "unload":
            print("   ✅ VRAM liberada totalmente.")
            return True
        print(f"   Cargando {target_model}...")
        cmd = ["lms", "load", target_model, "--context-length", str(context_length), "--gpu", "max"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✅ Modelo cargado: {target_model}")
            time.sleep(2)
        else:
            print(f"   ⚠️ Error cargando modelo via CLI: {result.stderr}")
    except Exception as e:
        print(f"   ⚠️ Error en gestión de modelos: {e}")
```

### 2. Control de Lotes (Batch Size Management)
Nunca delegues el tamaño de lote al valor por defecto de las librerías en hardware de alto rendimiento como la RTX 5090 (Blackwell).
- **Estándar:** Usa un `batch_size=32` para modelos medianos (Jina v2, BGE).
- **Conservador:** Usa un `batch_size=4` o menor para modelos pesados basados en arquitecturas CausalLM (Qwen3, Nemotron, Jina v3).
- **Protocolo Staged:** Descarga los modelos de LM Studio inmediatamente despues de terminar de usarlos. Para ello usa el siguiente comando: `lms unload --all` y espera a que la VRAM se libere.

### 3. Reporte Explícito de Parámetros
Nunca dejes parámetros de inferencia ocultos por default. Siempre debes declarar y hacer visible (imprimiendo en consola) los siguientes hiperparámetros fundamentales:
- **Temperatura ($T$):** Controla la aleatoriedad. $T = 0.0$ es crítico para reproductibilidad.
- **Top-p (Nucleus Sampling):** Umbral de probabilidad acumulada $p$.
- **Top-k:** Número absoluto de tokens de mayor probabilidad.
- **Penalización de repetición:** Usa `frequency_penalty` o `presence_penalty` (evita `repetition_penalty` en APIs OpenAI).
- **Límite de tokens (Max New Tokens):** Usa `max_tokens`.

### 4. Política de Reintentos (Retry Policy)
**Regla Estricta:** Siempre que llames a un LLM, envuelve la llamada en un bloque de reintento (retry loop) dándole **hasta 5 oportunidades (chances)** antes de reportarlo como un error fatal.

### 5. Validación de Formato y Reparación (JSON)
Dado que los LLMs a veces ignoran el modo JSON o cometen errores de sintaxis:
- Siempre parsea la salida y valida campos clave, tipos de datos y formatos correctos.
- **Manejo de Razonamiento:** Para modelos tipo DeepSeek R1, si el campo `content` viene vacío, verifica `reasoning_content`.
- Si hay errores sencillos (comillas, comas), intenta repararlos con Regex antes de reintentar.

### 6. Validación Profunda (Evaluación de Salidas)
- **Prioriza pruebas rápidas y baratas a pequeña escala.**
- Usa clasificadores rápidos paralelos o modelos económicos (1B-3B) para un *Cross-Check*.
