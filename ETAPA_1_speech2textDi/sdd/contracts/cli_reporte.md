# Contrato CLI — Generación del Informe del Piloto

Cubre `ETAPA_1_speech2textDi/reporte/generar_reporte.py`.

---

## Firma CLI

```bash
python ETAPA_1_speech2textDi/reporte/generar_reporte.py \
  --csv ETAPA_1_speech2textDi/metricas/resultados_piloto.csv \
  --resumen ETAPA_1_speech2textDi/metricas/resumen_piloto.json \
  --salida ETAPA_1_speech2textDi/reporte/informe_piloto.md
```

---

## Argumentos

| Bandera | Tipo | Requerido | Default | Descripción |
|:--------|:-----|:---------:|:--------|:------------|
| `--csv` | `Path` | Sí | — | Ruta a `resultados_piloto.csv` |
| `--resumen` | `Path` | Sí | — | Ruta a `resumen_piloto.json` |
| `--salida` | `Path` | No | `ETAPA_1_speech2textDi/reporte/informe_piloto.md` | Ruta del informe Markdown generado |

---

## Precondiciones
- Existen `--csv` y `--resumen` con esquemas válidos conforme a `sdd/data-model.md`.

---

## Contenido garantizado del informe (`reporte/informe_piloto.md`)
1. **Ficha técnica y trazabilidad:** `sha256_manifest`, archivo de anotación, versión de guía, estado de verificación de fuentes en `CodeCursos`, cobertura (`completos` vs. `no_anotables`) y tiempo de anotación (medio y total).
2. **Resultados primarios (global y por estrato A/B):** tabla con puntual e IC 95 % bootstrap para **WER**, **WDER (`segment`)**, **cpWER (`segment`)**, **$\Delta_{\text{diar}}$** y distribución de **$\Delta H$** (exacto / sobresegmentado / subsegmentado).
3. **Resultados secundarios y auditoría del pipeline:**
   - **CER** y **tasa de error en cifras/siglas/entidades**.
   - **Comparación directa `segment` vs. `word`:** tabla lado a lado mostrando si `merge_diarization()` de `general.py` mejora o degrada WDER/cpWER.
   - **Fragmentación `< 10` palabras:** proporción de texto potencialmente descartado por `fragmentador_oraciones.py`.
   - **Correlación de Spearman** (`score` y `avg_logprob` vs. WER).
4. **Desagregación exploratoria por candidato:** tabla con advertencia metodológica explícita de que $n = 3$ por candidato es exploratorio (enfocada en verificar la hipótesis de sobresegmentación en Keiko y Acuña).
5. **Peores 5 clips (análisis de casos):** tabla ordenada por WER y por `WDER_seg` para inspección cualitativa.
6. **Dimensionamiento de la muestra final ($E = \pm 3\text{ pp}$):** reporte de $s_B$, $s_{\text{UCL}, 80\%}$, $n_B$ recomendado, estimación de horas humanas y sección de cierre para registrar incidencias de la guía y la decisión de incorporar o excluir los 24 clips del piloto.

---

## Postcondiciones y códigos de salida
- **`0` (éxito):** escribe `informe_piloto.md` en español, tono neutral/académico, sin emojis en stdout.
- **`1` (error de entrada):** archivo faltante o campos requeridos ausentes en `resumen_piloto.json` / `resultados_piloto.csv`.

