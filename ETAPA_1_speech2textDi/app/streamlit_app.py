"""Aplicacion de anotacion humana (Streamlit) para el piloto de la Etapa 1."""

from __future__ import annotations

import base64
import copy
from datetime import datetime, timezone
import html as html_lib
import json
from pathlib import Path
import sys
import tempfile
import time
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

_ETAPA_DIR = Path(__file__).resolve().parents[1]
if str(_ETAPA_DIR) not in sys.path:
    sys.path.insert(0, str(_ETAPA_DIR))

from app.cargador_clips import (
    DIR_CLIPS_LOCAL_DEFAULT,
    cargar_manifest_piloto,
    descargar_clips_desde_url,
    extraer_zip_y_verificar,
    verificar_directorio_clips,
)
from app.estado_anotacion import (
    _sugerir_hablante_division,
    acumular_tiempo_clip,
    clips_ordenados_para_ui,
    construir_payload_exportacion,
    crear_estado_inicial,
    dividir_turno_en_indices,
    dividir_turno_en_marcador,
    eliminar_turno,
    importar_y_fusionar_anotacion,
    opciones_hablante_para_clip,
    previsualizar_division_por_indices,
    renumerar_turnos,
    siguiente_clip_pendiente_idx,
    unir_con_anterior,
    validar_clip_para_completar,
)

VERSION_GUIA = "1.0"
VERSION_APP = "1.0"

MOTIVOS_ETIQUETAS = {
    "solo_musica": "Solo musica o cortina del programa",
    "solo_ruido": "Solo ruido / silencio sin habla",
    "inaudible_total": "Audio completamente inaudible",
    "otro": "Otro motivo (indicar en notas)",
}


@st.cache_resource
def _obtener_manifest_cached() -> dict[str, Any]:
    return cargar_manifest_piloto()


@st.cache_resource
def _descargar_clips_desde_secrets(url: str, token: str, sha_manifest: str) -> tuple[str | None, list[str]]:
    manifest = _obtener_manifest_cached()
    dir_cache = Path(tempfile.gettempdir()) / "validacandi_clips" / sha_manifest[:16]
    ok, errores = descargar_clips_desde_url(url, token or None, manifest, dir_cache)
    return (str(dir_cache) if ok else None), errores


def _render_reproductor_audio(ruta_mp3: Path, clip_id: str) -> None:
    """Renderiza un reproductor HTML5 compacto con controles -5s, +5s y velocidad."""
    audio_b64 = base64.b64encode(ruta_mp3.read_bytes()).decode("ascii")
    html = f"""
    <div style="border:1px solid #d0d7de;border-radius:8px;padding:10px 14px;background:#f8fafc;">
      <audio id="player_{clip_id}" controls style="width:100%;height:38px;">
        <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mpeg" />
      </audio>
      <div style="display:flex;gap:8px;align-items:center;margin-top:8px;flex-wrap:wrap;font-family:sans-serif;font-size:13px;">
        <button type="button" onclick="const a=document.getElementById('player_{clip_id}');a.currentTime=Math.max(0,a.currentTime-5);" style="padding:4px 10px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:#0f172a;cursor:pointer;">-5 s</button>
        <button type="button" onclick="const a=document.getElementById('player_{clip_id}');a.currentTime=Math.min(a.duration||65,a.currentTime+5);" style="padding:4px 10px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:#0f172a;cursor:pointer;">+5 s</button>
        <span style="margin-left:8px;color:#475569;">Velocidad:</span>
        <button type="button" onclick="document.getElementById('player_{clip_id}').playbackRate=0.75;" style="padding:4px 8px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:#0f172a;cursor:pointer;">0.75x</button>
        <button type="button" onclick="document.getElementById('player_{clip_id}').playbackRate=1.0;" style="padding:4px 8px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:#0f172a;cursor:pointer;">1.0x</button>
        <button type="button" onclick="document.getElementById('player_{clip_id}').playbackRate=1.25;" style="padding:4px 8px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:#0f172a;cursor:pointer;">1.25x</button>
        <button type="button" onclick="document.getElementById('player_{clip_id}').playbackRate=1.5;" style="padding:4px 8px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:#0f172a;cursor:pointer;">1.5x</button>
      </div>
    </div>
    """
    components.html(html, height=106)


