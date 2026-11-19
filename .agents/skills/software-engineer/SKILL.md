---
name: software-engineer
description: Escribe implementaciones de código robusto en Python. Úsalo para desarrollar el backend RAG, scripts de procesamiento de datos con Pandas/Polars, y la integración de bases de datos vectoriales (FAISS) o índices léxicos (BM25).
---

# Habilidad: Ingeniero de Software Profesional (Python)

Esta habilidad asegura que las especificaciones técnicas se traduzcan en código Python de grado de producción, eficiente en memoria y matemáticamente robusto.

## Cuándo usar esta habilidad
- Al implementar los *scripts* de vectorización y búsqueda (Similitud Coseno, Producto Punto).
- Para construir la lógica del motor de búsqueda híbrida combinando *embeddings* e índices invertidos.
- Al procesar, limpiar y estructurar los datos del plan de gobierno y los discursos utilizando bibliotecas como Pandas, Polars o NumPy.

## Cómo utilizar esta habilidad

### 1. Convenciones de Código
- Obligatorio el uso de *Type-Hints* (anotaciones de tipo) en todas las firmas de funciones (ej. `def calcular_similitud(vector_q: np.ndarray, matriz_d: np.ndarray) -> np.ndarray:`).
- Documentación estricta utilizando Docstrings (formato Google o NumPy).

### 2. Implementación Matemática
- Vectoriza las operaciones utilizando `NumPy` o el motor nativo de la base de datos vectorial. Evita bucles `for` nativos de Python para el cálculo de distancias coseno o evaluación de rankings.

### 3. Manejo de Errores y Excepciones
- Implementa bloques `try/except` robustos alrededor de llamadas a APIs locales (LM Studio) y operaciones de I/O de archivos.
- Si un UUID no hace *match* durante la evaluación del dataset, el código no debe fallar silenciosamente; debe registrar la anomalía (Logging).
