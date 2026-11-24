"""Validadores de esquemas para manifest_piloto.json y anot_*.json."""

from __future__ import annotations

import re
from typing import Any

from core.hashes import sha256_manifest_canonico

PATRON_CLIP_ID = re.compile(r"^[PMS]\d{3}$")
PATRON_HABLANTE = re.compile(r"^H[1-9]\d*$")
PATRON_HEX64 = re.compile(r"^[0-9a-f]{64}$")

ESTRATOS_VALIDOS = frozenset({"A", "B"})
ESTADOS_VALIDOS = frozenset({"pendiente", "en_progreso", "completo", "no_anotable"})
MOTIVOS_NO_ANOTABLE_VALIDOS = frozenset({"solo_musica", "solo_ruido", "inaudible_total", "otro"})


class EsquemaInvalidoError(ValueError):
    """Error lanzado cuando un artefacto JSON incumple data-model.md."""


def validar_manifest(manifest: dict[str, Any], verificar_hash: bool = True) -> None:
    """Valida el esquema completo de ``manifest_piloto.json``.

    Args:
        manifest: Diccionario parseado del manifest.
        verificar_hash: Si es True, recalcula y compara ``sha256_manifest``.

    Raises:
        EsquemaInvalidoError: Si falta algun campo obligatorio o viola invariantes.
    """
    if not isinstance(manifest, dict):
        raise EsquemaInvalidoError("El manifest debe ser un objeto JSON.")

    for clave in ("version_esquema", "etapa", "fase", "semilla", "fuente", "parametros", "clips", "sha256_manifest"):
        if clave not in manifest:
            raise EsquemaInvalidoError(f"Falta clave obligatoria en manifest: '{clave}'.")

    clips = manifest["clips"]
    if not isinstance(clips, list) or not clips:
        raise EsquemaInvalidoError("El campo 'clips' debe ser una lista no vacia.")

    ids_vistos: set[str] = set()
    ordenes_vistos: set[int] = set()
    for idx, clip in enumerate(clips):
        if not isinstance(clip, dict):
            raise EsquemaInvalidoError(f"Clip en posicion {idx} no es un objeto.")
        cid = clip.get("clip_id", "")
        if not isinstance(cid, str) or not PATRON_CLIP_ID.match(cid):
            raise EsquemaInvalidoError(f"clip_id invalido en posicion {idx}: {cid!r}")
        if cid in ids_vistos:
            raise EsquemaInvalidoError(f"clip_id duplicado en manifest: {cid}")
        ids_vistos.add(cid)

        orden = clip.get("orden_anotacion")
        if not isinstance(orden, int) or orden < 1 or orden in ordenes_vistos:
            raise EsquemaInvalidoError(f"orden_anotacion invalido o duplicado en {cid}: {orden!r}")
        ordenes_vistos.add(orden)

        estrato = clip.get("estrato")
        if estrato not in ESTRATOS_VALIDOS:
            raise EsquemaInvalidoError(f"Estrato invalido en {cid}: {estrato!r}")

        inicio_s = clip.get("inicio_s")
        fin_s = clip.get("fin_s")
        if not isinstance(inicio_s, (int, float)) or not isinstance(fin_s, (int, float)) or fin_s <= inicio_s:
            raise EsquemaInvalidoError(f"Intervalo temporal invalido en {cid}: [{inicio_s}, {fin_s}]")

        for hcampo in ("sha256_wav", "sha256_json"):
            hval = clip.get(hcampo)
            if not isinstance(hval, str) or not PATRON_HEX64.match(hval):
                raise EsquemaInvalidoError(f"{hcampo} invalido en {cid}.")

        hclip = clip.get("sha256_clip")
        if hclip is not None and (not isinstance(hclip, str) or not PATRON_HEX64.match(hclip)):
            raise EsquemaInvalidoError(f"sha256_clip invalido en {cid}.")

        precarga = clip.get("precarga_ui")
        if not isinstance(precarga, list) or not precarga:
            raise EsquemaInvalidoError(f"precarga_ui vacia o invalida en {cid}.")
        for t in precarga:
            validar_turno(t, contexto=f"precarga_ui[{cid}]", permitir_texto_vacio=False)

    if verificar_hash:
        esperado = sha256_manifest_canonico(manifest)
        if manifest["sha256_manifest"] != esperado:
            raise EsquemaInvalidoError(
                f"sha256_manifest inconsistente: archivo={manifest['sha256_manifest']}, "
                f"calculado={esperado}"
            )

    linaje = manifest.get("linaje_muestreo")
    if linaje is not None:
        if not isinstance(linaje, dict) or not isinstance(linaje.get("manifests_previos"), list):
            raise EsquemaInvalidoError("El campo 'linaje_muestreo' debe incluir lista 'manifests_previos'.")
        for prev in linaje["manifests_previos"]:
            if not isinstance(prev, dict) or not PATRON_HEX64.match(str(prev.get("sha256_manifest", ""))):
                raise EsquemaInvalidoError("Entrada invalida en 'linaje_muestreo.manifests_previos'.")


