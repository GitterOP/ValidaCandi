# Etapa 1: Speech-to-Text + Diarización. Guía Consolidada (Fase 1 Cerrada)

Este documento consolida las **decisiones cerradas** de la Fase 1 del SDD para el **piloto de la Etapa 1** y sirve de índice hacia los artefactos formales de la Fase 2 ubicados en `sdd/`:

- [spec.md](sdd/spec.md): requerimientos funcionales, guía de anotación congelada (v1.0), métricas y casos límite.
- [plan.md](sdd/plan.md): arquitectura técnica, diseño de la app Streamlit (tarjetas por turno) y despliegue en Streamlit Community Cloud.
- [research.md](sdd/research.md): evidencia empírica del corpus real y fundamentos algorítmicos (WER/CER, WDER, cpWER, interpolación de números, entidades automáticas).
- [data-model.md](sdd/data-model.md): esquemas JSON y CSV (`manifest_piloto.json`, `anot_*.json`, `resultados_piloto.csv`, `resumen_piloto.json`).
- `sdd/contracts/`: contratos CLI (`cli_muestrear.md`, `cli_metricas.md`, `cli_reporte.md`).

> **Estado:** Todas las decisiones abiertas quedaron resueltas el 2026-11-19. Fase 2 lista para revisión antes de pasar a Fase 3 (`tasks.md`).

---

## 1. Contexto y objetivo

El pipeline principal (`/home/jd/Escritorio/CodeCursos`) transcribe y diariza 80 entrevistas de YouTube con WhisperX (Fuente 2, Paso 2 -> `Resultados/Diario/*.json`). Los pasos posteriores (`general.py`, `fragmentador_oraciones.py`, `procesador_atomico.py`, embeddings, comparación y auditoría NLI) operan **exclusivamente sobre texto agrupado por hablante** y **no utilizan timestamps sub-segundo**.

**Objetivo del piloto de la Etapa 1:** estimar, con intervalos de confianza, la calidad de:
1. **La transcripción ASR:** fidelidad del texto (palabras, cifras, siglas y nombres propios) frente al audio.
2. **La diarización a nivel textual/de palabras:** proporción de palabras atribuidas al hablante correcto (sin evaluar identidad real) y grado de sobresegmentación o subsegmentación por clip.
3. **El puente Paso 2 -> Paso 3:** impacto de que `general.py` agrupe por `segment["speaker"]` en lugar de `words[].speaker` (dado que ~10,9 % de los segmentos presentan hablantes mixtos a nivel palabra) y pérdida potencial por el filtro `< 10` palabras de `fragmentador_oraciones.py`.

**Fuera de alcance:**
- Identidad real del hablante (`Speaker_Name` / `Es_Candidato` -> pertenece a la **Etapa 2**).
- Métricas temporales sub-segundo (**DER temporal** con collar de 0,25 s y error de ubicación `|t_det - t_real|`), descartadas por no afectar el pipeline de `CodeCursos` y por triplicar el esfuerzo humano y técnico.

---

## 2. Sistema bajo evaluación y hallazgos empíricos del corpus

| Elemento | Valor verificado (2026-11-19) |
|:---------|:------------------------------|
| Repositorio fuente (solo lectura) | `/home/jd/Escritorio/CodeCursos` |
| Audios y diarizaciones | 80 WAVs (`Resultados/Audios/*.wav`) y 80 JSONs (`Resultados/Diario/*.json`), correspondencia 1 a 1; 10 entrevistas por cada uno de los 8 candidatos (~62,4 h) |
| Duración por entrevista | Mínima 9,9 min (`592,6 s`), mediana 44 min, máxima 96,6 min (`5794,9 s`) |
| Volumen textual en `Diario/` | 47.542 segmentos (`75` sin `speaker`, `0` sin `avg_logprob`); 559.781 palabras |
| Palabras sin timestamp (`no_ts`) | 4.469 palabras (`0,80 %`), correspondientes principalmente a **números, años y porcentajes** (`10`, `55%`, `2021`). **No deben excluirse: se interpolan linealmente** |
| Palabras sin `speaker` | 4.999 palabras (`0,89 %`); heredan etiqueta determinísticamente |
| Densidad de cambios de turno | Mediana 2,25 cambios/min; 79,6 % de las ventanas de 60 s tienen ≥ 1 cambio |

