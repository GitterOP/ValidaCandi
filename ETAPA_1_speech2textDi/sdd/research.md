# Investigación Técnica y Fundamentos Algorítmicos — Etapa 1 (Piloto)

Este documento respalda las decisiones técnicas y matemáticas de [spec.md](spec.md) y [plan.md](plan.md) con mediciones directas sobre el corpus real de `/home/jd/Escritorio/CodeCursos/Resultados/` (inspeccionado en modo solo lectura el 2026-11-19).

---

## 1. Diagnóstico empírico del corpus real (`Resultados/Diario/*.json`)

### 1.1 Integridad y volumen
- **Archivos:** 80 `*.wav` y 80 `*.json` con correspondencia exacta 1 a 1 (10 entrevistas por cada uno de los 8 candidatos: `1_keiko` a `8_cerron`).
- **Duraciones:** mínimo `592,6 s` (9,9 min), máximo `5794,9 s` (96,6 min). Todas las entrevistas superan ampliamente el margen necesario para muestrear clips de 60 s con ventana `[45, duracion - 45]` en Estrato A.
- **Segmentos y palabras:** 47.542 segmentos (`0` sin `avg_logprob`, `75` sin `speaker` = 0,16 %) y 559.781 palabras totales.

### 1.2 Hallazgo crítico #1: Palabras sin timestamp (`0,80 %` = 4.469 palabras)
Al inspeccionar ejemplos reales de palabras sin `start`/`end` (que tampoco tienen `score` ni `speaker`), se comprobó que corresponden casi en su totalidad a **números, años y porcentajes** que el modelo de alineación fonética `wav2vec2` de WhisperX no alinea a nivel de carácter:
- Ejemplos reales observados: `{'word': '10'}`, `{'word': '55%,'}`, `{'word': '2011.'}`, `{'word': '2016'}`, `{'word': '2021,'}`.

**Decisión:** **prohibido descartar palabras sin timestamp.** Descartarlas eliminaría silenciosamente cifras y fechas críticas del discurso político. Se especifica interpolación lineal determinista dentro de su segmento padre (`core/io_diario.py`):
1. Sea $w_k$ una secuencia contigua de $m$ palabras sin timestamp dentro de un segmento $S$ con bordes $[t_{\text{seg\_ini}}, t_{\text{seg\_fin}}]$.
2. Sea $t_L$ el `end` de la palabra anterior con timestamp (o $t_{\text{seg\_ini}}$ si no existe) y $t_R$ el `start` de la palabra siguiente con timestamp (o $t_{\text{seg\_fin}}$ si no existe), garantizando $t_R \ge t_L$.
3. Cada palabra $j \in \{0, \dots, m-1\}$ del bloque recibe:
   $$\text{start}_j = t_L + \frac{j}{m}(t_R - t_L), \qquad \text{end}_j = t_L + \frac{j + 1}{m}(t_R - t_L)$$
4. Para `speaker` ausente (`0,89 %` de las palabras): hereda el `speaker` de la palabra anterior válida dentro del mismo segmento; si no existe, la siguiente válida; si todo el segmento carece de hablante a nivel palabra, hereda `segment.get("speaker") or "UNKNOWN"`.

### 1.3 Hallazgo crítico #2: Brecha `segment["speaker"]` vs. `words[].speaker`
Al revisar `CodeCursos/common/general.py` (`merge_diarization`, líneas 63–103):
- `general.py` ignora `words[].speaker` y agrupa segmentos contiguos por `segment["speaker"]`.
- En una muestra de 10 archivos de `Diario/*.json` (9.356 segmentos), **1.018 segmentos (10,9 %)** contenían palabras asignadas a más de un hablante distinto internamente (`1.955` cambios a nivel segmento vs. `2.505` cambios a nivel palabra).

