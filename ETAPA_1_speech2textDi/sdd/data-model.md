# Modelo de Datos — Etapa 1 (Piloto): ASR y Diarización Textual

Este documento define de forma estricta los esquemas de los cuatro artefactos de datos del piloto de la Etapa 1. Todas las rutas relativas se resuelven respecto a `ETAPA_1_speech2textDi/`.

---

## 1. `muestreo/manifest_piloto.json`

Artefacto inmutable generado por `muestreo/muestrear.py` y completado con `sha256_clip` por `muestreo/recortar_clips.py`. **Se versiona en Git** (no contiene audio, solo metadatos, hashes y `precarga_ui`).

### Estructura JSON

```json
{
  "version_esquema": "1.0",
  "etapa": "ETAPA_1_speech2textDi",
  "fase": "piloto",
  "semilla": 20261119,
  "fecha_generacion": "2026-11-19T16:00:00-05:00",
  "fuente": {
    "repo_path": "/home/jd/Escritorio/CodeCursos",
    "dir_diario": "Resultados/Diario",
    "dir_audios": "Resultados/Audios",
    "n_entrevistas_marco": 80
  },
  "parametros": {
    "duracion_clip_s": 60.0,
    "ajuste_borde_max_s": 2.0,
    "offset_estrato_a_s": [15.0, 45.0],
    "clips_por_candidato_estrato_b": 2,
    "clips_por_candidato_estrato_a": 1,
    "formato_clip": {
      "codec": "mp3",
      "canales": 1,
      "frecuencia_hz": 16000,
      "bitrate_kbps": 64
    }
  },
  "clips": [
    {
      "clip_id": "P001",
      "orden_anotacion": 1,
      "entrevista": "10_1_keiko",
      "candidato_cid": 1,
      "candidato_slug": "1_keiko",
      "estrato": "B",
      "cambio_turno_ancla_s": null,
      "inicio_s": 1234.56,
      "fin_s": 1294.61,
      "duracion_s": 60.05,
      "sha256_wav": "64-hex-chars",
      "sha256_json": "64-hex-chars",
      "archivo_clip": "P001.mp3",
      "sha256_clip": "64-hex-chars-or-null-before-recorte",
      "precarga_ui": [
        {
          "turno_id": 1,
          "hablante": "H1",
          "texto": "Texto precargado del primer turno del clip."
        },
        {
          "turno_id": 2,
          "hablante": "H2",
          "texto": "Texto precargado del segundo turno del clip."
        }
      ]
    }
  ],
  "sha256_manifest": "64-hex-chars"
}
```

### Reglas e invariantes
- **`clips`**: exactamente 24 elementos en el piloto (16 `estrato == "B"`, 8 `estrato == "A"`).
- **`clip_id`**: único, patrón `^P\d{3}$` (`P001`..`P024`).
- **`orden_anotacion`**: permutación aleatoria reproducible (con la misma `semilla`) de `1..24`, para que el anotador **no** vea los clips agrupados por candidato ni por estrato.
- **`estrato`**: `"A"` o `"B"`. Nunca se renderiza en la UI.
- **`cambio_turno_ancla_s`**: `float` en `[45.0, duracion_entrevista - 45.0]` si `estrato == "A"`, `null` si `estrato == "B"`.
- **`entrevista`**: única dentro del piloto (3 entrevistas distintas por cada `candidato_cid` en `1..8`).
- **`precarga_ui`**: lista no vacía de turnos genéricos (`^H[1-9]\d*$`) ordenados cronológicamente; derivada de la vista `segment` (`segment["speaker"]`) del JSON fuente tras interpolar palabras sin timestamp.
- **`sha256_manifest`**: SHA-256 calculado sobre la serialización JSON canónica (`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`) del objeto manifest **excluyendo** los campos `"sha256_manifest"` y `"sha256_clip"` (de modo que el hash de identidad del diseño muestral permanezca estable al regenerar los MP3, mientras `"sha256_clip"` valida cada MP3 individualmente).

---

## 2. `gold/anot_{anotador}_{fecha}_n{NNN}.json`

Archivo de progreso y referencia *gold* exportado e importado por `app/streamlit_app.py`.

### Estructura JSON

