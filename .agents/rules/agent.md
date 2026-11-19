---
trigger: always_on
glob: "*"
description: Instrucciones generales del proyecto ValidaCandi - Validación empírica por etapas del pipeline de análisis político (CodeCursos).
---

Este proyecto (**ValidaCandi**) tiene como objetivo **validar empíricamente, etapa por etapa**, el flujo completo del pipeline de análisis político implementado en `/home/jd/Escritorio/CodeCursos` (contrastación entre planes de gobierno en PDF y entrevistas en YouTube de 8 candidatos presidenciales peruanos).

El repositorio principal (`/home/jd/Escritorio/CodeCursos`) mantiene únicamente la arquitectura final del pipeline. Este repositorio concentra todo lo relativo a su validación: diseño muestral, `manifests`, herramientas de anotación humana, referencias *gold*, cálculo de métricas e informes estadísticos.

La validación se aborda **poco a poco y de manera secuencial**: cada etapa evalúa un componente acotado del pipeline para aislar fuentes de error antes de pasar a la siguiente.

### Principios de Validación

1. **Solo lectura sobre `/home/jd/Escritorio/CodeCursos`:** Ningún script ni proceso de `ValidaCandi` puede modificar, sobrescribir o eliminar archivos en `/home/jd/Escritorio/CodeCursos`. La ruta al repositorio fuente se configura de forma explícita por etapa.
2. **Avance incremental por etapas:** Se trabaja una etapa a la vez en su propia carpeta autocontenida (`ETAPA_N_<nombre>/`). Cuando una etapa requiere anotación humana, se ejecuta primero un **piloto** para calibrar la guía, la herramienta y el tamaño muestral final.
3. **Trazabilidad:** Cada muestreo y corrida registra el hash **SHA-256** de todos los insumos leídos en `/home/jd/Escritorio/CodeCursos/Resultados/` (audios, JSONs, CSVs). Si un insumo cambia en el repositorio fuente, las anotaciones asociadas quedan marcadas como obsoletas.
4. **Reproducibilidad Académica:** Todo muestreo y proceso estocástico (p. ej., bootstrap para intervalos de confianza) debe usar **semilla fija** y materializarse en un `manifest` con todos los parámetros documentados.
5. **Spec-Driven Development (SDD):** Cada etapa sigue estrictamente las fases de `.agents/rules/spec-drive.md` (Propuesta -> Especificación y Plan -> Tareas -> Implementación -> Validación) y el protocolo de aclaración de `.agents/rules/understanding-validation.md`.
6. **Sin versionado de audio:** No se versionan archivos de audio ni clips derivados (`*.wav`, `*.mp3`, `**/clips/`); siempre se regeneran de forma determinista a partir del `manifest`.
7. **Comunicación y rigor:** Comentarios, artefactos y reportes deben estar en español, con tono neutral y académico, respaldando hallazgos con intervalos de confianza o consistencia estadística.
8. **Compatibilidad de terminal:** Queda estrictamente prohibido el uso de emojis o caracteres Unicode especiales en las salidas de terminal (`print`) de los scripts. Se debe utilizar texto plano (ASCII/UTF-8 sin símbolos) para evitar errores `UnicodeEncodeError`.

### Hoja de Ruta por Etapas (Enfoque Gradual)

Las etapas se irán definiendo e incorporando progresivamente conforme se cierren las anteriores:

| Etapa | Carpeta en `ValidaCandi` | Paso evaluado en `CodeCursos` | Qué se valida | Estado |
|:-----:|:-------------------------|:------------------------------|:--------------|:-------|
| **1** | `ETAPA_1_speech2textDi/` | Fuente 2, Paso 2 (`whisperx/` -> `Resultados/Diario/*.json`) | Transcripción ASR (texto vs. audio) y fronteras de diarización (sin identidad del hablante) | Fase 1 SDD cerrada (`GUIA_SDD.md`); Fase 2 (piloto) pendiente |
| **2** | *(por crear)* | Fuente 2, Paso 3 (`general.py` -> `Resultados/Consolidado/*.csv`) | Identidad del hablante (`Speaker_Name` / `Es_Candidato`) | No iniciada |
| **3+** | *(por crear progresivamente)* | Pasos restantes (fragmentación, extracción atómica, estructuración/chunking de planes, recuperación híbrida, auditoría NLI con LLM, etc.) | Se definirá el alcance y métricas de cada etapa al cerrar la anterior | No iniciadas |

> **Foco actual:** Avanzar con la **Etapa 1** (`ETAPA_1_speech2textDi/`), partiendo de las decisiones registradas en `ETAPA_1_speech2textDi/GUIA_SDD.md`, sin adelantar implementación ni diseño de etapas posteriores hasta completar la actual.

### Referencia del Flujo Bajo Evaluación (`/home/jd/Escritorio/CodeCursos`)

El pipeline fuente se orquesta desde `/home/jd/Escritorio/CodeCursos/main.ipynb` sobre **8 candidatos presidenciales peruanos** (`1_keiko`, `2_rla`, `3_carlosal`, `4_chau`, `5_jorgeni`, `6_robertosa`, `7_cesara`, `8_cerron`), con 8 planes de gobierno en PDF y 80 entrevistas de YouTube (~62,4 h de audio).

#### Fuente 1: Planes de Gobierno
| Paso | Descripción | Módulo en `CodeCursos/common/` | Insumo -> Salida en `CodeCursos/` |
|:----:|:------------|:-------------------------------|:------------------------------------|
| 1a | Extracción de estructura jerárquica del PDF (Docling) | `estructurador.py` | `Planes/*.pdf` -> `Resultados/Estructura/*.json` |
| 1b | Chunking semántico de propuestas con LLM local | `chunker.py` | `Resultados/Estructura/*.json` -> `Resultados/Chunks/*.json` |

