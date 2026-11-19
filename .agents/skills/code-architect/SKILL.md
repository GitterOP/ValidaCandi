---
name: code-architect
description: Diseña la arquitectura del sistema RAG, flujos de datos y redacta especificaciones técnicas detalladas (Spec-Driven Development). Úsalo para planificar la infraestructura, definir esquemas de datos o revisar la lógica del pipeline antes de escribir código.
---

# Habilidad: Arquitecto de Software Principal

Esta habilidad guía la planificación técnica y el diseño de la arquitectura del proyecto de validación RAG, garantizando que el desarrollo esté basado en especificaciones formales (Spec-Driven Development).

## Cuándo usar esta habilidad
- Cuando se requiera definir el pipeline de datos desde la ingesta (DocLing) hasta la evaluación.
- Cuando sea necesario diseñar estructuras JSON o esquemas de bases de datos para almacenar los datasets `Plan2Speech` y `Speech2Plan`.
- Cuando se deba decidir la arquitectura de recuperación (ej. Búsqueda Híbrida con RRF vs. Búsqueda Densa simple).

## Cómo utilizar esta habilidad

### 1. Definición de Flujos de Trabajo
- Todo diseño debe separar estrictamente las responsabilidades (Separation of Concerns). El motor de búsqueda no debe evaluar coherencia lógica; eso se delega a la fase NLI (Natural Language Inference).
- Define explícitamente los inputs y outputs de cada módulo.

### 2. Trazabilidad de Datos (Regla de UUIDs)
- Estipula que todo documento procesado debe mantener un UUID inmutable. El cruce de datos entre el vector de la consulta sintética y el fragmento del plan de gobierno se debe diseñar basándose exclusivamente en este UUID.

### 3. Redacción de Especificaciones
Genera documentos técnicos estructurados que el `software-engineer` pueda implementar como "cajas negras".
- **Precondiciones:** Estado inicial requerido.
- **Transformación:** Lógica matemática o algorítmica a aplicar.
- **Postcondiciones:** Salida esperada y manejo de excepciones (ej. qué hacer si la búsqueda vectorial devuelve un conjunto vacío).
