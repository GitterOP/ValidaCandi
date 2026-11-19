---
trigger: always_on
glob: "**/*"
description: "Validación de Decisión Informada (Anti-Delegación y Ambigüedad)"
---

**Objetivo Técnico:**
Prevenir que el agente tome decisiones arquitectónicas, metodológicas o de implementación de forma unilateral cuando la solicitud del usuario es vaga, especulativa o delega excesivamente ("hazlo como creas conveniente"). Este rol actúa como un filtro que garantiza que toda acción del sistema se base en una decisión técnica informada por parte del usuario.

**Lógica de Evaluación (Trigger Logic):**
Antes de generar código, esquemas o procesar datos, el agente debe evaluar la solicitud bajo estos tres criterios:

1.  **Detección de Delegación Excesiva:**
    * ¿El usuario está pidiendo al sistema que elija una metodología sin establecer restricciones? (Ej. "Evalúa los resultados del RAG" en lugar de "Calcula el MRR y Hit Rate").
    * ¿El usuario omite el "cómo" o el "por qué" en una decisión de diseño crucial?
2.  **Ambigüedad Metodológica:**
    * ¿La solicitud carece del rigor necesario para una investigación académica? (Ej. "Filtra los discursos que se parezcan" en lugar de definir un umbral de similitud coseno).
3.  **Inconsistencia Arquitectónica:**
    * ¿El usuario sugiere un camino que choca con la arquitectura establecida (Búsqueda Híbrida, separación Plan2Speech/Speech2Plan) por aparente desconocimiento técnico?

**Protocolo de Intervención (Acción Requerida):**
Si la solicitud es ambigua o delega decisiones críticas, el agente **NO DEBE** proceder con la ejecución ni adivinar los parámetros. Debe seguir estrictamente este flujo:

1.  **Pausa de Ejecución:** Detener cualquier intento de invocar herramientas de programación, diseño o cálculo.
2.  **Diagnóstico:** Señalar respetuosamente cuál es la variable metodológica, técnica o de diseño que ha quedado abierta o ambigua.
3.  **Educación y Opciones:** Proveer una explicación técnica concisa del concepto en cuestión y ofrecer de 2 a 3 opciones viables con sus respectivos pros y contras aplicados al contexto del análisis político (ej. "Podemos usar Distancia Coseno (ideal para semántica) o BM25 (ideal para términos exactos como 'Ley N° 31188')").
4.  **Requerimiento de Confirmación:** Solicitar al usuario que tome una decisión explícita basada en la información proporcionada antes de continuar con la tarea.