def verificar_sin_solapamiento_manifests(
    manifests: list[dict[str, Any]],
    colchon_s: float = 0.0,
) -> None:
    """Verifica que no existan clip_id repetidos ni intervalos solapados entre manifests."""
    ids_globales: set[str] = set()
    por_entrevista: dict[str, list[tuple[str, float, float]]] = {}

    for m in manifests:
        for clip in m.get("clips", []):
            cid = clip["clip_id"]
            if cid in ids_globales:
                raise EsquemaInvalidoError(f"clip_id duplicado al consolidar manifests: {cid}")
            ids_globales.add(cid)

            ent = clip["entrevista"]
            ini = float(clip["inicio_s"])
            fin = float(clip["fin_s"])
            for prev_cid, p_ini, p_fin in por_entrevista.get(ent, []):
                if ini < (p_fin + colchon_s) and fin > (p_ini - colchon_s):
                    raise EsquemaInvalidoError(
                        f"Solapamiento detectado en '{ent}': {prev_cid} [{p_ini}, {p_fin}] "
                        f"y {cid} [{ini}, {fin}] (colchon={colchon_s} s)."
                    )
            por_entrevista.setdefault(ent, []).append((cid, ini, fin))


def validar_turno(
    turno: dict[str, Any],
    contexto: str = "turno",
    permitir_texto_vacio: bool = False,
) -> None:
    """Valida un diccionario individual de turno."""
    if not isinstance(turno, dict):
        raise EsquemaInvalidoError(f"{contexto}: el turno debe ser un objeto.")
    hab = turno.get("hablante")
    if not isinstance(hab, str) or not PATRON_HABLANTE.match(hab):
        raise EsquemaInvalidoError(f"{contexto}: hablante invalido ({hab!r}), esperado H1, H2, ...")
    texto = turno.get("texto")
    if not isinstance(texto, str):
        raise EsquemaInvalidoError(f"{contexto}: 'texto' debe ser una cadena.")
    if not permitir_texto_vacio and not texto.strip():
        raise EsquemaInvalidoError(f"{contexto}: el texto del turno no puede estar vacio.")


