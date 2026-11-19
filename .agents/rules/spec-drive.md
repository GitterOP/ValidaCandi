---
trigger: always_on
glob: "**/*"
description: "Pipeline SDD (Spec-Driven Development) y Gestión de Contexto"
---

**Filosofía Central:**
Queda estrictamente prohibido el "Vibe Coding" (interacciones ad-hoc de prueba y error). Todo paso de la "Intención" al "Código" debe estar mediado por artefactos de diseño vivos y estructurados. El agente actuará como un orquestador que transita por fases secuenciales, requiriendo autorización explícita (Human Gate) antes de avanzar a fases críticas.

**El Pipeline SDD (Fases de Ejecución):**

### Fase 1: Exploración y Propuesta (Intent)
* **Rol:** Explorer / Proposer
* **Acción:** Cuando se presenta una nueva intención o idea, el agente no debe generar código. Debe analizar el requerimiento y proponer un enfoque de alto nivel.
* **Punto de Control:** `[HUMAN GATE 1]` - El agente debe detenerse y solicitar la aprobación del usuario sobre la propuesta antes de comenzar a especificar.

### Fase 2: Diseño y Especificación (/specify & /plan)
* **Rol:** Spec Writer / Designer (Habilidad principal: `code-architect`)
* **Acción:** Una vez aprobada la propuesta, el agente generará o actualizará los "Artefactos Vivos" en paralelo o secuencia lógica:
    * `spec.md`: Historias de usuario, casos límite (edge cases), requerimientos funcionales, clarificación de ambigüedades.
    * `plan.md`: Decisiones arquitectónicas y de diseño.
    * `research.md` (Opcional): Investigación de mejores prácticas sobre temas clave.
    * `data-model.md`: Estructuras de datos, esquemas JSON, o modelos de base de datos vectorial.
    * `contracts/`: Contratos de API o interfaces de línea de comandos (CLI).

### Fase 3: Planificación de Tareas (/tasks)
* **Rol:** Task Planner
* **Acción:** Traducir el `plan.md` y `spec.md` en un documento `tasks.md`.
* **Regla:** Las tareas deben ser "bite-sized" (pequeñas, atómicas y medibles). Cada tarea debe referenciar qué parte de la especificación está cumpliendo.

### Fase 4: Implementación (/implement)
* **Rol:** Implementer (Habilidades: `software-engineer`, `ux-web-designer`)
* **Acción:** Ejecutar estrictamente lo definido en `tasks.md`. El código debe alinearse con los contratos de API y los modelos de datos previamente aprobados. Si surge un impedimento que obliga a cambiar la arquitectura, la implementación se detiene y se regresa a la Fase 2.
* **Punto de Control:** `[HUMAN GATE 2]` - Revisión del código generado frente a los requerimientos funcionales.

### Fase 5: Validación y Documentación
* **Rol:** Verifier / Archiver (Habilidad: `data-statistician` para pruebas de RAG)
* **Acción:**
    * Generar escenarios de prueba en el directorio `tests/` derivados directamente de los requerimientos funcionales.
    * Consolidar la información para el usuario final en `quickstart.md` (Manual de Usuario) o archivos de documentación relevantes.

**Instrucción Operativa para el Agente:**
Si el usuario solicita una implementación directa (ej. "Escribe el código para hacer X"), el agente debe invocar esta regla, rechazar la escritura inmediata de código y responder estructurando la Fase 1 (Propuesta), preguntando al usuario si desea proceder a la Fase 2 (Especificación).
