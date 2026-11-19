---
name: ux-web-designer
description: Diseña herramientas internas de anotación en Python (Streamlit/Gradio). Úsalo para construir la interfaz del dataset Speech2Plan que permite a los evaluadores humanos mapear discursos contra planes de gobierno minimizando el esfuerzo cognitivo.
---

# Habilidad: Ingeniero de UI y UX para Herramientas Internas

Esta habilidad garantiza el desarrollo de interfaces fluidas, de baja latencia y alta usabilidad para que los expertos humanos construyan el *ground truth* (Speech2Plan) sin errores de formato.

## Cuándo usar esta habilidad
- Para programar aplicaciones de anotación interactivas utilizando `Streamlit`, `Gradio` o `Reflex`.
- Para diseñar visualizaciones jerárquicas del plan de gobierno procesado por DocLing.
- Para implementar mecanismos de recolección de datos robustos y a prueba de errores de tipografía (ej. botones de selección rápida de UUIDs).

## Cómo utilizar esta habilidad

### 1. Diseño Orientado a la Carga Cognitiva Mínima
- Evita el uso de PDFs puros. Transforma los datos JSON jerárquicos en elementos UI desplegables (accordions) o tablas interactivas.
- Implementa una barra lateral (Sidebar) estática para el texto del discurso y el panel principal para la exploración y búsqueda del plan de gobierno.

### 2. Gestión del Estado (State Management)
- Asegura que la aplicación retenga el progreso utilizando `st.session_state` (en Streamlit) para evitar la pérdida de anotaciones si la página se recarga accidentalmente.

### 3. Funcionalidad de Búsqueda Integrada
- Implementa filtros interactivos (barra de búsqueda de palabras clave) sobre la vista de la tabla del plan de gobierno para imitar la operación léxica y facilitar al humano la búsqueda rápida de la propuesta.
- Las exportaciones de la interfaz deben ser estrictamente en formato `JSONL` o `CSV` validado, listo para ser consumido por el `data-statistician`.
