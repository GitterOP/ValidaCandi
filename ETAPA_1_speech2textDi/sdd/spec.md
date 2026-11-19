# Especificación Funcional — Etapa 1 (Piloto): ASR y Diarización Textual

- **Etapa:** `ETAPA_1_speech2textDi` (Piloto)
- **Versión de especificación:** `1.0`
- **Versión de guía de anotación:** `1.0`
- **Repositorio evaluado (solo lectura):** `/home/jd/Escritorio/CodeCursos` (`Resultados/Audios/*.wav` y `Resultados/Diario/*.json`)

---

## 1. Propósito y alcance

Validar empíricamente la calidad de la salida del Paso 2 de entrevistas de `CodeCursos` (WhisperX `large-v3` + `pyannote/speaker-diarization-3.1`) mediante un **piloto de 24 clips de 60 segundos** anotados por 1 evaluador humano, enfocado en los errores que afectan a los pasos posteriores del pipeline (`general.py`, `fragmentador_oraciones.py`, `procesador_atomico.py`, comparación semántica y auditoría NLI).

### Dentro de alcance
- Muestreo reproducible y estratificado de 24 clips sobre las 80 entrevistas del corpus.
- Recorte determinista de audio en formato liviano (`MP3 mono 64 kbps`) y empaquetado local (`clips_piloto.zip`) sin versionado en Git.
- Aplicación web en Streamlit (desplegable en **Streamlit Community Cloud**) basada en **tarjetas por turno `(Hablante, Texto)`** para construir la referencia *gold*.
- Cálculo reproducible de métricas de ASR y diarización a nivel de palabra/texto, con intervalos de confianza por bootstrap.
- Generación de informe técnico del piloto y recálculo del tamaño muestral final para margen $E = \pm 3\text{ pp}$ de WER.

### Fuera de alcance
- Identificación de la identidad real del hablante (`Speaker_Name`, `Es_Candidato` -> Etapa 2).
- Edición de forma de onda, timestamps sub-segundo, DER temporal y error de ubicación `|t_det - t_real|`.
- Cálculo de acuerdo entre anotadores (el piloto cuenta con 1 solo anotador).
- Modificación de cualquier archivo dentro de `/home/jd/Escritorio/CodeCursos`.

---

## 2. Requerimientos funcionales

### 2.1 Muestreo y trazabilidad (`muestreo/muestrear.py`)
- **RF-01 (Marco muestral y verificación de integridad):** El muestreador debe leer las 80 parejas `(WAV, JSON)` de `CodeCursos/Resultados/`, verificar correspondencia 1 a 1, calcular el hash **SHA-256** de cada archivo seleccionado y rechazar la corrida si faltan archivos o el JSON carece de `segments`.
- **RF-02 (Diseño estratificado del piloto):** Con semilla fija (`20261119` por defecto), debe seleccionar exactamente **24 clips de 60 s** (3 entrevistas distintas por candidato, 8 candidatos):
  - **16 clips de Estrato B (aleatorio):** 2 por candidato; inicio muestreado uniformemente en `[0, duracion_entrevista - 60]`.
  - **8 clips de Estrato A (anclado a cambio de turno):** 1 por candidato; se sortea un cambio de turno detectado (a nivel de `segment["speaker"]`) cuyo instante $t_c$ cumpla $t_c \in [45,\; \text{duracion} - 45]$ y se fija el inicio en $t_c - u$, con $u \sim U(15, 45)\text{ s}$.