```json
{
  "version_esquema": "1.0",
  "sha256_manifest": "64-hex-chars",
  "version_guia": "1.0",
  "version_app": "1.0",
  "anotador": "jd",
  "fecha_exportacion": "2026-11-20T18:30:00-05:00",
  "clips": {
    "P001": {
      "estado": "completo",
      "motivo_no_anotable": null,
      "notas": "",
      "turnos": [
        {
          "turno_id": 1,
          "hablante": "H1",
          "texto": "Señor candidato, ¿usted bajará el IGV?"
        },
        {
          "turno_id": 2,
          "hablante": "H2",
          "texto": "Sí, proponemos bajar el IGV al 15%."
        }
      ],
      "tiempo_anotacion_s": 318.4,
      "timestamp_ultima_edicion": "2026-11-20T18:24:12-05:00"
    },
    "P002": {
      "estado": "no_anotable",
      "motivo_no_anotable": "solo_musica",
      "notas": "Cortina musical de inicio del programa",
      "turnos": [],
      "tiempo_anotacion_s": 22.0,
      "timestamp_ultima_edicion": "2026-11-20T18:26:01-05:00"
    }
  }
}
```

### Reglas e invariantes
- **`sha256_manifest`**: debe coincidir exactamente con `manifest_piloto.json`. Si no coincide, tanto la app (al importar) como `calcular_metricas.py` rechazan el archivo.
- **`estado`**: enum cerrado `{"pendiente", "en_progreso", "completo", "no_anotable"}`.
- **`motivo_no_anotable`**: `null` cuando `estado != "no_anotable"`; enum `{"solo_musica", "solo_ruido", "inaudible_total", "otro"}` cuando `estado == "no_anotable"`.
- **`turnos`**:
  - Si `estado == "completo"`: lista no vacía; cada turno tiene `hablante` conforme a `^H[1-9]\d*$` y `texto.strip() != ""`.
  - Si `estado == "no_anotable"`: lista vacía `[]`.
- **`tiempo_anotacion_s`**: `float >= 0.0`, acumulado entre sesiones con tope de 900 s por intervalo inactivo.
- **Fusión lógica en evaluación:** si dos turnos consecutivos tienen el mismo `hablante`, el evaluador los concatena con un espacio al calcular métricas de diarización, sin requerir que el anotador los haya unido manualmente.

---

## 3. `metricas/resultados_piloto.csv`

Tabla con **exactamente 1 fila por clip** del manifest (24 filas en el piloto), codificación `utf-8`, separador `,`. Los clips con `estado == "no_anotable"` conservan sus metadatos y llevan vacío (`NaN`) en las columnas de métricas.

| Columna | Tipo | Descripción |
|:--------|:-----|:------------|
| `clip_id` | `str` | Identificador del clip (`P001`..`P024`) |
| `entrevista` | `str` | Nombre base (`10_1_keiko`) |
| `candidato_cid` | `int` | ID del candidato (`1..8`) |
| `candidato_slug` | `str` | Slug del candidato (`1_keiko`..`8_cerron`) |
| `estrato` | `str` | `"A"` o `"B"` |
| `estado` | `str` | `"completo"` o `"no_anotable"` |
| `motivo_no_anotable` | `str` | Vacío si es completo |
| `n_inaudible` | `int` | Conteo de marcas `[inaudible]` en la referencia |
| `n_solapado` | `int` | Conteo de marcas `[solapado]` en la referencia |
| `N_ref` | `int` | Palabras de referencia tras normalizar |
| `N_hip` | `int` | Palabras de hipótesis tras normalizar |
| `S` | `int` | Sustituciones (WER) |
| `D` | `int` | Borrados (WER) |
| `I` | `int` | Inserciones (WER) |
| `H` | `int` | Aciertos exactos (WER) |
| `WER` | `float` | `(S + D + I) / N_ref` |
| `CER` | `float` | Tasa de error a nivel de caracteres |
| `entidades_ref` | `int` | Cifras, siglas y nombres propios extraídos del *gold* |
| `entidades_err` | `int` | Tokens de entidad sustituidos o borrados en hipótesis |
| `tasa_err_entidades` | `float` | `entidades_err / entidades_ref` (`NaN` si `entidades_ref == 0`) |
| `n_hablantes_ref` | `int` | Hablantes distintos en el *gold* |
| `n_hablantes_hip_seg` | `int` | Hablantes distintos en vista `segment` (`general.py`) |
| `delta_hablantes_seg` | `int` | `n_hablantes_hip_seg - n_hablantes_ref` |
| `pares_alineados_seg` | `int` | `S + H` usados como denominador de WDER (`segment`) |
| `err_spk_seg` | `int` | Palabras alineadas con hablante equivocado (`segment`) |
| `WDER_seg` | `float` | `err_spk_seg / pares_alineados_seg` |
| `cpWER_errores_seg` | `int` | Suma de distancias de edición bajo permutación óptima (`segment`) |
| `cpWER_seg` | `float` | `cpWER_errores_seg / N_ref` |
| `delta_diar_seg` | `float` | `cpWER_seg - WER` |
| `n_hablantes_hip_word` | `int` | Hablantes distintos en vista `word` (`words[].speaker`) |
| `delta_hablantes_word` | `int` | `n_hablantes_hip_word - n_hablantes_ref` |
| `err_spk_word` | `int` | Palabras alineadas con hablante equivocado (`word`) |
| `WDER_word` | `float` | WDER sobre `words[].speaker` |
| `cpWER_errores_word` | `int` | Errores cpWER sobre `words[].speaker` |
| `cpWER_word` | `float` | cpWER sobre `words[].speaker` |
| `palabras_frag_lt10` | `int` | Palabras de hipótesis (`segment`) en turnos internos `< 10` palabras |
| `tasa_frag_lt10` | `float` | `palabras_frag_lt10 / N_hip` |
| `score_medio` | `float` | Media de `score` de palabras con `score` en el clip |
| `avg_logprob_medio` | `float` | Media de `avg_logprob` de segmentos que cubren el clip |
| `tiempo_anotacion_s` | `float` | Tiempo efectivo de anotación registrado por la app |

