# Manual de Usuario — Etapa 1 (Piloto): ASR y Diarizacion Textual

Guia operativa paso a paso para ejecutar el muestreo, anotar los 24 clips en Streamlit (local o **Streamlit Community Cloud**), calcular metricas y generar el informe del piloto.

---

## 1. Preparar entorno local (una sola vez)

Desde la raiz del repositorio (`/home/jd/Escritorio/ValidaCandi`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r ETAPA_1_speech2textDi/requirements-dev.txt
```

Verifica que `ffmpeg` este instalado:

```bash
ffmpeg -version
```

---

## 2. Muestreo y recorte de los 24 clips del piloto

> Estos dos pasos leen `/home/jd/Escritorio/CodeCursos` en **modo solo lectura** y nunca modifican archivos en ese repositorio.

1. Generar `muestreo/manifest_piloto.json` (versionado en Git):
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
   *(Si necesitas regenerarlo, anade `--sobrescribir`.)*

2. Recortar los 24 MP3 y crear `muestreo/clips/clips_piloto.zip` (~11 MB, ignorado por `.gitignore`):
   ```bash
   python ETAPA_1_speech2textDi/muestreo/recortar_clips.py \
     --manifest ETAPA_1_speech2textDi/muestreo/manifest_piloto.json \
     --dir-clips ETAPA_1_speech2textDi/muestreo/clips \
     --zip-salida ETAPA_1_speech2textDi/muestreo/clips/clips_piloto.zip
   ```

3. Verificar integridad de los clips:
   ```bash
   python ETAPA_1_speech2textDi/muestreo/recortar_clips.py --solo-verificar
   ```

---

## 3. Ejecutar la app de anotacion

### Opcion A: En Streamlit Community Cloud (recomendado para anotar desde cualquier lugar)
1. Haz `git push` del repositorio `ValidaCandi` a GitHub (los archivos MP3 y `clips_piloto.zip` quedan automaticamente excluidos por `.gitignore`; solo sube `manifest_piloto.json` y el codigo).
2. En **Streamlit Community Cloud** crea una nueva app apuntando a:
   - **Main file path:** `ETAPA_1_speech2textDi/app/streamlit_app.py`
   - *(El archivo `ETAPA_1_speech2textDi/app/requirements.txt` se detecta automaticamente; contiene unicamente `streamlit`.)*
3. Carga de audios al abrir la app:
   - **Forma directa:** sube `ETAPA_1_speech2textDi/muestreo/clips/clips_piloto.zip` en el cargador de la barra lateral.
   - **Forma automatica (opcional):** si hospedas `clips_piloto.zip` en un dataset privado (p. ej. Hugging Face), configura en *App Settings -> Secrets*:
     ```toml
     CLIPS_ZIP_URL = "https://..."
     CLIPS_ZIP_TOKEN = "hf_..."
     ```

### Opcion B: En local
```bash
streamlit run ETAPA_1_speech2textDi/app/streamlit_app.py
```
La app detectara automaticamente los MP3 en `ETAPA_1_speech2textDi/muestreo/clips/`.

---

## 4. Flujo de trabajo del anotador

1. Escribe tu identificador en **Anotador** (barra lateral, p. ej. `jd`).
2. Escucha cada clip de 60 s usando `-5 s`, `+5 s` y control de velocidad (`0.75x`–`1.5x`).
3. En las **tarjetas por turno**:
   - Corrige el texto escuchado (numeros en digitos como `15%`, nombres propios y siglas oficiales, `[inaudible]` / `[solapado]` en linea si aplica).
   - **Si falto una division de hablante:** pulsa **Dividir** en la tarjeta y haz clic en la primera palabra donde entra la otra persona (`1 clic = 2 cuadros`, o `2 clics = 3 cuadros` si hubo una interrupcion al medio), revisa la vista previa por colores y pulsa **Aplicar division**. (Tambien puedes escribir `||` en el texto.)
   - **Si sobro una division:** pulsa **Unir con anterior** o cambia el desplegable a la etiqueta del turno previo.
   - Si el audio es solo musica/ruido, marca **No anotable** y elige el motivo.
4. Pulsa **Marcar completo y siguiente**.
5. Cada 3 clips (y al terminar los 24), pulsa **Exportar progreso JSON** en la barra lateral y guarda el archivo `anot_<anotador>_<fecha>_n024.json` dentro de `ETAPA_1_speech2textDi/gold/`.
   - *Respaldo de emergencia:* cada guardado copia tambien el progreso en `localStorage` del navegador (recuperable desde el desplegable *Respaldo en navegador* de la barra lateral).

---

## 5. Calcular metricas y generar el informe del piloto

Con el archivo exportado en `ETAPA_1_speech2textDi/gold/anot_<...>.json`:

1. Calcular `resultados_piloto.csv` y `resumen_piloto.json`:
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
   *(Para inspeccionar avances parciales antes de completar los 24 clips, agrega `--permitir-incompleto`.)*

2. Generar `reporte/informe_piloto.md`:
   ```bash
   python ETAPA_1_speech2textDi/reporte/generar_reporte.py \
     --csv ETAPA_1_speech2textDi/metricas/resultados_piloto.csv \
     --resumen ETAPA_1_speech2textDi/metricas/resumen_piloto.json \
     --salida ETAPA_1_speech2textDi/reporte/informe_piloto.md
   ```

---

## 6. Ejecutar pruebas unitarias

```bash
pytest ETAPA_1_speech2textDi/tests/ -v
```