def fusionar_turnos_consecutivos(turnos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fusiona turnos adyacentes con la misma etiqueta de hablante.

    Ignora turnos completamente vacios y reenumera ``turno_id`` desde 1.
    """
    fusionados: list[dict[str, Any]] = []
    for t in turnos:
        hab = str(t.get("hablante", "")).strip()
        txt = str(t.get("texto", "")).strip()
        if not txt:
            continue
        if fusionados and fusionados[-1]["hablante"] == hab:
            fusionados[-1]["texto"] = f"{fusionados[-1]['texto']} {txt}".strip()
        else:
            fusionados.append(
                {
                    "turno_id": len(fusionados) + 1,
                    "hablante": hab,
                    "texto": txt,
                }
            )
    return fusionados


def validar_anotacion(
    anotacion: dict[str, Any],
    manifest: dict[str, Any],
    exigir_todos_terminados: bool = False,
) -> list[str]:
    """Valida un archivo ``anot_*.json`` frente a ``manifest_piloto.json``.

    Args:
        anotacion: Diccionario JSON importado o exportado por la app.
        manifest: Manifest validado.
        exigir_todos_terminados: Si es True, verifica que ningun clip este pendiente o en progreso.

    Returns:
        Lista de ``clip_id`` incompletos (vacia si todos estan completos o no_anotable).

    Raises:
        EsquemaInvalidoError: Si el hash no coincide o algun clip viola el esquema.
    """
    if not isinstance(anotacion, dict):
        raise EsquemaInvalidoError("El archivo de anotacion debe ser un objeto JSON.")

    for clave in ("version_esquema", "sha256_manifest", "version_guia", "anotador", "clips"):
        if clave not in anotacion:
            raise EsquemaInvalidoError(f"Falta clave obligatoria en anotacion: '{clave}'.")

    if anotacion["sha256_manifest"] != manifest["sha256_manifest"]:
        raise EsquemaInvalidoError(
            "El archivo de anotacion pertenece a otro manifest "
            f"(anotacion={anotacion['sha256_manifest']}, actual={manifest['sha256_manifest']})."
        )

    clips_manifest = {c["clip_id"] for c in manifest["clips"]}
    clips_anot = anotacion["clips"]
    if not isinstance(clips_anot, dict):
        raise EsquemaInvalidoError("El campo 'clips' de la anotacion debe ser un diccionario.")

    extras = set(clips_anot.keys()) - clips_manifest
    if extras:
        raise EsquemaInvalidoError(f"La anotacion contiene clip_ids ajenos al manifest: {sorted(extras)}")

    incompletos: list[str] = []
    for cid in sorted(clips_manifest):
        entry = clips_anot.get(cid)
        if entry is None:
            incompletos.append(cid)
            continue
        if not isinstance(entry, dict):
            raise EsquemaInvalidoError(f"Entrada invalida para {cid}.")

        estado = entry.get("estado")
        if estado not in ESTADOS_VALIDOS:
            raise EsquemaInvalidoError(f"Estado invalido en {cid}: {estado!r}")

        motivo = entry.get("motivo_no_anotable")
        turnos = entry.get("turnos")
        if not isinstance(turnos, list):
            raise EsquemaInvalidoError(f"'turnos' debe ser una lista en {cid}.")

        if estado == "no_anotable":
            if motivo not in MOTIVOS_NO_ANOTABLE_VALIDOS:
                raise EsquemaInvalidoError(f"Motivo no_anotable invalido en {cid}: {motivo!r}")
            if turnos:
                raise EsquemaInvalidoError(f"Clip {cid} marcado no_anotable debe tener 'turnos' vacio.")
        elif estado == "completo":
            if motivo is not None:
                raise EsquemaInvalidoError(f"Clip {cid} completo no debe tener motivo_no_anotable.")
            if not turnos:
                raise EsquemaInvalidoError(f"Clip {cid} completo debe tener al menos un turno.")
            for t in turnos:
                validar_turno(t, contexto=f"anotacion[{cid}]", permitir_texto_vacio=False)
        else:
            incompletos.append(cid)
            for t in turnos:
                validar_turno(t, contexto=f"anotacion[{cid}]", permitir_texto_vacio=True)

        tiempo = entry.get("tiempo_anotacion_s", 0.0)
        if not isinstance(tiempo, (int, float)) or tiempo < 0:
            raise EsquemaInvalidoError(f"tiempo_anotacion_s invalido en {cid}: {tiempo!r}")

    if exigir_todos_terminados and incompletos:
        raise EsquemaInvalidoError(
            f"Aun existen {len(incompletos)} clips sin terminar: {incompletos}"
        )
    return incompletos