---

## 3. Registro de decisiones cerradas

| # | Decisión | Justificación |
|:-:|:---------|:--------------|
| D1 | Validación secuencial por etapas; Etapa 1 evalúa ASR + diarización textual sin identidad | Aísla fuentes de error; la identidad se valida en Etapa 2 |
| D2 | Repositorio de validación separado (`ValidaCandi`), solo lectura sobre `CodeCursos` | Mantiene el pipeline fuente limpio y auditable por SHA-256 |
| D3 | Referencia *gold* humana sobre clips muestreados (sin usar subtítulos de YouTube) | Mide exactitud real contra audio, no acuerdo entre dos ASR |
| D4 | Anotación orientada a turnos `(Hablante, Texto)` sin forma de onda ni timestamps | Valida exactamente lo que consume `CodeCursos` y reduce ~3x el costo de anotación y desarrollo |
| D5 | Interfaz Streamlit basada en **tarjetas por turno** (desplegable `H1`/`H2`..., edición de texto, botones `Dividir`/`Unir`) | Evita errores de sintaxis y minimiza carga cognitiva |
| D6 | Despliegue en **Streamlit Community Cloud** con carga de `clips_piloto.zip` (~12 MB) vía subida manual o `st.secrets`, sin versionar audios en Git | Cumple la prohibición de versionar audio con derechos de autor y funciona sobre disco efímero |
| D7 | Persistencia mediante exportar/importar JSON de progreso + respaldo automático en navegador | Sin base de datos externa; trazable por `sha256_manifest` |
| D8 | Muestreo del piloto: **24 clips de 60 s** (3 entrevistas distintas por candidato): **2 Estrato B (aleatorio) + 1 Estrato A (anclado a cambio)**; estrato oculto al anotador | Estrato B aporta estimaciones insesgadas de WER/WDER y $s$ para dimensionar; Estrato A garantiza cobertura de transiciones por candidato |
| D9 | **1 anotador** en el piloto (sin clips duplicados) | Agiliza la calibración inicial de la guía y la estimación de $s$ |
| D10 | Dimensionamiento de muestra final con margen objetivo **$E = \pm 3\text{ pp}$ de WER** usando $s_{\text{UCL}}$ al 80 % de los 16 clips B | Equilibrio práctico entre precisión estadística y horas humanas |
| D11 | Métricas primarias: **WER**, **WDER**, **cpWER** (y `cpWER - WER`), y **$\Delta H$** (error en número de hablantes); secundarias automáticas: **CER**, entidades/cifras, `segment` vs. `word`, fragmentación `< 10` palabras y Spearman | Cobertura completa del impacto real sobre el flujo sin tareas extra para el anotador |
| D12 | No mostrar ayudas visuales basadas en `score` de WhisperX en la app | Evita sesgo de anclaje del anotador |

---

## 4. Criterios de cierre del piloto

1. 24 de 24 clips del `manifest_piloto.json` anotados (o marcados `no_anotable` con motivo) y exportados en `gold/`.
2. Validación de hashes SHA-256 sin desviaciones frente a `CodeCursos/Resultados/`.
3. Generación automática de `metricas/resultados_piloto.csv`, `metricas/resumen_piloto.json` y `reporte/informe_piloto.md` con:
   - Estimaciones puntuales e IC 95 % por bootstrap ($B = 10{.}000$, semilla fija).
   - Desviación estándar del WER en Estrato B ($s$ y $s_{\text{UCL}, 80\%}$) y **tamaño muestral final $n_B$ recalculado para $E = \pm 3\text{ pp}$**.
   - Diagnóstico de `segment["speaker"]` vs. `words[].speaker` y tiempo medio de anotación por clip.
   - Registro de incidencias de la guía/app y decisión documentada sobre sumar o excluir los 24 clips en la muestra final.
