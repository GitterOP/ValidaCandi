"""Gestion pura de estado de anotacion, edicion de turnos y persistencia JSON."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import re
from typing import Any

from core.validacion_esquemas import (
    MOTIVOS_NO_ANOTABLE_VALIDOS,
    validar_anotacion,
)


def clips_ordenados_para_ui(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Devuelve los clips ordenados por ``orden_anotacion`` sin exponer estrato."""
    return sorted(manifest["clips"], key=lambda c: int(c["orden_anotacion"]))


def crear_estado_inicial(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Construye el diccionario inicial ``clips`` a partir de ``precarga_ui``."""
    clips_estado: dict[str, dict[str, Any]] = {}
    for clip in clips_ordenados_para_ui(manifest):
        cid = clip["clip_id"]
        clips_estado[cid] = {
            "estado": "pendiente",
            "motivo_no_anotable": None,
            "notas": "",
            "turnos": copy.deepcopy(clip["precarga_ui"]),
            "tiempo_anotacion_s": 0.0,
            "timestamp_ultima_edicion": None,
        }
    return clips_estado


def siguiente_clip_pendiente_idx(
    clips_lista: list[dict[str, Any]],
    clips_estado: dict[str, dict[str, Any]],
    desde_idx: int = 0,
) -> int:
    """Devuelve el indice del proximo clip pendiente/en_progreso (o 0 si todos cerraron)."""
    n = len(clips_lista)
    if n == 0:
        return 0
    for offset in range(n):
        idx = (desde_idx + offset) % n
        cid = clips_lista[idx]["clip_id"]
        estado = clips_estado.get(cid, {}).get("estado", "pendiente")
        if estado in {"pendiente", "en_progreso"}:
            return idx
    return 0


def renumerar_turnos(turnos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Asigna ``turno_id`` secuenciales desde 1 sin mutar la lista original."""
    return [
        {
            "turno_id": idx,
            "hablante": str(t["hablante"]).strip(),
            "texto": str(t["texto"]),
        }
        for idx, t in enumerate(turnos, start=1)
    ]


def opciones_hablante_para_clip(turnos: list[dict[str, Any]]) -> list[str]:
    """Devuelve las etiquetas H1..Hn presentes mas la siguiente etiqueta nueva disponible."""
    indices: set[int] = {1}
    for t in turnos:
        m = re.match(r"^H(\d+)$", str(t.get("hablante", "")))
        if m:
            indices.add(int(m.group(1)))
    max_h = max(indices) if indices else 1
    return [f"H{i}" for i in range(1, max_h + 2)]


def _sugerir_hablante_division(turnos: list[dict[str, Any]], hablante_actual: str) -> str:
    """Sugiere una etiqueta distinta razonable para el segundo bloque tras dividir."""
    existentes = []
    for t in turnos:
        h = str(t.get("hablante", ""))
        if h not in existentes:
            existentes.append(h)
    if hablante_actual == "H1" and "H2" in existentes:
        return "H2"
    if hablante_actual != "H1":
        return "H1"
    # Si solo existe H1, proponer H2
    indices = [int(m.group(1)) for h in existentes if (m := re.match(r"^H(\d+)$", h))]
    siguiente = (max(indices) + 1) if indices else 2
    return f"H{siguiente}"


def _asignar_hablantes_division(
    n_bloques: int,
    hab_inicial: str,
    hab_alterno: str,
    hablante_segundo: str | None = None,
) -> list[str]:
    """Asigna hablantes alternando (ej. 2 bloques: H1, H2; 3 bloques: H1, H2, H1)."""
    alt = hablante_segundo or hab_alterno
    return [hab_inicial if k % 2 == 0 else alt for k in range(n_bloques)]


def previsualizar_division_por_indices(
    texto: str,
    hab_inicial: str,
    hab_alterno: str,
    indices_corte: list[int],
) -> list[dict[str, str]]:
    """Calcula los bloques resultantes (2, 3 o mas) sin modificar el estado."""
    palabras = str(texto).split()
    cortes = sorted({int(k) for k in indices_corte if 0 < int(k) < len(palabras)})
    if not cortes:
        return []

    limites = [0, *cortes, len(palabras)]
    hablantes = _asignar_hablantes_division(len(limites) - 1, hab_inicial, hab_alterno)
    bloques: list[dict[str, str]] = []
    for k in range(len(limites) - 1):
        frag = " ".join(palabras[limites[k] : limites[k + 1]]).strip()
        if frag:
            bloques.append({"hablante": hablantes[k], "texto": frag})
    return bloques


def _reemplazar_turno_con_bloques(
    turnos: list[dict[str, Any]],
    idx: int,
    bloques: list[dict[str, str]],
) -> list[dict[str, Any]]:
    nuevos = copy.deepcopy(turnos)
    nuevos.pop(idx)
    for offset, blk in enumerate(bloques):
        nuevos.insert(
            idx + offset,
            {"turno_id": 0, "hablante": blk["hablante"], "texto": blk["texto"]},
        )
    return renumerar_turnos(nuevos)


def dividir_turno_en_marcador(
    turnos: list[dict[str, Any]],
    idx: int,
    marcador: str = "||",
    hablante_segundo: str | None = None,
) -> list[dict[str, Any]]:
    """Divide ``turnos[idx]`` en una o mas apariciones de ``marcador`` (2, 3+ cuadros)."""
    if idx < 0 or idx >= len(turnos):
        raise IndexError("Indice de turno fuera de rango.")
    texto = str(turnos[idx]["texto"])
    if marcador not in texto:
        raise ValueError(f"Inserta '{marcador}' dentro del texto en el punto donde cambia el hablante.")

    partes = [p.strip() for p in texto.split(marcador)]
    if len(partes) < 2 or any(not p for p in partes):
        raise ValueError("Todos los bloques tras dividir deben contener texto.")

    hab_1 = str(turnos[idx]["hablante"])
    hab_alt = hablante_segundo or _sugerir_hablante_division(turnos, hab_1)
    hablantes = _asignar_hablantes_division(len(partes), hab_1, hab_alt, hablante_segundo)
    bloques = [{"hablante": hablantes[k], "texto": partes[k]} for k in range(len(partes))]
    return _reemplazar_turno_con_bloques(turnos, idx, bloques)


def dividir_turno_en_indices(
    turnos: list[dict[str, Any]],
    idx: int,
    indices_corte: list[int],
    hablante_segundo: str | None = None,
) -> list[dict[str, Any]]:
    """Divide ``turnos[idx]`` en uno o varios indices de palabra (generando 2, 3+ cuadros)."""
    if idx < 0 or idx >= len(turnos):
        raise IndexError("Indice de turno fuera de rango.")
    palabras = str(turnos[idx]["texto"]).split()
    if len(palabras) < 2:
        raise ValueError("El turno necesita al menos 2 palabras para dividirse.")

    cortes_validos = sorted({int(k) for k in indices_corte if 0 < int(k) < len(palabras)})
    if not cortes_validos:
        raise ValueError("Selecciona al menos una palabra (distinta de la primera) para dividir.")

    hab_1 = str(turnos[idx]["hablante"])
    hab_alt = hablante_segundo or _sugerir_hablante_division(turnos, hab_1)
    bloques = previsualizar_division_por_indices(turnos[idx]["texto"], hab_1, hab_alt, cortes_validos)
    if len(bloques) < 2:
        raise ValueError("La division debe producir al menos 2 bloques con texto.")
    return _reemplazar_turno_con_bloques(turnos, idx, bloques)


def dividir_turno_en_palabra(
    turnos: list[dict[str, Any]],
    idx: int,
    indice_palabra: int,
    hablante_segundo: str | None = None,
) -> list[dict[str, Any]]:
    """Divide ``turnos[idx]`` antes de la palabra en ``indice_palabra`` (1 <= idx < n)."""
    return dividir_turno_en_indices(
        turnos=turnos,
        idx=idx,
        indices_corte=[indice_palabra],
        hablante_segundo=hablante_segundo,
    )


def unir_con_anterior(turnos: list[dict[str, Any]], idx: int) -> list[dict[str, Any]]:
    """Concatena ``turnos[idx]`` al final de ``turnos[idx - 1]``."""
    if idx <= 0 or idx >= len(turnos):
        raise ValueError("No existe un turno anterior para unir.")
    nuevos = copy.deepcopy(turnos)
    texto_prev = str(nuevos[idx - 1]["texto"]).strip()
    texto_curr = str(nuevos[idx]["texto"]).strip()
    nuevos[idx - 1]["texto"] = f"{texto_prev} {texto_curr}".strip()
    nuevos.pop(idx)
    return renumerar_turnos(nuevos)


def eliminar_turno(turnos: list[dict[str, Any]], idx: int) -> list[dict[str, Any]]:
    """Elimina el turno ``idx`` siempre que quede al menos un turno en el clip."""
    if len(turnos) <= 1:
        raise ValueError("Debe quedar al menos un turno; si el clip no tiene habla, marquelo como no_anotable.")
    if idx < 0 or idx >= len(turnos):
        raise IndexError("Indice de turno fuera de rango.")
    nuevos = copy.deepcopy(turnos)
    nuevos.pop(idx)
    return renumerar_turnos(nuevos)


def acumular_tiempo_clip(
    entrada_clip: dict[str, Any],
    delta_s: float,
    tope_s: float = 900.0,
) -> float:
    """Suma tiempo efectivo al clip acotando pausas largas a ``tope_s``."""
    incremento = min(max(0.0, float(delta_s)), tope_s)
    previo = float(entrada_clip.get("tiempo_anotacion_s", 0.0))
    total = round(previo + incremento, 2)
    entrada_clip["tiempo_anotacion_s"] = total
    return total


def validar_clip_para_completar(
    estado: str,
    motivo_no_anotable: str | None,
    turnos: list[dict[str, Any]],
) -> tuple[bool, str]:
    """Verifica si los datos del clip son validos antes de marcarlo completo o no_anotable."""
    if estado == "no_anotable":
        if motivo_no_anotable not in MOTIVOS_NO_ANOTABLE_VALIDOS:
            return False, "Selecciona un motivo valido para marcar el clip como no anotable."
        return True, ""

    limpios = [t for t in turnos if str(t.get("texto", "")).strip()]
    if not limpios:
        return False, "Debe existir al menos un turno con texto (o marcar el clip como no_anotable)."
    return True, ""


def construir_payload_exportacion(
    manifest: dict[str, Any],
    anotador: str,
    clips_estado: dict[str, dict[str, Any]],
    version_guia: str = "1.0",
    version_app: str = "1.0",
) -> tuple[str, str]:
    """Serializa el archivo ``anot_*.json`` conforme a data-model.md."""
    anot_limpio = re.sub(r"[^a-zA-Z0-9_-]", "", anotador.strip()) or "anon"
    ahora = datetime.now(timezone.utc).astimezone()
    fecha_corta = ahora.strftime("%Y-%m-%d")

    n_terminados = sum(
        1 for v in clips_estado.values() if v.get("estado") in {"completo", "no_anotable"}
    )
    nombre_archivo = f"anot_{anot_limpio}_{fecha_corta}_n{n_terminados:03d}.json"

    clips_serializados: dict[str, Any] = {}
    for clip in clips_ordenados_para_ui(manifest):
        cid = clip["clip_id"]
        entry = copy.deepcopy(clips_estado[cid])
        if entry["estado"] == "no_anotable":
            entry["turnos"] = []
        else:
            entry["motivo_no_anotable"] = None
            entry["turnos"] = renumerar_turnos(entry["turnos"])
        clips_serializados[cid] = entry

    payload = {
        "version_esquema": "1.0",
        "sha256_manifest": manifest["sha256_manifest"],
        "version_guia": version_guia,
        "version_app": version_app,
        "anotador": anot_limpio,
        "fecha_exportacion": ahora.isoformat(timespec="seconds"),
        "clips": clips_serializados,
    }
    return nombre_archivo, json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def importar_y_fusionar_anotacion(
    json_str: str,
    manifest: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], str]:
    """Valida un JSON importado contra el manifest y restaura el estado de todos los clips."""
    data = json.loads(json_str)
    validar_anotacion(data, manifest, exigir_todos_terminados=False)

    base = crear_estado_inicial(manifest)
    for cid, entry in data.get("clips", {}).items():
        if cid in base:
            base[cid] = copy.deepcopy(entry)
            if base[cid]["estado"] != "no_anotable" and not base[cid]["turnos"]:
                clip_meta = next(c for c in manifest["clips"] if c["clip_id"] == cid)
                base[cid]["turnos"] = copy.deepcopy(clip_meta["precarga_ui"])
    return base, str(data.get("anotador", "anon"))