- **RF-03 (Ajuste de bordes sin cortar palabras):** Los extremos `[inicio_s, fin_s]` se ajustan al hueco entre palabras más cercano dentro de un máximo de `±2,0 s` para evitar palabras partidas al inicio o fin del clip.
- **RF-04 (Interpolación determinista y precarga de turnos):**
  - Toda palabra de WhisperX sin `start`/`end` (en el corpus real son principalmente números y porcentajes, 0,80 % del total) **debe interpolarse linealmente** usando las palabras vecinas con timestamp o los bordes del segmento padre; jamás debe descartarse.
  - Toda palabra sin `speaker` hereda el `speaker` de la palabra anterior válida del mismo segmento; si no existe, la siguiente válida; y como último recurso `segment.get("speaker", "UNKNOWN")`.
  - Las palabras cuyo punto medio `(start + end) / 2` cae en `[inicio_s, fin_s]` se agrupan en turnos consecutivos según el criterio de `general.py` (`segment["speaker"]`), remapeados en orden de primera aparición a etiquetas genéricas **`H1`, `H2`, `H3`...**, y se embeben en `manifest_piloto.json` como `precarga_ui`.
- **RF-05 (Recorte y empaquetado de clips — `muestreo/recortar_clips.py`):** A partir de `manifest_piloto.json`, debe recortar cada clip desde el WAV fuente usando `ffmpeg` (`MP3`, mono, 16 kHz, 64 kbps), calcular el `sha256_clip` de cada MP3, registrar los hashes en el manifest y generar un archivo `clips_piloto.zip` (~12 MB) listo para subir a la app web.

### 2.2 Aplicación de anotación (`app/streamlit_app.py`)
- **RF-06 (Carga segura de clips sin audio en Git):** La app debe leer `manifest_piloto.json` del repositorio y cargar los MP3 de los clips mediante:
  1. Descarga automática desde `st.secrets["CLIPS_ZIP_URL"]` (si está configurado en Streamlit Community Cloud), descomprimiendo en caché efímero, o
  2. Subida manual de `clips_piloto.zip` mediante `st.file_uploader`.
  Antes de habilitar la anotación, la app debe verificar que el `sha256_clip` de cada MP3 coincida con `manifest_piloto.json`.
- **RF-07 (Interfaz de tarjetas por turno sin sesgos):**
  - Mostrar un clip por pantalla con reproductor de audio (play/pausa, retroceder 5 s y selector de velocidad `0.75x`, `1.0x`, `1.25x`).
  - **Ocultar** el `estrato` (`A`/`B`), los nombres reales de hablantes, las etiquetas `SPEAKER_XX` originales y los valores de `score`/`avg_logprob` de WhisperX.
  - Presentar los turnos precargados como **tarjetas editables** secuenciales, cada una con:
    - Selector desplegable de hablante (`H1`, `H2`, ..., más opción `+ Nuevo hablante`).
    - Campo de texto multilínea editable con el texto del turno.
    - Acción **`Dividir turno`**: permite partir una tarjeta en dos indicando el punto de corte en el texto (ej. insertando `||` o eligiendo el índice de palabra) y asignando la nueva etiqueta al segundo bloque.
    - Acción **`Unir con anterior`**: fusiona el texto de la tarjeta actual al final de la tarjeta previa (conservando la etiqueta de la previa).
    - Acción **`Eliminar turno vacío`** (solo si el texto queda vacío).
  - Control para marcar el clip como **`no_anotable`** seleccionando un motivo (`solo_musica`, `solo_ruido`, `inaudible_total`, `otro`).
- **RF-08 (Persistencia, validación de manifest y cronómetro):**
  - Soportar importación y exportación del archivo de progreso `anot_{anotador}_{fecha}_n{NNN}.json`.
  - Rechazar la importación si `sha256_manifest` no coincide con el manifest activo o si el esquema JSON es inválido.
  - Mantener respaldo automático en el navegador (`localStorage`) ante recargas accidentales y mostrar aviso de exportación cada 3 clips completados.
  - Registrar automáticamente el `tiempo_anotacion_s` efectivo dedicado a cada clip (acumulable si el anotador regresa al clip).