**Decisión:** `calcular_metricas.py` construirá dos vistas de hipótesis desde el mismo `Diario/*.json`:
- **Vista `segment` (primaria para validar el flujo real):** replica exactamente `merge_diarization()` de `general.py`, asignando a todas las palabras del segmento la etiqueta `segment.get("speaker") or "UNKNOWN"`.
- **Vista `word` (diagnóstica de WhisperX crudo):** utiliza `words[].speaker` (con la herencia determinista del §1.2).

Comparar ambas vistas contra la misma referencia *gold* permite cuantificar exactamente si el colapso a nivel segmento de `general.py` empeora o mejora (por suavizado de ruido) el WDER y el cpWER.

### 1.4 Densidad de cambios de turno
Sobre las 80 entrevistas (3.742 ventanas consecutivas de 60 s):
- Mediana de cambios a nivel segmento: `2,25 cambios/min`.
- El **79,6 %** de las ventanas de 60 s tiene ≥ 1 cambio de turno; el **20,4 %** son tramos de un solo hablante.
- Mantener **Estrato B (2 aleatorios/candidato)** + **Estrato A (1 anclado a cambio/candidato)** garantiza tanto estimaciones insesgadas en B (incluyendo monólogos para detectar sobresegmentación) como cobertura segura de transiciones en A para todos los candidatos.

---

## 2. Normalización de texto español (`core/normalizacion.py`)

Para evitar sesgos al comparar texto editado por humano contra salida de WhisperX, ambos pasan por la misma tubería determinista:

1. **Conteo y remoción de etiquetas especiales:** detectar y contar `[inaudible]`, `[solapado]`, `[musica]`, `[ruido]` (insensible a mayúsculas); eliminarlos del texto antes de tokenizar.
2. **Porcentajes:** unificar `(\d+)\s*%` y `(\d+)\s+por\s+ciento` a `\1 porcentaje`.
3. **Separadores numéricos:** unificar separadores de miles (`10.000`, `10,000` -> `10000`) preservando decimales con punto (`3,5` -> `3.5`).
4. **Números en palabras -> dígitos (subconjunto seguro en español):** convertir cardinales explícitos frecuentes (`cero`..`noventa y nueve`, `cien`/`ciento`, `mil`, años frecuentes) a dígitos mediante parser determinista acotado (evitando ambigüedad con el artículo indefinido `un`/`una`, que **no** se convierte a `1` salvo ante `millón`/`mil`/`por ciento`).
5. **Minúsculas y diacríticos:** pasar a minúsculas, descomponer Unicode (`NFD`) y remover tildes combinantes preservando explícitamente `ñ` (`á->a, é->e, í->i, ó->o, ú->u, ü->u, ñ->ñ`).
6. **Puntuación:** reemplazar `-`, `—`, `/` por espacio; eliminar todo carácter fuera de `[a-z0-9ñ.\s]` (quitando puntos finales que no sean decimales entre dígitos).
7. **Muletillas no léxicas:** eliminar tokens exactos pertenecientes al conjunto cerrado `{"eh", "ehm", "em", "mm", "mmm", "ah", "uh", "um", "hm", "hmm"}`.

---

## 3. Algoritmos exactos de métricas

### 3.1 WER y CER (`jiwer`)
- Se emplea `jiwer.process_words(ref_norm, hip_norm)` para obtener exactamente `substitutions` ($S$), `deletions` ($D$), `insertions` ($I$), `hits` ($H$) y $N_{\text{ref}} = S + D + H$.
- **WER por clip:** $(S + D + I) / N_{\text{ref}}$.
- **WER agregado (global o por estrato):** $\sum (S_i + D_i + I_i) / \sum N_{\text{ref}, i}$ (ponderado por número de palabras de referencia, conforme a estándar NIST/ASR).
- **CER:** análogo mediante `jiwer.process_characters(ref_norm, hip_norm)`.

