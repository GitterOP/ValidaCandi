# Contrato CLI — Cálculo de Métricas del Piloto

Cubre `ETAPA_1_speech2textDi/metricas/calcular_metricas.py`. Se ejecuta en local (solo lectura sobre `/home/jd/Escritorio/CodeCursos`).

---

## Firma CLI

```bash
python ETAPA_1_speech2textDi/metricas/calcular_metricas.py \
  --manifest ETAPA_1_speech2textDi/muestreo/manifest_piloto.json \
  --anotacion ETAPA_1_speech2textDi/gold/anot_jd_2026-11-20_n024.json \
  --salida-csv ETAPA_1_speech2textDi/metricas/resultados_piloto.csv \
  --salida-resumen ETAPA_1_speech2textDi/metricas/resumen_piloto.json \
  --semilla-bootstrap 20261119 \
  --n-bootstrap 10000 \
  --margen-objetivo 0.03
```

---

## Argumentos

| Bandera | Tipo | Requerido | Default | Descripción |
|:--------|:-----|:---------:|:--------|:------------|
| `--manifest` | `Path` | Sí | — | Ruta a `manifest_piloto.json` |
| `--anotacion` | `Path` | Sí | — | Ruta al archivo `anot_*.json` exportado de la app |
| `--repo-fuente` | `Path` | No | *(leído del manifest)* | Override opcional de la ruta de solo lectura a `CodeCursos` |
| `--salida-csv` | `Path` | No | `ETAPA_1_speech2textDi/metricas/resultados_piloto.csv` | Tabla de métricas por clip |
| `--salida-resumen` | `Path` | No | `ETAPA_1_speech2textDi/metricas/resumen_piloto.json` | Resumen agregado, IC bootstrap y $n$ final |
| `--semilla-bootstrap` | `int` | No | `20261119` | Semilla fija para bootstrap no paramétrico |
| `--n-bootstrap` | `int` | No | `10000` | Número de réplicas bootstrap ($B$) |
| `--margen-objetivo` | `float` | No | `0.03` | Margen objetivo $E$ de WER para dimensionar $n_B$ |
| `--permitir-incompleto` | `flag` | No | `False` | Permite corrida parcial cuando aún faltan clips por anotar (marcando `parcial=true` en el resumen) |
| `--permitir-obsoletos` | `flag` | No | `False` | Permite continuar si cambió algún SHA-256 en `CodeCursos` (marcando `fuentes_validadas_ok=false`) |

---

## Precondiciones
1. `manifest_piloto.json` y `anot_*.json` cumplen los esquemas de `sdd/data-model.md`.
2. `anotacion["sha256_manifest"] == manifest["sha256_manifest"]`.
3. Todos los clips del manifest tienen estado `"completo"` o `"no_anotable"` (salvo `--permitir-incompleto`).
4. Todos los `sha256_json` (y `sha256_wav` si existen) coinciden con `/home/jd/Escritorio/CodeCursos/Resultados/` (salvo `--permitir-obsoletos`).

---

## Transformaciones clave
1. Reconstruye para cada clip las dos vistas de hipótesis desde `CodeCursos/Resultados/Diario/<entrevista>.json` usando `core/io_diario.py`:
   - Vista **`segment`** (idéntica a `general.py`).
   - Vista **`word`** (`words[].speaker` con interpolación/herencia determinista).
2. Aplica `core/normalizacion.py` idénticamente a referencia *gold* e hipótesis.
3. Calcula por clip: `WER`, `CER`, `entidades_ref/err`, `WDER_seg`, `cpWER_seg`, `delta_diar_seg`, `WDER_word`, `cpWER_word`, `delta_hablantes`, `tasa_frag_lt10`, `score_medio`, `avg_logprob_medio`.
4. Ejecuta bootstrap no paramétrico ($B = 10{.}000$) para métricas globales y por estrato (`A`, `B`), correlación de Spearman y recálculo de $n_B$ con $s_{\text{UCL}, 80\%}$.

---

## Postcondiciones y códigos de salida
- **`0` (éxito):** escribe `resultados_piloto.csv` y `resumen_piloto.json` conformes a `sdd/data-model.md`. Imprime tabla resumen en texto plano ASCII/UTF-8 sin emojis.
- **`1` (error de trazabilidad/esquema):** desacople de `sha256_manifest`, archivo de `CodeCursos` modificado sin `--permitir-obsoletos`, o JSON de anotación inválido.
- **`2` (piloto incompleto):** existen clips `"pendiente"` o `"en_progreso"` sin `--permitir-incompleto`.

