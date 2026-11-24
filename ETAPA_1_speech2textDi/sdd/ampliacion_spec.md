# SDD Breve — Ampliacion Anidada de la Muestra (Etapa 1: Medio +32 y Reserva Seguro +32)

- **Etapa:** `ETAPA_1_speech2textDi`
- **Base inmutable:** `muestreo/manifest_piloto.json` (`P001`..`P024`, semilla `20261119`)
- **Estado:** Aprobado en `[HUMAN GATE 1]` (2026-11-24)

---

## 1. Objetivo y alcance

Ampliar el piloto de 24 clips hacia el **nivel Medio (+32 clips -> 56 totales)** dejando pre-asignado en reserva el **nivel Seguro (+32 clips -> 88 totales)** en una unica corrida determinista, garantizando **cero solapamiento** entre los 88 clips y trazabilidad completa del linaje muestral.

### Invariantes de diseno
1. **Inmutabilidad del piloto:** `manifest_piloto.json` y los 24 clips `P001`..`P024` no se modifican ni se re-anotan.
2. **Prefijos por lote:**
   - Piloto: `P001`..`P024` (24 clips: `16 B + 8 A`)
   - Ampliacion Medio: `M001`..`M032` (32 clips: `16 B + 16 A`, es decir `+2 B + 2 A` por candidato)
   - Ampliacion Seguro (reserva): `S001`..`S032` (32 clips: `24 B + 8 A`, es decir `+3 B + 1 A` por candidato)
   - Validacion de `clip_id`: `^[PMS]\d{3}$`.
3. **Estrategia anti-solapamiento (semilla `20261124`):**
   - Cada candidato dispone de 10 entrevistas (`3` usadas en Piloto, `7` virgenes).
   - **Lote Medio (`4` clips/candidato):** se sortean sobre **4 de las 7 entrevistas virgenes** (`0` repeticiones con Piloto).
   - **Lote Seguro (`4` clips/candidato):** los primeros `3` clips usan las **3 entrevistas virgenes restantes** (completando `10/10` entrevistas por candidato = `80/80` en el corpus); el `4.o` clip por candidato (`8` clips en total) se sortea en la entrevista mas larga de ese candidato (`>= 58 min`) respetando una **zona de exclusion obligatoria** de `+-30,0 s` alrededor de cualquier clip previo en esa entrevista.
4. **Linaje muestral:** cada manifest ampliado incluye el bloque `linaje_muestreo` (cubierto por `sha256_manifest`) con `semilla_ampliacion`, `colchon_exclusion_s`, y `manifests_previos` (`archivo`, `sha256_manifest`, `n_clips`).
5. **Compatibilidad web (Streamlit Cloud):** `app/cargador_clips.py` y `app/streamlit_app.py` autodetectan el manifest correspondiente al ZIP subido por el usuario (comparando nombres de MP3 y `sha256_clip`) y ofrecen selector manual de lote en la barra lateral.
6. **Evaluacion consolidada:** `metricas/calcular_metricas.py` admite multiples pares `--manifest` / `--anotacion` para consolidar `Piloto + Medio` (56 clips) o `Piloto + Medio + Seguro` (88 clips), validando que no existan `clip_id` duplicados ni intervalos solapados.

---

## 2. Tareas atomicas

- [x] **A-01:** Actualizar `core/validacion_esquemas.py` (`^[PMS]\d{3}$` y validacion de `linaje_muestreo` opcional).
- [x] **A-02:** Implementar `muestreo/ampliar_muestra.py` reutilizando helpers de `core/io_diario.py` y `muestreo/muestrear.py`.
- [x] **A-03:** Actualizar `app/cargador_clips.py` y `app/streamlit_app.py` para multi-manifest y autodeteccion desde ZIP.
- [x] **A-04:** Actualizar `metricas/calcular_metricas.py` para aceptar multiples pares `--manifest` / `--anotacion`.
- [x] **A-05:** Ejecutar `ampliar_muestra.py` y `recortar_clips.py` generando `manifest_ampliacion_medio.json`, `manifest_ampliacion_seguro.json` y `muestreo/clips/clips_ampliacion_medio.zip`.
- [x] **A-06:** Agregar pruebas en `tests/test_ampliacion.py` (cero solapamiento entre los 88 clips, autodeteccion ZIP, consolidacion multi-lote) y ejecutar `pytest` + `AppTest`.
- [x] **A-07:** Hacer `git commit` y `git push` a `origin/main` (verificando que ningun `.mp3`/`.zip` quede rastreado).
