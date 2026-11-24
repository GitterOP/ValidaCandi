# Informe de Validacion — Etapa 1 (Piloto): ASR y Diarizacion Textual


## 1. Ficha tecnica y trazabilidad

| Elemento | Valor |
|:---------|:------|
| Fecha de calculo | `2026-11-24T12:16:56-05:00` |
| `sha256_manifest` | `dadc91a0a8dc7da0cb36db43f36f7fe4f1add25849f9a87559c16cad2bd298c5` |
| Archivo de anotacion | `/home/jd/Escritorio/ValidaCandi/ETAPA_1_speech2textDi/gold/pilot/anot_jd_2026-11-21_n024.json` |
| `sha256_anotacion` | `b8e7a871f3787b906e92592a36e77643fd30710ec4d2edb9363e5b75eb61e913` |
| Version de guia | `1.0` |
| Fuentes `CodeCursos` intactas | `Si` |
| Cobertura del piloto | 24 completos, 0 no anotables (de 24) |
| Clips evaluables por estrato | Estrato B = 16, Estrato A = 8 |
| Tiempo medio / total de anotacion | 130.1 s/clip (0.87 h totales) |
| Bootstrap | B = 10000 replicas (semilla `20261119`) |

---

## 2. Resultados primarios (global y por estrato)

Todas las metricas se reportan como estimacion puntual agregada con **IC 95 % por bootstrap** remuestreando clips.

| Metrica (vista `segment` = `general.py`) | Global | Estrato B (aleatorio) | Estrato A (anclado) |
|:-----------------------------------------|:-------|:----------------------|:--------------------|
| **WER** | 0.77% [0.46%, 1.09%] | 0.55% [0.25%, 0.93%] | 1.16% [0.60%, 1.64%] |
| **WDER** | 2.73% [1.23%, 4.36%] | 1.79% [0.43%, 3.44%] | 4.44% [1.38%, 7.75%] |
| **cpWER** | 6.02% [3.13%, 9.19%] | 4.13% [1.48%, 7.41%] | 9.45% [3.48%, 15.61%] |
| **Brecha diarizacion (`cpWER - WER`)** | 5.25% [2.40%, 8.33%] | 3.58% [0.86%, 6.86%] | 8.29% [2.62%, 14.32%] |

### Distribucion del error en numero de hablantes (`ΔH = H_hip - H_ref`)

| Indicador | Valor |
|:----------|:------|
| Sesgo medio (`ΔH`) | -0.042 hablantes/clip |
| Mediana (`ΔH`) | 0.0 |
| Clips exactos (`ΔH == 0`) | 95.83% |
| Clips sobresegmentados (`ΔH > 0`) | 0.00% |
| Clips subsegmentados (`ΔH < 0`) | 4.17% |

---

## 3. Resultados secundarios y auditoria del flujo

| Indicador | Estimacion global [IC 95 %] |
|:----------|:----------------------------|
| **CER** | 0.46% [0.22%, 0.74%] |
| **Error en cifras, siglas y nombres propios** | 2.84% [0.65%, 6.25%] |
| **Fragmentacion interna `< 10` palabras** | 1.73% [0.25%, 4.15%] |

### Auditoria del puente Paso 2 -> Paso 3 (`segment` vs. `word`)

Compara la agrupacion actual de `general.py` (`segment['speaker']`) frente a la salida fina de palabras de WhisperX (`words[].speaker`).

| Metrica | Vista `segment` (`general.py`) | Vista `word` (`words[].speaker`) |
|:--------|:-------------------------------|:---------------------------------|
| **WDER** | 2.73% [1.23%, 4.36%] | 4.10% [2.29%, 5.93%] |
| **cpWER** | 6.02% [3.13%, 9.19%] | 8.46% [4.95%, 12.04%] |

### Correlacion de confianza de WhisperX vs. WER (Spearman)

| Variable de confianza | rho de Spearman | p-valor |
|:----------------------|:----------------|:--------|
| `score_medio` (palabras) | -0.4937 | 0.01422 |
| `avg_logprob_medio` (segmentos) | -0.5835 | 0.00276 |

---

## 4. Desagregacion exploratoria por candidato

> **Nota metodologica:** Con $n \le 3$ clips por candidato en el piloto, estos valores son estrictamente **exploratorios** y no permiten inferir diferencias significativas entre candidatos.

| Candidato | n eval | WER | WDER (`segment`) | cpWER (`segment`) | `ΔH` medio |
|:----------|:------:|:----|:-----------------|:------------------|:-----------|
| `1_keiko` | 3 | 0.47% | 0.23% | 0.94% | -0.33 |
| `2_rla` | 3 | 0.92% | 6.18% | 13.04% | 0.00 |
| `3_carlosal` | 3 | 0.85% | 4.10% | 9.06% | 0.00 |
| `4_chau` | 3 | 0.54% | 1.63% | 3.77% | 0.00 |
| `5_jorgeni` | 3 | 1.03% | 1.25% | 3.51% | 0.00 |
| `6_robertosa` | 3 | 0.20% | 0.00% | 0.20% | 0.00 |
| `7_cesara` | 3 | 1.78% | 4.09% | 9.92% | 0.00 |
| `8_cerron` | 3 | 0.45% | 4.33% | 7.73% | 0.00 |

---

## 5. Inspeccion de los 5 peores clips

### Por WER (peores 5)

| Clip | Candidato | Estrato | WER | WDER (`seg`) | `ΔH` (`seg`) | Entidades err/ref |
|:-----|:----------|:-------:|:----|:-------------|:-------------|:-----------------|
| `P015` | `7_cesara` | B | 2.65% | 0.00% | 0 | 1/2 |
| `P004` | `5_jorgeni` | A | 2.30% | 0.00% | 0 | 1/2 |
| `P003` | `4_chau` | B | 2.15% | 0.00% | 0 | 0/5 |
| `P019` | `2_rla` | A | 1.63% | 5.98% | 0 | 0/5 |
| `P016` | `3_carlosal` | A | 1.52% | 5.56% | 0 | 0/12 |

### Por WDER (`segment`, peores 5)

| Clip | Candidato | Estrato | WDER (`seg`) | cpWER (`seg`) | WER | `ΔH` (`seg`) |
|:-----|:----------|:-------:|:-------------|:--------------|:----|:-------------|
| `P023` | `8_cerron` | A | 12.03% | 21.38% | 1.26% | 0 |
| `P021` | `7_cesara` | A | 11.19% | 23.45% | 1.38% | 0 |
| `P010` | `2_rla` | B | 10.81% | 22.30% | 0.68% | 0 |
| `P019` | `2_rla` | A | 5.98% | 13.04% | 1.63% | 0 |
| `P013` | `3_carlosal` | B | 5.79% | 11.58% | 0.00% | 0 |

---

## 6. Dimensionamiento de la muestra final y cierre del piloto

| Parametro | Valor |
|:----------|:------|
| Margen objetivo $E$ | +-3.0 pp |
| Clips Estrato B en el piloto | 16 |
| Desviacion estandar $s_B$ (WER por clip en B) | 0.0084 |
| Limite superior al 80 % ($s_{\text{UCL}}$) | 0.0101 |
| **Tamano final recomendado ($n_B$)** | **1** |
| Horas adicionales estimadas de anotacion | 0.00 h |

### Registro de cierre del piloto (completar tras revision)

- **Incidencias detectadas en la guia o la app:** *(completar)*
- **Decision de integracion:** *(documentar si los 24 clips se suman a la muestra final o se excluyen por cambio en la guia)*
