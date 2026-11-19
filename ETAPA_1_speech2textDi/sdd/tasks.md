# Plan de Tareas Atómicas — Etapa 1 (Piloto): ASR y Diarización Textual

- **Fase SDD:** Fase 3 (`/tasks`)
- **Artefactos fuente:** [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md) y `contracts/`
- **Regla de ejecución:** Cada tarea es atómica, verificable y respeta estrictamente el modo solo lectura sobre `/home/jd/Escritorio/CodeCursos` y salida de terminal sin emojis.

---

## Bloque 0 — Entorno y configuración base

- [x] **T-01: Crear archivos de dependencias y verificar `.gitignore`**
  - **Archivos:** `ETAPA_1_speech2textDi/app/requirements.txt`, `ETAPA_1_speech2textDi/requirements-dev.txt`, `.gitignore`
  - **Referencia SDD:** `plan.md` §4 y §5
  - **Skill:** `software-engineer`
  - **Detalle:** Definir `app/requirements.txt` mínimo para Streamlit Community Cloud (`streamlit>=1.39,<2.0`), `requirements-dev.txt` para entorno local (`jiwer`, `numpy`, `pandas`, `scipy`, `pytest`, `streamlit`), y asegurar en `.gitignore` que `**/clips/` y `clips_piloto.zip` nunca se versionen.
  - **Verificación:** Ambos archivos se instalan limpiamente en un entorno Python 3.11; `git status` ignora archivos creados en `muestreo/clips/`.

---

## Bloque 1 — Núcleo compartido (`ETAPA_1_speech2textDi/core/`)