def _sincronizar_local_storage(sha_manifest: str, payload_json: str) -> None:
    """Guarda respaldo automatico en localStorage del navegador sin bloquear la UI."""
    key = f"validacandi_etapa1_{sha_manifest[:16]}"
    payload_seguro = json.dumps(payload_json)
    js = f"""
    <script>
      try {{
        window.localStorage.setItem({json.dumps(key)}, {payload_seguro});
      }} catch (e) {{}}
    </script>
    """
    components.html(js, height=0)


def _render_recuperacion_local_storage(sha_manifest: str) -> None:
    """Boton pure-JS para descargar el ultimo respaldo guardado en localStorage."""
    key = f"validacandi_etapa1_{sha_manifest[:16]}"
    html = f"""
    <div style="font-family:sans-serif;font-size:12px;">
      <button type="button" onclick="
        const raw = window.localStorage.getItem({json.dumps(key)});
        if (!raw) {{ alert('No hay respaldo guardado en este navegador para este manifest.'); return; }}
        const blob = new Blob([raw], {{type: 'application/json'}});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'respaldo_localstorage_{sha_manifest[:8]}.json';
        a.click();
        URL.revokeObjectURL(url);
      " style="width:100%;padding:6px 10px;border:1px solid #cbd5e1;border-radius:6px;background:#f8fafc;color:#0f172a;cursor:pointer;font-size:12px;">
        Descargar respaldo localStorage
      </button>
    </div>
    """
    components.html(html, height=42)


def _iniciar_session_state(manifest: dict[str, Any]) -> None:
    sha = manifest["sha256_manifest"]
    if st.session_state.get("sha256_manifest") == sha:
        return

    st.session_state["sha256_manifest"] = sha
    st.session_state["anotador"] = st.session_state.get("anotador", "jd")
    st.session_state["clips_estado"] = crear_estado_inicial(manifest)
    st.session_state["clip_idx"] = 0
    st.session_state["t_inicio_clip"] = time.monotonic()
    st.session_state["undo_stacks"] = {}
    st.session_state["completados_desde_export"] = 0
    st.session_state["dir_clips_activo"] = None


def _registrar_undo(cid: str, turnos: list[dict[str, Any]]) -> None:
    pilas = st.session_state["undo_stacks"]
    pila = pilas.setdefault(cid, [])
    pila.append(copy.deepcopy(turnos))
    if len(pila) > 25:
        pila.pop(0)


def _aplicar_tiempo_actual(cid: str) -> None:
    t0 = st.session_state.get("t_inicio_clip")
    if t0 is not None:
        ahora = time.monotonic()
        acumular_tiempo_clip(st.session_state["clips_estado"][cid], ahora - t0)
        st.session_state["t_inicio_clip"] = ahora


def _cambiar_clip(nuevo_idx: int, cid_actual: str) -> None:
    _aplicar_tiempo_actual(cid_actual)
    st.session_state["clip_idx"] = nuevo_idx
    st.session_state["t_inicio_clip"] = time.monotonic()


def _rev_clip(cid: str) -> int:
    return int(st.session_state.get(f"rev_{cid}", 0))