### 2.3 Cálculo de métricas y reporte (`metricas/calcular_metricas.py`, `reporte/generar_reporte.py`)
- **RF-09 (Verificación de obsolescencia):** Antes de calcular métricas, el script debe verificar que los `sha256_wav` y `sha256_json` registrados en `manifest_piloto.json` coincidan con los archivos actuales en `/home/jd/Escritorio/CodeCursos/Resultados/` y que `sha256_manifest` coincida entre manifest y archivo de anotación. Si algún archivo fuente cambió, debe abortar con código de error explícito (salvo bandera `--permitir-obsoletos` que lo marca en el reporte).
- **RF-10 (Métricas primarias y secundarias por clip y agregadas):** Calcular sobre todos los clips anotables (`estado == "completo"`):
  - **Primarias:**
    1. **WER** (agregado $\sum(S+D+I)/\sum N$ y media/mediana por clip).
    2. **WDER** (*Word-level Diarization Error Rate*) bajo mapeo óptimo 1-a-1 de hablantes.
    3. **cpWER** (*Concatenated minimum-permutation WER*) y brecha $\Delta_{\text{diar}} = \text{cpWER} - \text{WER}$.
    4. **Error en el número de hablantes** ($\Delta H = H_{\text{hip}} - H_{\text{ref}}$: sesgo medio, % exacto, % sobresegmentado, % subsegmentado).
  - **Secundarias (automáticas):**
    5. **CER** (*Character Error Rate*).
    6. **Tasa de error en cifras, siglas y nombres propios** (extracción automática sobre texto *gold* sin normalizar).
    7. **Auditoría del puente Paso 2 -> Paso 3:** calcular WDER, cpWER y $\Delta H$ tanto para la vista **`segment` (como consume `general.py`)** como para la vista **`word` (salida fina `words[].speaker` de WhisperX)**.
    8. **Tasa de fragmentación crítica (`< 10` palabras):** proporción de palabras de la hipótesis atrapadas en turnos contiguos de menos de 10 palabras (descartables por `fragmentador_oraciones.py`).
    9. **Correlación de Spearman** entre `avg_logprob` medio / `score` medio del clip y su WER.
- **RF-11 (Inferencia estadística):** Calcular intervalos de confianza al 95 % mediante **bootstrap no paramétrico remuestreando clips** ($B = 10{.}000$, semilla fija `20261119`), reportando resultados globales, por estrato (`A` vs. `B`) y desagregación exploratoria por candidato.
- **RF-12 (Informe del piloto y dimensionamiento final):** Generar `reporte/informe_piloto.md` con tablas de resultados, diagnóstico de errores y el cálculo automático del tamaño muestral final $n_B$ para $E = \pm 3\text{ pp}$ usando el límite superior de confianza al 80 % de la desviación estándar del WER en Estrato B ($s_{\text{UCL}}$):
  $$s_{\text{UCL}} = s_B \cdot \sqrt{\frac{n_{B,\text{piloto}} - 1}{\chi^2_{0.20,\; n_{B,\text{piloto}} - 1}}}, \qquad n_B = \left\lceil \left(\frac{1{,}96 \cdot s_{\text{UCL}}}{0{,}03}\right)^2 \right\rceil$$

---

## 3. Historias de usuario y criterios de aceptación