### 3.2 WDER — *Word-level Diarization Error Rate* (Shafey et al., 2019)
Dada una secuencia de palabras de referencia con etiquetas de hablante $\{(r_1, s^{\text{ref}}_1), \dots, (r_N, s^{\text{ref}}_N)\}$ y una secuencia de hipótesis $\{(h_1, s^{\text{hip}}_1), \dots, (h_M, s^{\text{hip}}_M)\}$:

1. Se calcula la alineación óptima de palabras mediante `jiwer.process_words` (distancia de Levenshtein a nivel token).
2. Se extraen todos los pares alineados de tipo **`equal` (acierto)** y **`substitute` (sustitución)** — siguiendo exactamente la definición original de Shafey et al. (2019), donde las inserciones y borrados no tienen par de hablante biunívoco:
   - Sea $P = \{(s^{\text{ref}}_k, s^{\text{hip}}_k)\}_{k=1}^{|P|}$ el conjunto de pares de hablantes alineados (donde $|P| = H + S$).
3. Se construye la matriz de contingencia $M \in \mathbb{Z}_{\ge 0}^{K_R \times K_H}$ donde $M_{a,b}$ cuenta cuántas veces el hablante de referencia $a$ se alinea con el hablante de hipótesis $b$.
4. Se resuelve la **asignación óptima 1-a-1** que maximiza las coincidencias mediante el algoritmo Húngaro (`scipy.optimize.linear_sum_assignment(-M)`):
   $$\text{correct\_spk} = \sum_{(a, b) \in \pi^*} M_{a, b}$$
5. Se calcula:
   $$\text{WDER} = 1 - \frac{\text{correct\_spk}}{|P|} = \frac{|P| - \text{correct\_spk}}{S + H}$$
   - **WDER agregado:** $\sum (|P|_i - \text{correct\_spk}_i) / \sum |P|_i$.
   - Si $|P| = 0$ en un clip, WDER es `NaN`.
   - **Propiedad clave:** es completamente invariante a los nombres de las etiquetas (`H1`, `H2` vs. `SPEAKER_00`, `SPEAKER_03`), penaliza tanto subsegmentación como sobresegmentación, y no requiere timestamps.

### 3.3 cpWER — *Concatenated minimum-permutation WER* (Watanabe et al., CHiME-6)
1. Para cada hablante único $a \in \mathcal{S}_{\text{ref}}$ del clip, se concatenan en orden cronológico todas sus palabras normalizadas en una cadena $R_a$. Análogamente, para cada hablante $b \in \mathcal{S}_{\text{hip}}$, se forma $H_b$.
2. Sea $K = \max(|\mathcal{S}_{\text{ref}}|, |\mathcal{S}_{\text{hip}}|)$. Si uno de los dos lados tiene menos hablantes, se completa con cadenas vacías `""` hasta dimensión $K$.
3. Se construye la matriz de costos $C \in \mathbb{Z}_{\ge 0}^{K \times K}$ donde:
   $$C_{a, b} = \text{edit\_distance\_words}(R_a, H_b) = S_{a,b} + D_{a,b} + I_{a,b}$$
   (si $R_a = \text{""}$, $C_{a,b} = |H_b|$; si $H_b = \text{""}$, $C_{a,b} = |R_a|$).
4. Dado que $\text{cpWER}$ minimiza $\sum_{a=1}^K \text{edit\_distance}(R_a, H_{\pi(a)})$ sobre todas las biyecciones $\pi$, el problema es **exactamente equivalente** a una asignación lineal mínima y `scipy.optimize.linear_sum_assignment(C)` encuentra el **óptimo global exacto** en $O(K^3)$ (sin explosión factorial aunque un clip tuviera 10 hablantes).
5. Resultado:
   $$\text{cpWER} = \frac{\sum_{(a,b) \in \pi^*} C_{a,b}}{N_{\text{ref}}}, \qquad \Delta_{\text{diar}} = \text{cpWER} - \text{WER}$$
   - **cpWER agregado:** suma de los costos óptimos por clip dividida por $\sum N_{\text{ref}, i}$.

