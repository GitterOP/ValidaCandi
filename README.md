# ValidaCandi

Repositorio oficial de **validación por etapas** del pipeline de análisis político
(planes de gobierno vs. entrevistas de candidatos presidenciales peruanos).

El repositorio principal (`~/Escritorio/CodeCursos`) contiene solo la arquitectura final del
pipeline. Este repositorio concentra todo lo relativo a su validación empírica: muestras,
anotaciones humanas, herramientas de etiquetado, métricas e informes.

## Principios

1. **Solo lectura sobre el repositorio principal.** Ningún script de este repositorio escribe en
   `CodeCursos/`. La ruta se configura de forma explícita por etapa.
2. **Trazabilidad.** Cada corrida registra el hash SHA-256 de todos los insumos leídos
   (audios, JSONs, CSVs). Si un insumo cambia, las anotaciones asociadas quedan marcadas como obsoletas.
3. **Reproducibilidad.** Todo muestreo usa semilla fija y queda materializado en un `manifest`.
4. **Spec-Driven Development.** Cada etapa transita por propuesta, especificación, tareas,
   implementación y validación (ver `.agents/rules/spec-drive.md`).
5. **No se versionan audios.** Los clips derivados se regeneran a partir del manifest.

## Etapas

| Etapa | Carpeta | Qué se valida | Estado |
|:-----:|:--------|:--------------|:-------|
| 1 | `ETAPA_1_speech2textDi/` | Transcripción (texto vs. audio) y fronteras de diarización | Fase 1 cerrada, Fase 2 pendiente |
| 2 | (por crear) | Identidad del hablante (el audio X corresponde a la persona X) | No iniciada |
| ... | | Fragmentación, extracción atómica, comparación, validación LLM | No iniciadas |

## Estructura

```text
ValidaCandi/
  .agents/                     # Reglas y skills del agente (copia de CodeCursos)
  ETAPA_1_speech2textDi/       # Etapa 1: ASR + diarización
    GUIA_SDD.md                # Decisiones tomadas y guía para redactar los artefactos SDD
    muestreo/  app/  gold/  metricas/  reporte/
```

> Nota: `.agents/rules/agent.md` describe el pipeline principal. Conviene agregar más adelante
> una regla específica de este repositorio de validación.