- [x] **T-02: Implementar cálculo y verificación SHA-256 (`core/hashes.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/core/__init__.py`, `ETAPA_1_speech2textDi/core/hashes.py`
  - **Referencia SDD:** `spec.md` (RF-01, RF-09), `data-model.md` §1
  - **Skill:** `software-engineer`
  - **Detalle:** Implementar `sha256_archivo(path)` (lectura en bloques de 1 MB para WAVs grandes) y `sha256_manifest_canonico(manifest_dict)` excluyendo `sha256_manifest` y `sha256_clip` (serialización JSON canónica `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`).
  - **Verificación:** Mismo archivo y mismo manifest (con o sin `sha256_clip`) producen exactamente el mismo hash de 64 caracteres hexadecimales.

- [x] **T-03: Implementar lector de `Diario/*.json` con interpolación y herencia (`core/io_diario.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/core/io_diario.py`
  - **Referencia SDD:** `spec.md` (RF-03, RF-04, §6 Casos límite), `research.md` §1.2–1.3
  - **Skill:** `software-engineer`
  - **Detalle:**
    - Cargar `segments` validando estructura.
    - Interpolar linealmente `(start, end)` para bloques contiguos de palabras sin timestamp dentro del segmento padre (nunca descartar números/porcentajes).
    - Resolver `speaker` ausente en vista `word` (anterior -> siguiente -> `segment["speaker"]` -> `"UNKNOWN"`) y en vista `segment` (`segment.get("speaker") or "UNKNOWN"`).
    - Extraer palabras cuyo punto medio `(start + end) / 2` cae en `[inicio_s, fin_s]` para ambas vistas (`segment` y `word`), construir `precarga_ui` con etiquetas genéricas `H1`, `H2`... y calcular `score_medio` y `avg_logprob_medio`.
  - **Verificación:** Probado sobre un archivo real de `CodeCursos/Resultados/Diario/` con números sin timestamp (`10`, `55%`, `2021`) y segmentos con hablantes mixtos; 0 palabras perdidas y timestamps monótonos.

- [x] **T-04: Implementar normalizador determinista de texto español (`core/normalizacion.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/core/normalizacion.py`
  - **Referencia SDD:** `spec.md` (§5 Reglas de normalización), `research.md` §2
  - **Skill:** `software-engineer`
  - **Detalle:** Implementar `normalizar_texto(texto) -> NormalizacionResultado` (retorna texto normalizado, lista de tokens y conteos `n_inaudible`, `n_solapado`, `n_musica`, `n_ruido`): remoción de marcadores especiales, unificación `%` / `por ciento` -> `porcentaje`, separadores de miles (`10.000` -> `10000`), conversión segura de cardinales en palabras -> dígitos (sin tocar el artículo `un`/`una` aislado), minúsculas sin tildes preservando `ñ`, limpieza de puntuación y remoción de la lista cerrada de muletillas no léxicas.
  - **Verificación:** Casos unitarios cubren `15%` == `15 por ciento`, `ñ` preservada, tildes removidas, `un país` intacto, `[inaudible]` contabilizado y excluido.

- [x] **T-05: Implementar validadores de esquema de manifest y anotación (`core/validacion_esquemas.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/core/validacion_esquemas.py`
  - **Referencia SDD:** `spec.md` (RF-08, RF-09, HU-08), `data-model.md` §1 y §2
  - **Skill:** `software-engineer`
  - **Detalle:** Validar estructura, tipos, enums (`estrato`, `estado`, `motivo_no_anotable`), patrón `^H[1-9]\d*$`, unicidad de `clip_id`, no-vacío de `turnos` cuando `estado == "completo"`, y coincidencia exacta de `sha256_manifest`. Incluir función `fusionar_turnos_consecutivos(turnos)`.
  - **Verificación:** Acepta ejemplos válidos de `data-model.md` y lanza excepciones descriptivas ante hash incorrecto, estado inválido o turno vacío.

---

## Bloque 2 — Muestreo y recorte de clips (`ETAPA_1_speech2textDi/muestreo/`)

- [x] **T-06: Implementar script de muestreo estratificado (`muestreo/muestrear.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/muestreo/muestrear.py`
  - **Referencia SDD:** `spec.md` (RF-01, RF-02, RF-03, RF-04), `contracts/cli_muestrear.md` §1, `data-model.md` §1
  - **Skill:** `software-engineer` + `data-statistician`
  - **Detalle:** Verificar correspondencia 1 a 1 de los 80 WAV/JSON en `CodeCursos/Resultados/`, sortear con semilla fija (`20261119`) 3 entrevistas distintas por candidato (2 Estrato B + 1 Estrato A anclado a cambio de `segment["speaker"]` con offset $U(15, 45)\text{ s}$), ajustar bordes al hueco entre palabras más cercano (máx. ±2 s), asignar `orden_anotacion` permutado aleatoriamente, calcular `sha256_wav`, `sha256_json`, `precarga_ui` y `sha256_manifest`, y escribir `manifest_piloto.json`.
  - **Verificación:** Dos corridas con la misma semilla producen `manifest_piloto.json` bit a bit idéntico (salvo `fecha_generacion`); exactamente 16 B + 8 A, 3 entrevistas distintas por candidato, códigos de salida `0/1/2` conformes al contrato y sin emojis en stdout.

- [x] **T-07: Implementar script de recorte de MP3 y empaquetado ZIP (`muestreo/recortar_clips.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/muestreo/recortar_clips.py`
  - **Referencia SDD:** `spec.md` (RF-05), `research.md` §4, `contracts/cli_muestrear.md` §2
  - **Skill:** `software-engineer`
  - **Detalle:** Verificar `sha256_wav` de cada archivo fuente contra el manifest, recortar los 24 clips con `ffmpeg` (`-ac 1 -ar 16000 -b:a 64k -map_metadata -1`), registrar `sha256_clip` en `manifest_piloto.json` (verificando que `sha256_manifest` no cambie), empaquetar `muestreo/clips/clips_piloto.zip` y soportar `--solo-verificar`.
  - **Verificación:** Genera los 24 MP3 (~11–13 MB totales en ZIP), `--solo-verificar` retorna `0`, y `git status` confirma que ningún MP3/ZIP queda rastreado.

- [x] **T-08: Ejecutar muestreo y recorte real del piloto (`manifest_piloto.json` + `clips_piloto.zip`)**
  - **Archivos:** `ETAPA_1_speech2textDi/muestreo/manifest_piloto.json` (Git), `ETAPA_1_speech2textDi/muestreo/clips/clips_piloto.zip` (local, fuera de Git)
  - **Referencia SDD:** `spec.md` (RF-01..RF-05)
  - **Skill:** `software-engineer`
  - **Detalle:** Correr `muestrear.py` y `recortar_clips.py` sobre `/home/jd/Escritorio/CodeCursos` con semilla `20261119` y revisar que los 24 clips tengan `precarga_ui` coherente y duraciones ~60 s.
  - **Verificación:** `manifest_piloto.json` válido según `validacion_esquemas.py` y 24 MP3 verificados por `--solo-verificar`.

---

## Bloque 3 — App de anotación en Streamlit (`ETAPA_1_speech2textDi/app/`)

- [x] **T-09: Implementar cargador seguro de clips (`app/cargador_clips.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/app/cargador_clips.py`
  - **Referencia SDD:** `spec.md` (RF-06, HU-01), `plan.md` §3.2
  - **Skill:** `ux-web-designer` + `software-engineer`
  - **Detalle:** Cargar `manifest_piloto.json` local del repo; soportar descarga automática desde `st.secrets["CLIPS_ZIP_URL"]` (+ token opcional `CLIPS_ZIP_TOKEN`) con `@st.cache_resource` en `/tmp/validacandi_clips/<sha256_manifest>/`, o fallback mediante `st.file_uploader` de `clips_piloto.zip`; verificar `sha256_clip` de los 24 MP3 antes de habilitar anotación.
  - **Verificación:** Con `clips_piloto.zip` válido desbloquea la app; con un MP3 alterado o faltante bloquea y reporta exactamente qué `clip_id` falló.

- [x] **T-10: Implementar gestión de estado, cronómetro y edición de turnos (`app/estado_anotacion.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/app/estado_anotacion.py`
  - **Referencia SDD:** `spec.md` (RF-07, RF-08, HU-03..HU-08), `plan.md` §3.3–3.4, `data-model.md` §2
  - **Skill:** `software-engineer` + `ux-web-designer`
  - **Detalle:** Inicializar `st.session_state` ordenado por `orden_anotacion`, implementar lógica pura de `dividir_turno(turnos, idx, posicion_o_marcador)`, `unir_con_anterior(turnos, idx)`, `agregar_hablante(turnos)`, pila `deshacer`, cronómetro efectivo por clip (tope 900 s por inactividad), serialización/deserialización de `anot_{anotador}_{fecha}_n{NNN}.json` con validación de `sha256_manifest`, y contador de recordatorio cada 3 clips completados.
  - **Verificación:** Pruebas unitarias sobre dividir/unir/deshacer, acumulación de tiempo y rechazo de JSON con `sha256_manifest` distinto.

- [x] **T-11: Construir interfaz Streamlit de tarjetas por turno (`app/streamlit_app.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/app/streamlit_app.py`
  - **Referencia SDD:** `spec.md` (RF-06..RF-08, §4 Guía congelada, HU-01..HU-08), `plan.md` §3.3–3.4
  - **Skill:** `ux-web-designer`
  - **Detalle:**
    - Barra lateral: nombre de anotador, carga de `clips_piloto.zip` (si no hay `st.secrets`), importar/exportar JSON, barra de progreso (`X/24`), selector rápido de clips (sin revelar `estrato` ni `entrevista`) y guía de anotación v1.0 plegable.
    - Panel principal: reproductor de audio HTML5 con controles `-5 s`, `+5 s` y velocidad (`0.75x`, `1.0x`, `1.25x`) aislado de las tarjetas mediante **`@st.fragment`** para evitar reinicios de audio al escribir.
    - Tarjetas por turno: desplegable `H1`/`H2`... (+ botón `+ Nuevo hablante`), `text_area`, botones `Dividir en ||` (o selector de palabra), `Unir con anterior`, `Deshacer`, opción `No anotable` con motivo, y botón `Guardar y siguiente`.
    - Respaldo automático en `localStorage` del navegador keyed por `sha256_manifest`.
  - **Verificación:** `streamlit run ETAPA_1_speech2textDi/app/streamlit_app.py` arranca sin errores; editar texto o dividir tarjetas no reinicia el audio; no se muestra `estrato`, `SPEAKER_XX`, `score` ni `avg_logprob`; exportar y reimportar restaura 100 % del estado.

---

## Bloque 4 — Motor de métricas e inferencia (`ETAPA_1_speech2textDi/metricas/`)

- [x] **T-12: Implementar métricas ASR y entidades automáticas (`metricas/calculo_asr.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/metricas/calculo_asr.py`
  - **Referencia SDD:** `spec.md` (RF-10), `research.md` §3.1 y §3.4
  - **Skill:** `software-engineer` + `data-statistician`
  - **Detalle:** Calcular `S`, `D`, `I`, `H`, `N_ref`, `N_hip`, `WER` y `CER` con `jiwer`; implementar extractor determinista de cifras, siglas (`[A-ZÁÉÍÓÚÑ]{2,}`) y nombres propios internos de oración sobre el texto *gold* sin normalizar y cruzar contra la alineación de `jiwer.process_words` para obtener `entidades_ref`, `entidades_err` y `tasa_err_entidades`.
  - **Verificación:** Validado con casos sintéticos exactos (`WER = 0`, 1 sustitución, 1 cifra alterada `15% -> 50%`, sigla `ONPE` borrada).

- [x] **T-13: Implementar métricas de diarización textual (`metricas/calculo_diarizacion.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/metricas/calculo_diarizacion.py`
  - **Referencia SDD:** `spec.md` (RF-10, §6 Casos límite), `research.md` §3.2, §3.3 y §3.5
  - **Skill:** `software-engineer` + `data-statistician`
  - **Detalle:** Implementar `calcular_wder(...)` (alineación `jiwer` + matriz de contingencia + `scipy.optimize.linear_sum_assignment`), `calcular_cpwer(...)` (matriz $K \times K$ de distancias de edición por hablante con padding `""` + `linear_sum_assignment`), cálculo de `delta_hablantes` ($\Delta H$) y `calcular_fragmentacion_lt10(...)` (palabras en turnos internos de `< 10` palabras).
  - **Verificación:** Invarianza a permutación de etiquetas (`H1/H2` vs `SPEAKER_07/SPEAKER_02` -> `WDER = 0`, `cpWER = WER`); caso con sobresegmentación (1 hablante real partido en 2 iguales -> `WDER = 0.5`, `ΔH = +1`).

- [x] **T-14: Implementar bootstrap, Spearman y dimensionamiento final (`metricas/inferencia.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/metricas/inferencia.py`
  - **Referencia SDD:** `spec.md` (RF-11, RF-12), `research.md` §3.6
  - **Skill:** `data-statistician` + `software-engineer`
  - **Detalle:** Implementar bootstrap no paramétrico remuestreando clips ($B = 10{.}000$, `numpy.random.default_rng(semilla)`) para métricas agregadas (globales y por estrato A/B), correlación de Spearman (`scipy.stats.spearmanr`) para `score_medio` y `avg_logprob_medio` vs. `WER`, y cálculo de $s_B$, $s_{\text{UCL}, 80\%}$ (`scipy.stats.chi2.ppf(0.20, df)`), $n_B$ para $E = 0{,}03$ y horas estimadas adicionales.
  - **Verificación:** Reproducibilidad exacta con semilla fija; verificación numérica contra tabla de referencia de `GUIA_SDD.md` (con $n_B = 16$ y $s = 0{,}10$ -> $s_{\text{UCL}} \approx 0{,}124$ y $n_B = 66$ para $E = 0{,}03$).

- [x] **T-15: Implementar CLI orquestador de métricas (`metricas/calcular_metricas.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/metricas/calcular_metricas.py`
  - **Referencia SDD:** `spec.md` (RF-09..RF-12), `contracts/cli_metricas.md`, `data-model.md` §3 y §4
  - **Skill:** `software-engineer`
  - **Detalle:** Validar `sha256_manifest`, verificar hashes `sha256_json` (y `sha256_wav`) contra `CodeCursos/Resultados/`, reconstruir vistas `segment` y `word` desde `Diario/*.json`, computar métricas por clip (`resultados_piloto.csv`, 40 columnas exactas) y resumen estadístico (`resumen_piloto.json`), soportando `--permitir-incompleto` y `--permitir-obsoletos`.
  - **Verificación:** Prueba end-to-end con una anotación sintética de prueba genera CSV y JSON conformes a `data-model.md`, códigos de salida `0/1/2` correctos y salida de terminal sin emojis.

---

## Bloque 5 — Reporte del piloto (`ETAPA_1_speech2textDi/reporte/`)

- [x] **T-16: Implementar generador del informe Markdown (`reporte/generar_reporte.py`)**
  - **Archivos:** `ETAPA_1_speech2textDi/reporte/generar_reporte.py`
  - **Referencia SDD:** `spec.md` (RF-12), `contracts/cli_reporte.md`
  - **Skill:** `data-statistician` + `software-engineer`
  - **Detalle:** Leer `resultados_piloto.csv` y `resumen_piloto.json`, generar `reporte/informe_piloto.md` en español académico con las 6 secciones obligatorias del contrato (trazabilidad, métricas primarias con IC 95 %, auditoría `segment` vs. `word` + fragmentación `< 10` + Spearman, desagregación exploratoria por candidato, top-5 peores clips, y tabla de dimensionamiento $n_B$ + plantilla de cierre del piloto).
  - **Verificación:** Genera Markdown bien formateado y completo a partir de entradas sintéticas; código de salida `1` si faltan archivos o campos obligatorios.

---

## Bloque 6 — Fase 5 SDD: Pruebas y documentación de usuario

- [x] **T-17: Suite de pruebas unitarias con casos sintéticos (`ETAPA_1_speech2textDi/tests/`)**
  - **Archivos:** `tests/test_normalizacion.py`, `tests/test_io_diario.py`, `tests/test_metricas_sinteticas.py`, `tests/test_muestreo_y_esquemas.py`
  - **Referencia SDD:** `spec.md` (§5, §6), `plan.md` §2, `research.md` §3
  - **Skill:** `data-statistician` + `software-engineer`
  - **Detalle:** Cubrir interpolación de palabras sin timestamp, normalización española, casos sintéticos con solución analítica conocida de WER/CER/WDER/cpWER/entidades/bootstrap/$n_B$, lógica de dividir/unir turnos, validación de hashes y rechazo de archivos obsoletos o con manifest distinto.
  - **Verificación:** `pytest ETAPA_1_speech2textDi/tests/` pasa al 100 % en <10 s sin depender de archivos de audio pesados.

- [x] **T-18: Redactar manual operativo del piloto (`ETAPA_1_speech2textDi/quickstart.md`)**
  - **Archivos:** `ETAPA_1_speech2textDi/quickstart.md`
  - **Referencia SDD:** `spec-drive.md` (Fase 5), `plan.md` §1 y §3.2
  - **Skill:** `code-architect`
  - **Detalle:** Guía paso a paso en español para: (1) crear entorno local y ejecutar `muestrear.py` + `recortar_clips.py`, (2) desplegar `app/streamlit_app.py` en Streamlit Community Cloud (con `CLIPS_ZIP_URL` en `st.secrets` o subida manual de `clips_piloto.zip`), (3) anotar y exportar el JSON a `gold/`, y (4) correr `calcular_metricas.py` y `generar_reporte.py`.
  - **Verificación:** Todos los comandos coinciden literalmente con los contratos CLI en `sdd/contracts/`.

---

## Orden sugerido de ejecución (Fase 4)

```text
T-01 -> T-02..T-05 (core) -> T-06..T-08 (muestreo + clips del piloto)
     -> T-09..T-11 (app Streamlit) -> T-12..T-15 (métricas) -> T-16 (reporte)
     -> T-17..T-18 (tests + quickstart)
```