---

## 4. `metricas/resumen_piloto.json`

Resumen estadístico estructurado consumido por `reporte/generar_reporte.py`.

### Estructura JSON

```json
{
  "version_esquema": "1.0",
  "fecha_calculo": "2026-11-21T10:00:00-05:00",
  "trazabilidad": {
    "sha256_manifest": "64-hex-chars",
    "archivo_anotacion": "gold/anot_jd_2026-11-20_n024.json",
    "sha256_anotacion": "64-hex-chars",
    "version_guia": "1.0",
    "fuentes_validadas_ok": true,
    "semilla_bootstrap": 20261119,
    "n_bootstrap": 10000
  },
  "cobertura": {
    "n_total_manifest": 24,
    "n_completos": 24,
    "n_no_anotables": 0,
    "n_estrato_b_eval": 16,
    "n_estrato_a_eval": 8,
    "tiempo_medio_clip_s": 340.5,
    "tiempo_total_h": 2.27
  },
  "metricas_globales": {
    "WER": {"puntual": 0.085, "ic95": [0.061, 0.112]},
    "CER": {"puntual": 0.042, "ic95": [0.029, 0.058]},
    "tasa_err_entidades": {"puntual": 0.140, "ic95": [0.095, 0.192]},
    "WDER_seg": {"puntual": 0.071, "ic95": [0.040, 0.109]},
    "cpWER_seg": {"puntual": 0.148, "ic95": [0.102, 0.198]},
    "delta_diar_seg": {"puntual": 0.063, "ic95": [0.031, 0.099]},
    "WDER_word": {"puntual": 0.058, "ic95": [0.031, 0.091]},
    "cpWER_word": {"puntual": 0.132, "ic95": [0.089, 0.180]},
    "tasa_frag_lt10": {"puntual": 0.045, "ic95": [0.021, 0.074]}
  },
  "hablantes_seg": {
    "delta_medio": 0.42,
    "delta_mediana": 0.0,
    "pct_exacto": 0.583,
    "pct_sobresegmentado": 0.333,
    "pct_subsegmentado": 0.083
  },
  "por_estrato": {
    "B": { "...": "mismo esquema que metricas_globales + s_WER_clip" },
    "A": { "...": "mismo esquema que metricas_globales + s_WER_clip" }
  },
  "por_candidato_exploratorio": {
    "1_keiko": { "n_eval": 3, "WER": 0.09, "WDER_seg": 0.11, "cpWER_seg": 0.19, "delta_hablantes_medio": 1.33 }
  },
  "correlacion_confianza": {
    "spearman_score_vs_WER": {"rho": -0.62, "p_value": 0.0012},
    "spearman_logprob_vs_WER": {"rho": -0.58, "p_value": 0.0029}
  },
  "dimensionamiento_muestra_final": {
    "margen_objetivo_E": 0.03,
    "n_B_piloto": 16,
    "s_B_WER_clip": 0.072,
    "s_UCL_80": 0.089,
    "n_B_recomendado": 34,
    "horas_anotacion_estimadas_adicionales": 1.7
  }
}
```

