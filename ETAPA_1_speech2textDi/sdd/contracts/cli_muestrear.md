# Contrato CLI — Muestreo y Recorte de Clips

Cubre los dos scripts locales de preparación del piloto en `ETAPA_1_speech2textDi/muestreo/`. Ambos operan en **estricto modo solo lectura** sobre `/home/jd/Escritorio/CodeCursos`.

---

## 1. `muestreo/muestrear.py`

### Propósito
Muestrear de forma determinista los 24 clips del piloto (16 Estrato B + 8 Estrato A), verificar integridad 1 a 1 de WAV/JSON en `CodeCursos`, interpolar palabras sin timestamp, generar `precarga_ui` y escribir `muestreo/manifest_piloto.json`.

### Firma CLI

```bash
python ETAPA_1_speech2textDi/muestreo/muestrear.py \
  --repo-fuente /home/jd/Escritorio/CodeCursos \
  --salida ETAPA_1_speech2textDi/muestreo/manifest_piloto.json \
  --semilla 20261119 \
  --clips-b 2 \
  --clips-a 1 \
  --duracion 60.0 \
  --ajuste-borde-max 2.0
```

### Argumentos

| Bandera | Tipo | Requerido | Default | Descripción |
|:--------|:-----|:---------:|:--------|:------------|
| `--repo-fuente` | `Path` | No | `/home/jd/Escritorio/CodeCursos` | Ruta raíz de solo lectura del pipeline fuente |
| `--salida` | `Path` | No | `ETAPA_1_speech2textDi/muestreo/manifest_piloto.json` | Ruta de salida del manifest |
| `--semilla` | `int` | No | `20261119` | Semilla fija para el generador `random` / `numpy` |
| `--clips-b` | `int` | No | `2` | Clips aleatorios (Estrato B) por candidato |
| `--clips-a` | `int` | No | `1` | Clips anclados a cambio de turno (Estrato A) por candidato |
| `--duracion` | `float` | No | `60.0` | Duración nominal del clip en segundos |
| `--ajuste-borde-max` | `float` | No | `2.0` | Ajuste máximo de bordes al hueco entre palabras (segundos) |
| `--sobrescribir` | `flag` | No | `False` | Permite sobrescribir un manifest ya existente |

### Precondiciones
- Existen `<repo-fuente>/Resultados/Audios/*.wav` y `<repo-fuente>/Resultados/Diario/*.json` con correspondencia 1 a 1.
- Cada candidato dispone de al menos `clips_b + clips_a` entrevistas distintas válidas (en el piloto, 10 >= 3).
- `--salida` no existe, o se pasó `--sobrescribir`.

### Postcondiciones y códigos de salida
- **`0` (éxito):** escribe `manifest_piloto.json` válido según `sdd/data-model.md`, con `sha256_wav`, `sha256_json`, `precarga_ui` y `sha256_manifest` calculados; `sha256_clip` inicializado en `null`. Imprime resumen en texto plano ASCII/UTF-8 sin emojis.
- **`1` (error de validación de insumos):** faltan WAV/JSON emparejados, JSON corrupto o candidato sin suficientes entrevistas. No escribe archivo parcial.
- **`2` (error de argumentos/conflicto):** archivo de salida ya existe sin `--sobrescribir` o parámetros fuera de rango.

---

## 2. `muestreo/recortar_clips.py`

### Propósito
Recortar los 24 clips desde los WAV fuente usando `ffmpeg`, actualizar `sha256_clip` en `manifest_piloto.json` y empaquetar `clips_piloto.zip` (~12 MB) para subir a Streamlit Community Cloud.

### Firma CLI

```bash
python ETAPA_1_speech2textDi/muestreo/recortar_clips.py \
  --manifest ETAPA_1_speech2textDi/muestreo/manifest_piloto.json \
  --dir-clips ETAPA_1_speech2textDi/muestreo/clips \
  --zip-salida ETAPA_1_speech2textDi/muestreo/clips/clips_piloto.zip
```

### Argumentos

| Bandera | Tipo | Requerido | Default | Descripción |
|:--------|:-----|:---------:|:--------|:------------|
| `--manifest` | `Path` | No | `ETAPA_1_speech2textDi/muestreo/manifest_piloto.json` | Manifest generado por `muestrear.py` |
| `--repo-fuente` | `Path` | No | *(leído del manifest)* | Override opcional de la ruta a `CodeCursos` |
| `--dir-clips` | `Path` | No | `ETAPA_1_speech2textDi/muestreo/clips` | Directorio local (ignorado por Git) para los MP3 |
| `--zip-salida` | `Path` | No | `<dir-clips>/clips_piloto.zip` | Paquete ZIP con los 24 MP3 |
| `--solo-verificar` | `flag` | No | `False` | Verifica que los MP3 existentes coincidan con `sha256_clip` sin recortar |

### Precondiciones
- `ffmpeg` disponible en `PATH`.
- `manifest_piloto.json` válido y WAVs fuente con `sha256_wav` idéntico al registrado en el manifest.

### Postcondiciones y códigos de salida
- **`0` (éxito):** genera los 24 MP3 (`mono`, `16 kHz`, `64 kbps`, `-map_metadata -1`), actualiza `sha256_clip` en `manifest_piloto.json` (manteniendo intacto `sha256_manifest`), crea `clips_piloto.zip` e imprime tamaño total en MB en texto plano sin emojis.
- **`1` (error de integridad):** `sha256_wav` de algún archivo en `CodeCursos` cambió respecto al manifest.
- **`2` (error de herramienta):** `ffmpeg` no encontrado o falla en la codificación de algún clip.

