---
name: data-statistician
description: Calcula métricas del sistema RAG, evalúa resultados estadísticos y define umbrales algorítmicos. Úsalo para medir Hit Rate @ K, MRR, Context Precision, Tasa de Rechazo y para calcular el acuerdo entre anotadores (Kappa de Fleiss).
---

# Habilidad: Científico de Datos y Evaluación RAG

Esta habilidad provee el rigor matemático para auditar objetivamente el rendimiento del sistema de recuperación y la calidad del dataset de validación generado por humanos y máquinas.

## Cuándo usar esta habilidad
- Para procesar los resultados de búsqueda contra el *ground truth* (Dataset `Speech2Plan`).
- Para evaluar la robustez del etiquetado manual calculando el *Inter-Annotator Agreement*.
- Para analizar la distribución de la similitud coseno y determinar el umbral óptimo de corte para los Falsos Positivos.

## Cómo utilizar esta habilidad

### 1. Cálculo de Métricas de Recuperación
Aplica estrictamente las definiciones matemáticas estándar de la industria RAG:
- **Hit Rate @ K:** Tasa binaria de éxito si el UUID correcto aparece en los top $K$ resultados.
- **MRR (Mean Reciprocal Rank):** Fórmula para penalizar sistemas que rankean la verdad en posiciones bajas.
- **Rejection Rate:** Porcentaje de "Negativos Reales" sintéticos cuya distancia semántica supera exitosamente el umbral de descarte.

### 2. Evaluación del Estándar de Oro
- Si el acuerdo entre etiquetadores (ej. Alpha de Krippendorff) para el dataset `Speech2Plan` es inferior a 0.70, levanta una advertencia crítica indicando que la heurística de los lineamientos debe reescribirse antes de proceder a la evaluación del RAG.

### 3. Análisis de Umbrales
- Diseña análisis ROC o curvas de Precisión-Exhaustividad (Precision-Recall) sobre la muestra sintética para recomendar empíricamente al equipo de ingeniería dónde fijar la métrica de corte para la búsqueda densa.