def _sincronizar_textos_widgets(cid: str, turnos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lee el valor vigente en widgets de tarjetas antes de acciones de guardar/dividir."""
    rev = _rev_clip(cid)
    actualizados: list[dict[str, Any]] = []
    for i, t in enumerate(turnos):
        key_hab = f"hab_{cid}_{rev}_{i}"
        key_txt = f"txt_{cid}_{rev}_{i}"
        hab = st.session_state.get(key_hab, t["hablante"])
        txt = st.session_state.get(key_txt, t["texto"])
        actualizados.append({"turno_id": i + 1, "hablante": hab, "texto": txt})
    return actualizados


def _limpiar_widgets_clip(cid: str) -> None:
    prefijos = (
        f"hab_{cid}_",
        f"txt_{cid}_",
        f"split_pills_{cid}_",
        f"split_abierto_{cid}_",
    )
    for k in list(st.session_state.keys()):
        if any(k.startswith(p) for p in prefijos):
            del st.session_state[k]
    st.session_state[f"rev_{cid}"] = _rev_clip(cid) + 1


def _render_guia_anotacion() -> None:
    with st.expander("Guia rapida de anotacion (v1.0)", expanded=False):
        st.markdown(
            """
1. **Corrige el texto directamente** para que refleje lo que se dijo en el audio.
2. **Numeros en digitos** (`15%`, `2026`, `3 millones`).
3. **No agregues muletillas** puramente vocalicas (`eh`, `mmm`, `ah`).
4. **Nombres propios y siglas:** ortografia oficial (`ONPE`, `JNJ`, `BCRP`, `IGV`). Si dudas de un nombre, anade `?` al final.
5. **Ininteligible:** escribe `[inaudible]` donde corresponda (no adivines).
6. **Habla solapada:** si no se entiende por cruce de voces, escribe `[solapado]`.
7. **Etiquetas de hablante (`H1`, `H2`...):** son locales a cada clip (cada clip empieza de cero en `H1`). No intentes identificar quien es el candidato.
8. **Interjecciones breves de apoyo** (`aja`, `claro` sin quitar la palabra) no generan turno aparte.
9. **Para dividir un turno visualmente:** pulsa **Dividir** y haz clic en la(s) palabra(s) donde cambia el hablante (1 clic = 2 cuadros; 2 clics = 3 cuadros si alguien interrumpio a la mitad). Tambien puedes escribir `||` en el texto.
10. **Para unir un falso corte:** pulsa **Unir con anterior** o selecciona la misma etiqueta `H1` del turno anterior.
"""
        )


def _resolver_directorio_clips(manifest: dict[str, Any]) -> Path | None:
    """Resuelve los MP3 desde local, st.secrets o subida manual de ZIP."""
    dir_actual = st.session_state.get("dir_clips_activo")
    if dir_actual:
        ok, _ = verificar_directorio_clips(manifest, Path(dir_actual))
        if ok:
            return Path(dir_actual)

    # 1. Entorno local (si existe muestreo/clips validado)
    if DIR_CLIPS_LOCAL_DEFAULT.is_dir():
        ok_local, _ = verificar_directorio_clips(manifest, DIR_CLIPS_LOCAL_DEFAULT)
        if ok_local:
            st.session_state["dir_clips_activo"] = str(DIR_CLIPS_LOCAL_DEFAULT)
            return DIR_CLIPS_LOCAL_DEFAULT

    # 2. Configuracion via st.secrets en Streamlit Community Cloud
    url_secret = ""
    token_secret = ""
    try:
        url_secret = str(st.secrets.get("CLIPS_ZIP_URL", "")).strip()
        token_secret = str(st.secrets.get("CLIPS_ZIP_TOKEN", "")).strip()
    except Exception:
        pass

    if url_secret:
        dir_str, errores = _descargar_clips_desde_secrets(
            url_secret, token_secret, manifest["sha256_manifest"]
        )
        if dir_str:
            st.session_state["dir_clips_activo"] = dir_str
            return Path(dir_str)
        st.sidebar.error("Error cargando clips desde st.secrets:\n" + "\n".join(errores[:5]))

    # 3. Subida manual de clips_piloto.zip
    st.sidebar.subheader("Cargar audio del piloto")
    archivo_zip = st.sidebar.file_uploader(
        "Sube clips_piloto.zip (~12 MB)",
        type=["zip"],
        help="Los audios no se guardan en Git; se verifican por SHA-256 en sesion.",
    )
    if archivo_zip is not None:
        dir_tmp = Path(tempfile.gettempdir()) / "validacandi_clips" / manifest["sha256_manifest"][:16]
        ok_zip, errores_zip = extraer_zip_y_verificar(archivo_zip.getvalue(), manifest, dir_tmp)
        if ok_zip:
            st.session_state["dir_clips_activo"] = str(dir_tmp)
            st.sidebar.success("24 clips verificados por SHA-256.")
            return dir_tmp
        st.sidebar.error("El ZIP no coincide con el manifest:\n" + "\n".join(errores_zip[:6]))

    return None


@st.fragment
def _render_editor_tarjetas(
    manifest: dict[str, Any],
    clips_lista: list[dict[str, Any]],
    clip_idx: int,
) -> None:
    """Fragmento aislado para editar tarjetas sin reiniciar el reproductor de audio."""
    clip_meta = clips_lista[clip_idx]
    cid = clip_meta["clip_id"]
    clips_estado = st.session_state["clips_estado"]
    entrada = clips_estado[cid]

    st.markdown(f"### Turnos del clip `{cid}`")

    es_no_anotable = st.checkbox(
        "Marcar este clip como no anotable (solo musica, ruido o ininteligible)",
        value=(entrada["estado"] == "no_anotable"),
        key=f"chk_na_{cid}",
    )

    if es_no_anotable:
        motivo_actual = entrada.get("motivo_no_anotable") or "solo_musica"
        motivos_keys = list(MOTIVOS_ETIQUETAS.keys())
        motivo = st.selectbox(
            "Motivo",
            options=motivos_keys,
            index=motivos_keys.index(motivo_actual) if motivo_actual in motivos_keys else 0,
            format_func=lambda k: MOTIVOS_ETIQUETAS[k],
            key=f"motivo_na_{cid}",
        )
        notas = st.text_input("Notas opcionales", value=entrada.get("notas", ""), key=f"notas_{cid}")
        entrada["estado"] = "no_anotable"
        entrada["motivo_no_anotable"] = motivo
        entrada["notas"] = notas

        col_prev, col_save = st.columns([1, 2])
        with col_prev:
            if clip_idx > 0 and st.button("Anterior", key=f"prev_na_{cid}", use_container_width=True):
                _cambiar_clip(clip_idx - 1, cid)
                st.rerun()
        with col_save:
            if st.button("Confirmar no anotable y siguiente", type="primary", key=f"ok_na_{cid}", use_container_width=True):
                _aplicar_tiempo_actual(cid)
                entrada["turnos"] = []
                entrada["timestamp_ultima_edicion"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
                st.session_state["completados_desde_export"] += 1
                prox = siguiente_clip_pendiente_idx(clips_lista, clips_estado, clip_idx + 1)
                st.session_state["clip_idx"] = prox
                st.session_state["t_inicio_clip"] = time.monotonic()
                st.rerun()
        return

    # Si venia de no_anotable, restaurar precarga
    if entrada["estado"] == "no_anotable":
        entrada["estado"] = "en_progreso"
        entrada["motivo_no_anotable"] = None
        if not entrada["turnos"]:
            entrada["turnos"] = copy.deepcopy(clip_meta["precarga_ui"])
            _limpiar_widgets_clip(cid)

    turnos = entrada["turnos"]
    hablantes_unicos = list(dict.fromkeys(t["hablante"] for t in turnos))

    def _cb_undo() -> None:
        pila_cb = st.session_state["undo_stacks"].get(cid, [])
        if pila_cb:
            entrada["turnos"] = pila_cb.pop()
            _limpiar_widgets_clip(cid)

    def _cb_reset() -> None:
        _registrar_undo(cid, _sincronizar_textos_widgets(cid, turnos))
        entrada["turnos"] = copy.deepcopy(clip_meta["precarga_ui"])
        _limpiar_widgets_clip(cid)

    def _cb_toggle_split(idx_t: int) -> None:
        sk = f"split_abierto_{cid}_{idx_t}"
        st.session_state[sk] = not bool(st.session_state.get(sk, False))

    def _cb_join(idx_t: int) -> None:
        sinc = _sincronizar_textos_widgets(cid, turnos)
        _registrar_undo(cid, sinc)
        entrada["turnos"] = unir_con_anterior(sinc, idx_t)
        entrada["estado"] = "en_progreso"
        _limpiar_widgets_clip(cid)

    def _cb_delete(idx_t: int) -> None:
        sinc = _sincronizar_textos_widgets(cid, turnos)
        _registrar_undo(cid, sinc)
        entrada["turnos"] = eliminar_turno(sinc, idx_t)
        entrada["estado"] = "en_progreso"
        _limpiar_widgets_clip(cid)

    def _cb_apply_indices(idx_t: int, cortes_idx: list[int]) -> None:
        sinc = _sincronizar_textos_widgets(cid, turnos)
        _registrar_undo(cid, sinc)
        entrada["turnos"] = dividir_turno_en_indices(sinc, idx_t, cortes_idx)
        entrada["estado"] = "en_progreso"
        _limpiar_widgets_clip(cid)

    def _cb_cancel_split(idx_t: int) -> None:
        st.session_state[f"split_abierto_{cid}_{idx_t}"] = False

    col_info, col_undo, col_reset = st.columns([3, 1, 1])
    with col_info:
        st.caption(
            f"Turnos: {len(turnos)} | Hablantes en el clip: {', '.join(hablantes_unicos)} | "
            f"Tiempo acumulado: {entrada['tiempo_anotacion_s']:.0f} s"
        )
    with col_undo:
        pila = st.session_state["undo_stacks"].get(cid, [])
        st.button(
            "Deshacer",
            disabled=(len(pila) == 0),
            key=f"undo_{cid}",
            use_container_width=True,
            on_click=_cb_undo,
        )
    with col_reset:
        st.button(
            "Restaurar precarga",
            key=f"reset_{cid}",
            use_container_width=True,
            on_click=_cb_reset,
        )

    opciones_h = opciones_hablante_para_clip(turnos)
    rev = _rev_clip(cid)

    for i, turno in enumerate(turnos):
        with st.container(border=True):
            split_key = f"split_abierto_{cid}_{i}"
            split_abierto = bool(st.session_state.get(split_key, False))

            c_num, c_spk, c_split_btn, c_join, c_del = st.columns([1.0, 1.3, 1.5, 1.7, 1.0])
            with c_num:
                st.markdown(f"**Turno {i + 1}**")
            with c_spk:
                hab_actual = turno["hablante"]
                idx_h = opciones_h.index(hab_actual) if hab_actual in opciones_h else 0
                nuevo_h = st.selectbox(
                    "Hablante",
                    options=opciones_h,
                    index=idx_h,
                    key=f"hab_{cid}_{rev}_{i}",
                    label_visibility="collapsed",
                )
                if nuevo_h != hab_actual:
                    turno["hablante"] = nuevo_h
                    entrada["estado"] = "en_progreso"
            with c_split_btn:
                etiqueta_btn = "Cerrar division" if split_abierto else "Dividir"
                st.button(
                    etiqueta_btn,
                    key=f"toggle_split_{cid}_{i}",
                    use_container_width=True,
                    type="primary" if split_abierto else "secondary",
                    on_click=_cb_toggle_split,
                    args=(i,),
                )
            with c_join:
                st.button(
                    "Unir con anterior",
                    disabled=(i == 0),
                    key=f"join_{cid}_{i}",
                    use_container_width=True,
                    on_click=_cb_join,
                    args=(i,),
                )
            with c_del:
                st.button(
                    "Eliminar",
                    disabled=(len(turnos) <= 1),
                    key=f"del_{cid}_{i}",
                    use_container_width=True,
                    on_click=_cb_delete,
                    args=(i,),
                )

            altura = max(78, min(320, 48 + (len(turno["texto"]) // 75) * 24))
            nuevo_txt = st.text_area(
                f"Texto turno {i + 1}",
                value=turno["texto"],
                height=altura,
                key=f"txt_{cid}_{rev}_{i}",
                label_visibility="collapsed",
            )
            if nuevo_txt != turno["texto"]:
                turno["texto"] = nuevo_txt
                entrada["estado"] = "en_progreso"

            # Acceso directo rapido si el usuario escribio '||' en el texto
            if "||" in nuevo_txt and not split_abierto:
                if st.button("Aplicar corte rapido en ||", key=f"quick_mk_{cid}_{i}", type="primary"):
                    sinc = _sincronizar_textos_widgets(cid, turnos)
                    try:
                        dividido = dividir_turno_en_marcador(sinc, i, marcador="||")
                    except ValueError as exc:
                        st.warning(str(exc))
                    else:
                        _registrar_undo(cid, sinc)
                        entrada["turnos"] = dividido
                        entrada["estado"] = "en_progreso"
                        _limpiar_widgets_clip(cid)
                        st.rerun()

            # Panel visual interactivo para dividir en 2, 3 o mas cuadros
            palabras = nuevo_txt.split()
            if split_abierto:
                with st.container(border=True):
                    if "||" in nuevo_txt:
                        if st.button(
                            "Dividir usando los marcadores ||",
                            key=f"split_mk_{cid}_{i}",
                            use_container_width=True,
                        ):
                            sinc = _sincronizar_textos_widgets(cid, turnos)
                            try:
                                dividido = dividir_turno_en_marcador(sinc, i, marcador="||")
                            except ValueError as exc:
                                st.warning(str(exc))
                            else:
                                _registrar_undo(cid, sinc)
                                entrada["turnos"] = dividido
                                entrada["estado"] = "en_progreso"
                                _limpiar_widgets_clip(cid)
                                st.rerun()

                    if len(palabras) < 2:
                        st.info("Se necesitan al menos 2 palabras para dividir este turno.")
                    else:
                        st.markdown(
                            "**Division visual:** haz clic en la primera palabra donde empieza cada cuadro nuevo "
                            "*(1 clic = divide en 2 cuadros; 2 clics = divide en 3 cuadros)*."
                        )
                        seleccion = st.pills(
                            "Palabras de corte",
                            options=list(range(len(palabras))),
                            format_func=lambda k, p=palabras: p[k],
                            selection_mode="multi",
                            key=f"split_pills_{cid}_{i}",
                            label_visibility="collapsed",
                        )
                        cortes = sorted({int(k) for k in (seleccion or []) if 0 < int(k) < len(palabras)})
                        if seleccion and 0 in seleccion and not cortes:
                            st.caption("La primera palabra no inicia un corte nuevo; selecciona donde cambia el hablante.")

                        hab_alt = _sugerir_hablante_division(turnos, turno["hablante"])
                        bloques_prev = previsualizar_division_por_indices(
                            nuevo_txt, turno["hablante"], hab_alt, cortes
                        )
                        if len(bloques_prev) >= 2:
                            st.caption(f"Vista previa ({len(bloques_prev)} cuadros nuevos):")
                            paleta = [
                                "rgba(59, 130, 246, 0.16)",
                                "rgba(245, 158, 11, 0.18)",
                                "rgba(16, 185, 129, 0.16)",
                                "rgba(236, 72, 153, 0.16)",
                            ]
                            borde_pal = ["#3b82f6", "#f59e0b", "#10b981", "#ec4899"]
                            for idx_b, blk in enumerate(bloques_prev):
                                bg = paleta[idx_b % len(paleta)]
                                bd = borde_pal[idx_b % len(borde_pal)]
                                st.markdown(
                                    f"<div style='background:{bg};border-left:4px solid {bd};color:inherit;"
                                    f"padding:8px 12px;border-radius:6px;margin-bottom:6px;font-size:14px;line-height:1.45;'>"
                                    f"<strong>Cuadro {idx_b + 1} ({html_lib.escape(blk['hablante'])}):</strong> "
                                    f"{html_lib.escape(blk['texto'])}</div>",
                                    unsafe_allow_html=True,
                                )

                        c_ap, c_can = st.columns([2, 1])
                        with c_ap:
                            n_res = len(bloques_prev) if len(bloques_prev) >= 2 else 0
                            lbl_ap = f"Aplicar division ({n_res} cuadros)" if n_res else "Selecciona al menos 1 palabra de corte"
                            st.button(
                                lbl_ap,
                                disabled=(n_res < 2),
                                type="primary",
                                key=f"apply_split_{cid}_{i}",
                                use_container_width=True,
                                on_click=_cb_apply_indices,
                                args=(i, cortes),
                            )
                        with c_can:
                            st.button(
                                "Cancelar",
                                key=f"cancel_split_{cid}_{i}",
                                use_container_width=True,
                                on_click=_cb_cancel_split,
                                args=(i,),
                            )

    notas_val = st.text_input("Notas opcionales del clip", value=entrada.get("notas", ""), key=f"notas_{cid}")
    entrada["notas"] = notas_val

    col_prev, col_draft, col_next = st.columns([1, 1.5, 2.2])
    with col_prev:
        if clip_idx > 0 and st.button("Anterior", key=f"prev_{cid}", use_container_width=True):
            sinc = _sincronizar_textos_widgets(cid, turnos)
            entrada["turnos"] = renumerar_turnos(sinc)
            _cambiar_clip(clip_idx - 1, cid)
            st.rerun()
    with col_draft:
        if st.button("Guardar borrador", key=f"draft_{cid}", use_container_width=True):
            sinc = _sincronizar_textos_widgets(cid, turnos)
            entrada["turnos"] = renumerar_turnos(sinc)
            if entrada["estado"] == "pendiente":
                entrada["estado"] = "en_progreso"
            _aplicar_tiempo_actual(cid)
            entrada["timestamp_ultima_edicion"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            _, payload_str = construir_payload_exportacion(
                manifest, st.session_state["anotador"], clips_estado, VERSION_GUIA, VERSION_APP
            )
            _sincronizar_local_storage(manifest["sha256_manifest"], payload_str)
            st.success("Borrador guardado en sesion y respaldo local.")
    with col_next:
        if st.button("Marcar completo y siguiente", type="primary", key=f"done_{cid}", use_container_width=True):
            sinc = _sincronizar_textos_widgets(cid, turnos)
            ok_val, msg_val = validar_clip_para_completar("completo", None, sinc)
            if not ok_val:
                st.error(msg_val)
            else:
                turnos_limpios = [t for t in sinc if str(t["texto"]).strip()]
                entrada["turnos"] = renumerar_turnos(turnos_limpios)
                entrada["estado"] = "completo"
                entrada["motivo_no_anotable"] = None
                _aplicar_tiempo_actual(cid)
                entrada["timestamp_ultima_edicion"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
                st.session_state["completados_desde_export"] += 1

                _, payload_str = construir_payload_exportacion(
                    manifest, st.session_state["anotador"], clips_estado, VERSION_GUIA, VERSION_APP
                )
                _sincronizar_local_storage(manifest["sha256_manifest"], payload_str)

                prox = siguiente_clip_pendiente_idx(clips_lista, clips_estado, clip_idx + 1)
                st.session_state["clip_idx"] = prox
                st.session_state["t_inicio_clip"] = time.monotonic()
                st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="ValidaCandi - Etapa 1 (Piloto)",
        layout="wide",
    )

    try:
        manifest = _obtener_manifest_cached()
    except Exception as exc:
        st.error(f"No se pudo cargar manifest_piloto.json: {exc}")
        st.stop()

    _iniciar_session_state(manifest)
    clips_lista = clips_ordenados_para_ui(manifest)
    clips_estado = st.session_state["clips_estado"]

    # Sidebar: anotador, carga de clips, progreso y exportar/importar
    st.sidebar.title("ValidaCandi | Etapa 1")
    st.session_state["anotador"] = st.sidebar.text_input(
        "Anotador", value=st.session_state["anotador"]
    )

    dir_clips = _resolver_directorio_clips(manifest)

    n_total = len(clips_lista)
    n_term = sum(
        1 for c in clips_lista if clips_estado[c["clip_id"]]["estado"] in {"completo", "no_anotable"}
    )
    st.sidebar.markdown("---")
    st.sidebar.metric("Progreso del piloto", f"{n_term} / {n_total}")
    st.sidebar.progress(n_term / n_total if n_total else 0.0)

    if st.session_state.get("completados_desde_export", 0) >= 3:
        st.sidebar.warning("Llevas 3 o mas clips nuevos sin exportar. Descarga tu respaldo JSON.")

    nombre_json, payload_json = construir_payload_exportacion(
        manifest, st.session_state["anotador"], clips_estado, VERSION_GUIA, VERSION_APP
    )
    if st.sidebar.download_button(
        "Exportar progreso JSON",
        data=payload_json.encode("utf-8"),
        file_name=nombre_json,
        mime="application/json",
        use_container_width=True,
        type="primary",
    ):
        st.session_state["completados_desde_export"] = 0

    archivo_import = st.sidebar.file_uploader(
        "Importar JSON previo",
        type=["json"],
        key="uploader_anot_json",
    )
    if archivo_import is not None and st.sidebar.button("Aplicar JSON importado", use_container_width=True):
        try:
            nuevo_estado, nuevo_anot = importar_y_fusionar_anotacion(
                archivo_import.getvalue().decode("utf-8"),
                manifest,
            )
        except Exception as exc:
            st.sidebar.error(f"Archivo rechazado: {exc}")
        else:
            st.session_state["clips_estado"] = nuevo_estado
            st.session_state["anotador"] = nuevo_anot
            st.session_state["undo_stacks"] = {}
            st.session_state["completados_desde_export"] = 0
            st.session_state["clip_idx"] = siguiente_clip_pendiente_idx(clips_lista, nuevo_estado, 0)
            st.session_state["t_inicio_clip"] = time.monotonic()
            for c in clips_lista:
                _limpiar_widgets_clip(c["clip_id"])
            st.sidebar.success("Progreso importado correctamente.")
            st.rerun()

    with st.sidebar.expander("Respaldo en navegador", expanded=False):
        st.caption("Si la sesion se reinicio antes de exportar, descarga el respaldo automatico del navegador e importalo arriba.")
        _render_recuperacion_local_storage(manifest["sha256_manifest"])

    st.sidebar.markdown("---")
    etiquetas_estado = {
        "pendiente": "PENDIENTE",
        "en_progreso": "BORRADOR",
        "completo": "COMPLETO",
        "no_anotable": "NO ANOTABLE",
    }
    clip_idx_actual = int(st.session_state["clip_idx"])
    seleccion_idx = st.sidebar.selectbox(
        "Ir a clip",
        options=list(range(n_total)),
        index=clip_idx_actual,
        format_func=lambda idx: f"{idx + 1:02d}. {clips_lista[idx]['clip_id']}",
    )
    if seleccion_idx != clip_idx_actual:
        _cambiar_clip(seleccion_idx, clips_lista[clip_idx_actual]["clip_id"])
        st.rerun()

    with st.sidebar.expander("Estado de los 24 clips", expanded=False):
        resumen_clips = "\n".join(
            f"- **{idx + 1:02d}. {c['clip_id']}**: `{etiquetas_estado.get(clips_estado[c['clip_id']]['estado'], '')}`"
            for idx, c in enumerate(clips_lista)
        )
        st.markdown(resumen_clips)

    if dir_clips is None:
        st.info(
            "Para comenzar a anotar, sube el archivo `clips_piloto.zip` en la barra lateral "
            "(o configura `CLIPS_ZIP_URL` en `st.secrets`)."
        )
        _render_guia_anotacion()
        st.stop()

    clip_meta = clips_lista[clip_idx_actual]
    cid = clip_meta["clip_id"]
    estado_actual = clips_estado[cid]["estado"]

    st.title(f"Clip {clip_idx_actual + 1} de {n_total} — {cid} ({etiquetas_estado.get(estado_actual, estado_actual)})")
    _render_guia_anotacion()

    ruta_mp3 = dir_clips / clip_meta["archivo_clip"]
    _render_reproductor_audio(ruta_mp3, cid)

    st.markdown("---")
    _render_editor_tarjetas(manifest, clips_lista, clip_idx_actual)


if __name__ == "__main__":
    main()