#### Fuente 2: Entrevistas en YouTube
| Paso | Descripción | Módulo en `CodeCursos/common/` | Insumo -> Salida en `CodeCursos/` |
|:----:|:------------|:-------------------------------|:------------------------------------|
| 1 | Descarga de audios desde Excel de enlaces | `download.py` | `Discursos/Links.xlsx` -> `Resultados/Audios/*.wav` |
| 2 | Transcripción y diarización con WhisperX (`large-v3` + `pyannote/speaker-diarization-3.1`) | `whisperx/` | `Resultados/Audios/*.wav` -> `Resultados/Diario/*.json` |
| 3 | Identificación de hablantes y normalización de candidatos | `general.py` | `Resultados/Diario/*.json` -> `Resultados/Consolidado/*.csv` |
| 4 | Fragmentación de intervenciones en oraciones | `fragmentador_oraciones.py` | `Resultados/Consolidado/*.csv` -> `Resultados/Fragmentos/*.json` |
| 5 | Extracción de propuestas atómicas con LLM local | `procesador_atomico.py` | `Resultados/Fragmentos/*.json` -> `Resultados/Atomico/*.json` |

#### Núcleo Compartido (Comparación, Auditoría y Análisis)
| Paso | Descripción | Módulo en `CodeCursos/` | Insumo -> Salida en `CodeCursos/` |
|:----:|:------------|:------------------------|:------------------------------------|
| 6 | Vectorización (embeddings Qwen 4096 dims) | `common/vectorizador.py` | `Resultados/Atomico/`, `Resultados/Chunks/` |
| 7 | Recuperación híbrida y matching semántico (HyDE + BM25 + coseno + reranking) | `common/comparacion*.py` | `Resultados/Atomico/`, `Resultados/Chunks/` -> `Resultados/Matriz*.csv` |
| 8 | Auditoría y validación lógica NLI con LLM local (`openai/gpt-oss-20b`) | `common/validador*.py` | `Resultados/Matriz*.csv` -> `Resultados/Matriz_Final*.csv` |
| 9 | Generación de reportes gráficos | `common/graficos.py`, `graficos/` | Matrices y JSONs -> figuras / reportes |
| 10 | Modelado ideológico y clustering (PCA + K-Means) | `common/clustering_perfiles.py` | Matrices y JSONs -> `Resultados/Perfiles_*.csv` |

#### Nomenclatura de Archivos en `CodeCursos/Resultados/`
| Tipo | Patrón | Ejemplo |
|:-----|:-------|:--------|
| Audios / Diarización | `{ID}_{CID}_{candidato}.{wav,json}` | `10_1_keiko.json` |
| Chunks de planes | `{CID}_{candidato}.json` | `1_keiko.json` |
| Entrevistas atómicas | `{ID}_{CID}_{candidato}_atomico.json` | `1_1_keiko_atomico.json` |

### Matriz de Habilidades (Skills)

| Habilidad (Skill) | Rol en `ValidaCandi` | Cuándo Usar (Trigger Condition) |
|:------------------|:---------------------|:--------------------------------|
| **`code-architect`** | Diseña la arquitectura de validación de cada etapa y redacta artefactos SDD (`spec.md`, `plan.md`, `data-model.md`). | Al abrir Fase 2 del SDD de una etapa o definir esquemas de `manifest`, anotaciones y contratos CLI. |
| **`data-statistician`** | Define diseños muestrales, dimensionamiento de piloto/muestra, métricas e inferencia estadística (IC por bootstrap, acuerdo entre anotadores). | Al diseñar muestreos, calcular métricas (WER, CER, DER, Precision/Recall/F1, Kappa, Hit Rate, MRR) o redactar informes de validación. |
| **`ux-web-designer`** | Diseña y construye herramientas internas de anotación humana en Streamlit minimizando esfuerzo cognitivo y sesgos. | Al desarrollar o mejorar las apps de anotación por etapa (`app/`). |
| **`software-engineer`** | Implementa scripts reproducibles de muestreo, recorte de insumos, verificación SHA-256, cálculo de métricas y pruebas. | En Fase 4 del SDD para implementar y probar el código de cada etapa. |
| **`local-llm-expert`** | Apoya la evaluación de componentes basados en LLM local o jueces automáticos. | En etapas posteriores que validen chunking, extracción atómica o validación NLI con LLM local. |

### Estructura del Repositorio (`ValidaCandi`)

```text
/home/jd/Escritorio/ValidaCandi/
├── .agents/                        # Reglas (SDD, validación, errores) y skills del agente
├── ETAPA_1_speech2textDi/          # Etapa 1: validación de ASR y fronteras de diarización
│   ├── GUIA_SDD.md                 # Decisiones de Fase 1 y base para artefactos SDD
│   ├── muestreo/                   # Scripts de muestreo y manifests (sin clips versionados)
│   ├── app/                        # Herramienta de anotación humana (Streamlit)
│   ├── gold/                       # Anotaciones humanas exportadas (referencia gold)
│   ├── metricas/                   # Scripts y tablas de métricas por clip y agregadas
│   └── reporte/                    # Informes de resultados (piloto y muestra final)
├── .gitignore                      # Excluye audios, clips y configuración local
└── README.md                       # Visión general y tabla de avance por etapas
```

Cada nueva etapa seguirá esta misma convención de carpeta autocontenida (`ETAPA_N_<nombre>/`) cuando se inicie formalmente.
