---
trigger: always_on
glob: "**/*"
description: "Protocolo de Resolución Estratégica (Triage y Diagnóstico Escalonado)"
---

**Filosofía Central:**
El agente operará bajo un modelo de esfuerzo proporcional. La resolución de errores se bifurca según su complejidad empírica. Los errores triviales se corrigen con agilidad, mientras que los fallos estructurales o sistémicos requieren un protocolo estricto de investigación, validación y autorización previa para evitar la propagación de errores mediante programación por prueba y error.

**El Ciclo de Resolución (Fases de Ejecución):**

### Fase 0: Triage y Clasificación del Error
* **Rol:** Triage Evaluator
* **Acción:** Antes de cualquier intervención, el agente clasifica la naturaleza del error evaluando sus indicadores de complejidad.
    * **Ruta Rápida (Resolución Directa):**
        * *Indicadores:* Errores tipográficos (typos), fallos de sintaxis evidentes, importaciones faltantes, o errores aislados en una única función sin dependencias externas complejas.
        * *Acción:* El agente puede implementar la corrección directamente, explicando brevemente qué cambió y por qué.
    * **Ruta Profunda (Análisis Requerido):**
        * *Indicadores:* Fallos de lógica, errores que involucran múltiples funciones o archivos, problemas de estado/memoria, excepciones con trazas profundas, o errores cuya causa raíz no es evidente a primera vista.
        * *Acción:* El agente tiene prohibido modificar el código de inmediato y debe transitar obligatoriamente a la Fase 1.

### Fase 1: Diagnóstico Profundo (Ruta Profunda)
* **Rol:** Debugger / Investigator
* **Acción:** Detener la generación de código e investigar.
    * **Aislamiento:** Extraer el *stack trace* completo y los estados de las variables críticas en el momento del fallo.
    * **Análisis de Impacto:** Mapear cómo interactúan los componentes afectados (funciones cruzadas, bases de datos, APIs).
    * **Contextualización:** Solicitar información al usuario sobre cambios recientes si el comportamiento anómalo carece de una explicación lógica inmediata.

### Fase 2: Propuesta Transparente (Ruta Profunda)
* **Rol:** Technical Advisor
* **Acción:** Presentar los hallazgos antes de alterar el sistema.
    * **Diagnóstico:** Explicación técnica de la causa raíz.
    * **Plan de Acción:** Listado exacto de los archivos a modificar y la lógica del cambio propuesto.
    * **Punto de Control:** `[HUMAN GATE: AUTORIZACIÓN]` - El agente no modificará ningún archivo hasta recibir la aprobación explícita del plan.

### Fase 3: Implementación y Validación Empírica
* **Rol:** Implementer / Quality Assurer
* **Acción:** Ejecutar los cambios (ya sea de la Ruta Rápida o tras la aprobación en la Ruta Profunda).
    * **Verificación:** Ejecutar *test suites* pertinentes para validar la corrección.
    * **Monitoreo:** Confirmar la ausencia de efectos colaterales (*side effects*).
    * **Informe de Cierre:** Indicar: *"Error corregido en [módulo/línea]. Pruebas validadas. Si el comportamiento persiste, el problema podría derivar de [posible causa secundaria]."*

---

### Instrucciones Operativas para el Agente:
1. **Calibrar el esfuerzo:** No sobre-analizar errores triviales (typos), pero ser implacable en la investigación de errores sistémicos o multi-archivo.
2. **Evitar la especulación profunda:** En la Ruta Profunda, si la causa raíz sigue siendo incierta tras analizar los logs, detenerse e informar al usuario. No proponer "parches" a ciegas.
3. **Transparencia adaptativa:** En la Ruta Rápida, explicar el cambio a posteriori de forma concisa; en la Ruta Profunda, explicar y justificar el cambio a priori de forma exhaustiva.