| ID | Historia de usuario | Criterio de aceptación verificable |
|:---|:--------------------|:-----------------------------------|
| **HU-01** | Como anotador, quiero cargar `clips_piloto.zip` (o que cargue desde `st.secrets`) y retomar mi archivo `anot_*.json` para continuar donde quedé. | Al importar un JSON válido, el progreso y las tarjetas editadas se restauran intactas y la vista salta al primer clip pendiente. |
| **HU-02** | Como anotador, quiero escuchar el clip con controles básicos (play/pausa, -5 s, velocidad) mientras edito las tarjetas. | El reproductor mantiene la reproducción fluida sin reiniciar el audio al editar texto en una tarjeta. |
| **HU-03** | Como anotador, quiero corregir el texto de cada turno directamente en tarjetas precargadas. | El texto editado se conserva al navegar entre clips y se serializa en UTF-8 limpio. |
| **HU-04** | Como anotador, quiero dividir un turno cuando WhisperX omitió un cambio de hablante y asignar `H1`, `H2`, ... | Al dividir una tarjeta, aparecen dos tarjetas consecutivas sin pérdida de texto; la nueva tarjeta recibe por defecto un hablante distinto editable. |
| **HU-05** | Como anotador, quiero corregir falsas divisiones cambiando la etiqueta a la misma del bloque anterior o pulsando `Unir con anterior`. | Al unir dos tarjetas o asignar la misma etiqueta consecutiva, el exportador/evaluador trata las palabras bajo el mismo hablante sin discrepancias. |
| **HU-06** | Como anotador, quiero marcar un clip como `no_anotable` con motivo si solo contiene música o ruido. | El clip queda marcado `no_anotable`, no exige tarjetas válidas y avanza al siguiente clip. |
| **HU-07** | Como anotador, quiero exportar mi JSON en cualquier momento y contar con respaldo local en el navegador. | El botón de descarga genera un JSON válido conforme a `data-model.md`; si recargo la pestaña, la app ofrece restaurar el respaldo local. |
| **HU-08** | Como investigador, quiero que la app rechace archivos de progreso de otro manifest y registre el tiempo efectivo por clip. | Cargar un JSON con `sha256_manifest` distinto muestra error y no sobreescribe el estado; cada clip completo tiene `tiempo_anotacion_s > 0`. |
| **HU-09** | Como investigador, quiero ejecutar scripts deterministas que verifiquen SHA-256 y generen métricas e informe reproducibles. | Dos ejecuciones consecutivas con la misma semilla producen exactamente los mismos resultados numéricos e IC bootstrap. |

---

## 4. Guía de anotación congelada (v1.0)

Esta guía se mostrará en un panel plegable dentro de la propia app Streamlit:

1. **Transcribir lo que se dijo, no analizar errores:** corregir directamente el texto precargado hasta que refleje fielmente las palabras pronunciadas.
2. **Números y porcentajes:** escribirlos en **dígitos** (`15%`, `2026`, `3 millones`, `20`).
3. **Muletillas no léxicas:** no agregar sonidos puramente vocálicos de relleno (`eh`, `mmm`, `ah`, `uh`). Si el hablante repite palabras reales o se corrige en una frase, conservar las palabras reales pronunciadas.
4. **Nombres propios, instituciones y siglas:** escribirlos con ortografía oficial (`Fujimori`, `Combutters`, `ONPE`, `JNJ`, `BCRP`, `IGV`). Si hay duda razonable sobre un nombre poco conocido, escribir la mejor aproximación fonética y añadir `?` al final (solo como marca de revisión; el normalizador quita `?`).
5. **Tramos ininteligibles:** escribir `[inaudible]` en el lugar exacto del texto; no adivinar.
6. **Habla solapada:** si dos personas hablan encima y no puede transcribirse claramente cada intervención por separado, escribir `[solapado]` en el punto afectado. Si ambos mensajes son claros y distinguibles, transcribirlos en tarjetas separadas.
7. **Etiquetas de hablante (`H1`, `H2`, ...):** asignar etiquetas genéricas en orden de aparición **dentro de cada clip** (cada clip comienza de cero en `H1`). No intentar mantener coherencia de `H1`/`H2` entre clips distintos ni identificar al candidato.
8. **Interjecciones breves de apoyo:** respuestas mínimas (`ajá`, `claro`, `sí`) que otro interlocutor emite mientras el hablante principal continúa sin ceder la palabra **no** generan un turno separado.
9. **Clip sin habla útil:** si el clip contiene solo música, cortinas o ruido sin habla evaluable, marcarlo como **`no_anotable`** indicando el motivo.

---

## 5. Reglas de normalización para métricas (v1.0)

La misma función determinista `normalizar_texto(texto)` se aplica **idénticamente** a la referencia *gold* y a la hipótesis de WhisperX antes de calcular WER, CER, WDER y cpWER:

1. **Etiquetas especiales:** remover marcadores `[inaudible]`, `[solapado]`, `[musica]`, `[ruido]` (y contabilizar aparte cuántos ocurrieron en cada clip para el diagnóstico).
2. **Símbolos frecuentes:** expandir `%` -> ` por ciento ` únicamente si se usa normalización verbal, o **regla fija adoptada**: unificar `por ciento` -> `%` y luego separar `%` como token `porcentaje` (ej. `15%` y `15 por ciento` ambos normalizan a `15 porcentaje`).
3. **Números:** convertir números escritos en palabras en español (`cero`..`millones`) a **dígitos** cuando sea inequívoco (ver `research.md`), y eliminar separadores de miles (`10.000` / `10,000` -> `10000`) para evitar penalizaciones cosméticas.
4. **Minúsculas y tildes:** convertir a minúsculas y eliminar diacríticos/tildes (conservando `ñ`), de modo que diferencias menores de acentuación no inflen artificialmente el WER (se reportará además WER con tildes como columna de diagnóstico opcional si se requiere).
5. **Puntuación:** eliminar signos de puntuación (`.,;:¿?¡!"'()[]—-`) reemplazando guiones por espacio y colapsando espacios múltiples.
6. **Lista cerrada de muletillas no léxicas (por si WhisperX las emite):** remover tokens exactos en `{eh, ehm, em, mm, mmm, ah, uh, um, hm, hmm}`.

---

## 6. Casos límite (Edge Cases)

| Caso límite | Comportamiento especificado |
|:------------|:----------------------------|
| **Palabra sin timestamp en `Diario/*.json`** (0,80 %; números/porcentajes) | Se interpola linealmente `(start, end)` entre las palabras vecinas con timestamp o los límites del segmento padre. Nunca se descarta. |
| **Palabra o segmento sin `speaker`** | Herencia: palabra anterior válida del segmento -> palabra siguiente válida -> `segment["speaker"]` -> `"UNKNOWN"`. |
| **Palabra que cruza el borde `inicio_s` o `fin_s`** | Se incluye en el clip si y solo si su punto medio `(start + end) / 2` pertenece a `[inicio_s, fin_s]`. |
| **Clip con 1 solo hablante (monólogo en Estrato B)** | Clip válido. Si hipótesis también tiene 1 hablante -> `WDER = 0`, `ΔH = 0`; si hipótesis tiene >1 hablante -> penaliza `WDER`, `cpWER` y `ΔH > 0`. |
| **Clip marcado `no_anotable`** | Se conserva en `resultados_piloto.csv` con `estado = "no_anotable"` y métricas numéricas en `NaN`. Se excluye de los promedios y del bootstrap; se reporta la tasa de clips no anotables. No se reemplaza en el piloto. |
| **Clip con `[inaudible]` o `[solapado]` parcial** | Se contabiliza el número de marcas en `n_inaudible` y `n_solapado`. Las marcas se excluyen del texto normalizado; los clips con >3 marcas se señalan en el reporte para análisis de sensibilidad (con y sin dichos clips). |
| **Hablante en hipótesis sin pareja 1-a-1 (sobresegmentación)** | En WDER, toda palabra asignada a un hablante no emparejado cuenta como error de atribución. En cpWER, ese hablante se empareja con una cadena vacía `""` en la referencia, penalizando todas sus palabras como inserciones. |
| **Referencia con 0 palabras tras normalizar** | El clip se trata como no evaluable para WER/WDER/cpWER (métricas `NaN`, alerta en log). |
| **Turnos consecutivos del mismo hablante en la anotación** | Al cargar `anot_*.json`, el evaluador fusiona automáticamente turnos adyacentes que tengan la misma etiqueta `hablante` antes de contar turnos, pero preserva el orden secuencial de palabras. |
| **Cambio de hash SHA-256 en `CodeCursos`** | `calcular_metricas.py` detecta el desacople y detiene la corrida con error no-cero indicando los archivos modificados. |
| **Entrevista corta (~10 min) en muestra final** | En el piloto solo se toma 1 clip por entrevista (siempre cabe). En la muestra final, el muestreador garantizará no-solapamiento con separación mínima de 5 s entre clips de la misma entrevista. |