### 3.4 Extracción automática de cifras, siglas y nombres propios (`calculo_asr.py`)
Sin requerir anotación manual adicional ni modelos pesados (`spacy`), se extraen automáticamente entidades candidatas sobre el texto *gold* **antes de pasar a minúsculas** (para aprovechar mayúsculas y formato):
1. **Cifras y porcentajes:** toda secuencia numérica (`\b\d+(?:[.,]\d+)?%?\b`).
2. **Siglas:** tokens de 2 o más letras en mayúsculas (`\b[A-ZÁÉÍÓÚÑ]{2,}\b`, p. ej. `ONPE`, `JNJ`, `IGV`, `BCRP`, `PNP`).
3. **Nombres propios internos de oración:** palabras capitalizadas (`[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+`) que **no** están al inicio de una oración (es decir, no precedidas por inicio de turno ni por `.`, `?`, `!`, `¿`, `¡`), excluyendo una lista breve de tratamientos/meses comunes opcionales.

Cada token extraído se normaliza con `normalizar_texto()` y se evalúa su **tasa de error en entidades** sobre la alineación `jiwer.process_words` (proporción de tokens de entidad de la referencia cuya operación en la alineación no fue `equal`, es decir, fueron sustituidos o borrados en WhisperX).

### 3.5 Pérdida potencial por el filtro `< 10` palabras
Replica la regla de `CodeCursos/common/fragmentador_oraciones.py` (`if len(text.split()) < 10: return False`):
- Sobre los turnos fusionados de la hipótesis (en vista `segment`), se calcula la proporción de palabras totales de la hipótesis que caen en turnos con menos de 10 palabras.
- Para evitar sesgo de bordes artificiales del clip de 60 s, el cálculo también se reporta excluyendo el primer y el último turno del clip (o señalando explícitamente que es un indicador de fragmentación interna dentro de los 60 s).

### 3.6 Inferencia por bootstrap y dimensionamiento $n_B$
- **Bootstrap no paramétrico:** $B = 10{.}000$ réplicas con `numpy.random.default_rng(semilla)`. En cada réplica se remuestrean con reemplazo los clips evaluables (por estrato para las métricas de A y B, y globalmente para el total) y se recalcula cada métrica agregada; el IC 95 % corresponde a los percentiles `2.5` y `97.5`.
- **Dimensionamiento posterior ($E = \pm 3\text{ pp}$):** sobre la desviación estándar muestral $s_B$ (`ddof=1`) del WER por clip en los clips evaluables de Estrato B ($n_{B,\text{eval}}$):
  $$s_{\text{UCL}} = s_B \cdot \sqrt{\frac{n_{B,\text{eval}} - 1}{\chi^2_{0.20,\; n_{B,\text{eval}} - 1}}}, \qquad n_B = \left\lceil \left(\frac{1{,}96 \cdot s_{\text{UCL}}}{0{,}03}\right)^2 \right\rceil$$
  utilizando `scipy.stats.chi2.ppf(0.20, df=n_B_eval - 1)`.

---

## 4. Recorte de audio (`ffmpeg`) y compatibilidad Streamlit Cloud

- **Comando determinista de recorte:**
  `ffmpeg -y -ss <inicio_s> -t <duracion_s> -i <wav_fuente> -ac 1 -ar 16000 -b:a 64k -map_metadata -1 <salida.mp3>`
  - `-map_metadata -1` garantiza archivos reproducibles sin encabezados variables de fecha/herramienta, manteniendo estable `sha256_clip`.
  - Tamaño estimado: `64 kbps * 60 s / 8 ≈ 480 KB` por clip (~11,5 MB los 24 clips en `clips_piloto.zip`), muy por debajo del límite de subida de 200 MB de Streamlit Cloud y del límite de RAM.
- **Reproductor sin reinicio:** `@st.fragment` de Streamlit (>= 1.37) aísla las re-ejecuciones de las tarjetas de turnos respecto al reproductor de audio del clip actual.

