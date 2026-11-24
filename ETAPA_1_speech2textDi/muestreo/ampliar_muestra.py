"""Muestreador incremental anidado (Lote Medio +32 y Lote Seguro +32 en reserva)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
from typing import Any

_ETAPA_DIR = Path(__file__).resolve().parents[1]
if str(_ETAPA_DIR) not in sys.path:
    sys.path.insert(0, str(_ETAPA_DIR))

from core.hashes import sha256_archivo, sha256_manifest_canonico
from core.io_diario import (
    agrupar_en_turnos,
    ajustar_bordes_a_huecos,
    cargar_json_diario,
    detectar_cambios_turno_segmento,
    duracion_diario_s,
    extraer_palabras_diario,
    recortar_palabras_clip,
)
from core.validacion_esquemas import (
    validar_manifest,
    verificar_sin_solapamiento_manifests,
)
from muestreo.muestrear import _descubrir_parejas


def _intervalo_libre(
    entrevista: str,
    inicio_s: float,
    fin_s: float,
    ocupados: dict[str, list[tuple[float, float]]],
    colchon_s: float,
) -> bool:
    for p_ini, p_fin in ocupados.get(entrevista, []):
        if inicio_s < (p_fin + colchon_s) and fin_s > (p_ini - colchon_s):
            return False
    return True


def _muestrear_estrato_b_libre(
    rng: random.Random,
    entrevista: str,
    palabras_seg: list[Any],
    duracion_total: float,
    duracion_clip: float,
    ajuste_borde_max: float,
    ocupados: dict[str, list[tuple[float, float]]],
    colchon_s: float,
) -> tuple[float, float, list[dict[str, Any]]]:
    max_inicio = duracion_total - duracion_clip
    if max_inicio < 0:
        raise ValueError(f"Entrevista '{entrevista}' demasiado corta ({duracion_total:.2f} s).")

    for _ in range(200):
        inicio_nom = rng.uniform(0.0, max_inicio)
        fin_nom = inicio_nom + duracion_clip
        inicio_s, fin_s = ajustar_bordes_a_huecos(
            inicio_nom, fin_nom, palabras_seg, duracion_total, ajuste_borde_max
        )
        if not _intervalo_libre(entrevista, inicio_s, fin_s, ocupados, colchon_s):
            continue
        pals_clip = recortar_palabras_clip(palabras_seg, inicio_s, fin_s)
        turnos = agrupar_en_turnos(pals_clip, mapear_genericos=True)
        if turnos:
            return inicio_s, fin_s, turnos

    raise ValueError(f"No se encontro ventana libre en Estrato B para '{entrevista}'.")


def _muestrear_estrato_a_libre(
    rng: random.Random,
    entrevista: str,
    diario_data: dict[str, Any],
    palabras_seg: list[Any],
    duracion_total: float,
    duracion_clip: float,
    ajuste_borde_max: float,
    ocupados: dict[str, list[tuple[float, float]]],
    colchon_s: float,
) -> tuple[float, float, float, list[dict[str, Any]]]:
    cambios = detectar_cambios_turno_segmento(diario_data)
    cambios_validos = [t for t in cambios if 45.0 <= t <= duracion_total - 45.0]
    if not cambios_validos:
        cambios_validos = [t for t in cambios if 15.0 <= t <= duracion_total - 15.0]
    if not cambios_validos:
        raise ValueError(f"Sin cambios de turno elegibles en '{entrevista}'.")

    candidatos_tc = list(cambios_validos)
    rng.shuffle(candidatos_tc)
    for t_c in candidatos_tc:
        for _ in range(5):
            offset = rng.uniform(15.0, 45.0)
            inicio_nom = max(0.0, min(duracion_total - duracion_clip, t_c - offset))
            fin_nom = inicio_nom + duracion_clip
            inicio_s, fin_s = ajustar_bordes_a_huecos(
                inicio_nom, fin_nom, palabras_seg, duracion_total, ajuste_borde_max
            )
            if not _intervalo_libre(entrevista, inicio_s, fin_s, ocupados, colchon_s):
                continue
            pals_clip = recortar_palabras_clip(palabras_seg, inicio_s, fin_s)
            turnos = agrupar_en_turnos(pals_clip, mapear_genericos=True)
            if turnos:
                return round(t_c, 3), inicio_s, fin_s, turnos

    raise ValueError(f"No se encontro ventana libre en Estrato A para '{entrevista}'.")


def _construir_clip_registro(
    rng: random.Random,
    item: dict[str, Any],
    estrato: str,
    duracion_clip: float,
    ajuste_borde_max: float,
    ocupados: dict[str, list[tuple[float, float]]],
    colchon_s: float,
) -> dict[str, Any]:
    ent = item["entrevista"]
    diario_data = cargar_json_diario(item["ruta_json"])
    dur_total = duracion_diario_s(diario_data)
    palabras_seg = extraer_palabras_diario(diario_data, vista="segment")

    if estrato == "B":
        ancla = None
        inicio_s, fin_s, precarga = _muestrear_estrato_b_libre(
            rng, ent, palabras_seg, dur_total, duracion_clip, ajuste_borde_max, ocupados, colchon_s
        )
    else:
        ancla, inicio_s, fin_s, precarga = _muestrear_estrato_a_libre(
            rng, ent, diario_data, palabras_seg, dur_total, duracion_clip, ajuste_borde_max, ocupados, colchon_s
        )

    ocupados.setdefault(ent, []).append((inicio_s, fin_s))
    return {
        "entrevista": ent,
        "candidato_cid": item["candidato_cid"],
        "candidato_slug": item["candidato_slug"],
        "estrato": estrato,
        "cambio_turno_ancla_s": ancla,
        "inicio_s": inicio_s,
        "fin_s": fin_s,
        "duracion_s": round(fin_s - inicio_s, 3),
        "sha256_wav": sha256_archivo(item["ruta_wav"]),
        "sha256_json": sha256_archivo(item["ruta_json"]),
        "sha256_clip": None,
        "precarga_ui": precarga,
    }


def _empaquetar_manifest_lote(
    rng: random.Random,
    seleccionados: list[dict[str, Any]],
    prefijo_id: str,
    fase: str,
    semilla: int,
    repo_fuente: Path,
    n_marco: int,
    duracion_clip: float,
    ajuste_borde_max: float,
    clips_b: int,
    clips_a: int,
    colchon_s: float,
    manifests_previos: list[dict[str, Any]],
) -> dict[str, Any]:
    lista = list(seleccionados)
    rng.shuffle(lista)

    clips_finales: list[dict[str, Any]] = []
    for idx, entry in enumerate(lista, start=1):
        clip_id = f"{prefijo_id}{idx:03d}"
        clips_finales.append(
            {
                "clip_id": clip_id,
                "orden_anotacion": idx,
                "entrevista": entry["entrevista"],
                "candidato_cid": entry["candidato_cid"],
                "candidato_slug": entry["candidato_slug"],
                "estrato": entry["estrato"],
                "cambio_turno_ancla_s": entry["cambio_turno_ancla_s"],
                "inicio_s": entry["inicio_s"],
                "fin_s": entry["fin_s"],
                "duracion_s": entry["duracion_s"],
                "sha256_wav": entry["sha256_wav"],
                "sha256_json": entry["sha256_json"],
                "archivo_clip": f"{clip_id}.mp3",
                "sha256_clip": None,
                "precarga_ui": entry["precarga_ui"],
            }
        )

    manifest: dict[str, Any] = {
        "version_esquema": "1.0",
        "etapa": "ETAPA_1_speech2textDi",
        "fase": fase,
        "semilla": semilla,
        "fecha_generacion": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "fuente": {
            "repo_path": str(repo_fuente.resolve()),
            "dir_diario": "Resultados/Diario",
            "dir_audios": "Resultados/Audios",
            "n_entrevistas_marco": n_marco,
        },
        "parametros": {
            "duracion_clip_s": duracion_clip,
            "ajuste_borde_max_s": ajuste_borde_max,
            "offset_estrato_a_s": [15.0, 45.0],
            "clips_por_candidato_estrato_b": clips_b,
            "clips_por_candidato_estrato_a": clips_a,
            "formato_clip": {
                "codec": "mp3",
                "canales": 1,
                "frecuencia_hz": 16000,
                "bitrate_kbps": 64,
            },
        },
        "linaje_muestreo": {
            "semilla_ampliacion": semilla,
            "colchon_exclusion_s": colchon_s,
            "manifests_previos": manifests_previos,
        },
        "clips": clips_finales,
        "sha256_manifest": "",
    }
    manifest["sha256_manifest"] = sha256_manifest_canonico(manifest)
    validar_manifest(manifest, verificar_hash=True)
    return manifest


def generar_manifests_ampliacion(
    ruta_piloto: Path,
    repo_fuente: Path | None = None,
    semilla: int = 20261124,
    colchon_s: float = 30.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Genera de forma anidada el Lote Medio (+32) y la reserva Lote Seguro (+32)."""
    with ruta_piloto.open("r", encoding="utf-8") as fh:
        manifest_piloto = json.load(fh)
    validar_manifest(manifest_piloto, verificar_hash=True)

    fuente_path = (
        repo_fuente if repo_fuente is not None else Path(manifest_piloto["fuente"]["repo_path"])
    )
    por_candidato = _descubrir_parejas(fuente_path)
    n_marco = sum(len(v) for v in por_candidato.values())
    duracion_clip = float(manifest_piloto["parametros"]["duracion_clip_s"])
    ajuste_borde_max = float(manifest_piloto["parametros"]["ajuste_borde_max_s"])

    usadas_piloto: dict[int, set[str]] = {}
    ocupados: dict[str, list[tuple[float, float]]] = {}
    for clip in manifest_piloto["clips"]:
        usadas_piloto.setdefault(int(clip["candidato_cid"]), set()).add(clip["entrevista"])
        ocupados.setdefault(clip["entrevista"], []).append(
            (float(clip["inicio_s"]), float(clip["fin_s"]))
        )

    rng = random.Random(semilla)
    sel_medio: list[dict[str, Any]] = []
    sel_seguro: list[dict[str, Any]] = []

    for cid, entrevistas in por_candidato.items():
        usadas_cid = usadas_piloto.get(cid, set())
        virgenes = [e for e in entrevistas if e["entrevista"] not in usadas_cid]
        if len(virgenes) < 7:
            raise ValueError(
                f"Candidato {cid} requiere al menos 7 entrevistas sin usar; encontradas {len(virgenes)}."
            )

        rng.shuffle(virgenes)
        # Lote Medio: 4 entrevistas virgenes (2 B + 2 A)
        for idx_m, item in enumerate(virgenes[:4]):
            estrato = "B" if idx_m < 2 else "A"
            sel_medio.append(
                _construir_clip_registro(
                    rng, item, estrato, duracion_clip, ajuste_borde_max, ocupados, colchon_s
                )
            )

        # Lote Seguro (reserva): 3 entrevistas virgenes restantes (2 B + 1 A) + 1 B en entrevista mas larga
        for idx_s, item in enumerate(virgenes[4:7]):
            estrato = "B" if idx_s < 2 else "A"
            sel_seguro.append(
                _construir_clip_registro(
                    rng, item, estrato, duracion_clip, ajuste_borde_max, ocupados, colchon_s
                )
            )

        entrevista_mas_larga = max(
            entrevistas,
            key=lambda e: duracion_diario_s(cargar_json_diario(e["ruta_json"])),
        )
        sel_seguro.append(
            _construir_clip_registro(
                rng,
                entrevista_mas_larga,
                "B",
                duracion_clip,
                ajuste_borde_max,
                ocupados,
                colchon_s,
            )
        )

    prev_piloto = {
        "archivo": ruta_piloto.name,
        "fase": manifest_piloto["fase"],
        "sha256_manifest": manifest_piloto["sha256_manifest"],
        "n_clips": len(manifest_piloto["clips"]),
    }

    manifest_medio = _empaquetar_manifest_lote(
        rng=rng,
        seleccionados=sel_medio,
        prefijo_id="M",
        fase="ampliacion_medio",
        semilla=semilla,
        repo_fuente=fuente_path,
        n_marco=n_marco,
        duracion_clip=duracion_clip,
        ajuste_borde_max=ajuste_borde_max,
        clips_b=2,
        clips_a=2,
        colchon_s=colchon_s,
        manifests_previos=[prev_piloto],
    )

    prev_medio = {
        "archivo": "manifest_ampliacion_medio.json",
        "fase": manifest_medio["fase"],
        "sha256_manifest": manifest_medio["sha256_manifest"],
        "n_clips": len(manifest_medio["clips"]),
    }

    manifest_seguro = _empaquetar_manifest_lote(
        rng=rng,
        seleccionados=sel_seguro,
        prefijo_id="S",
        fase="ampliacion_seguro",
        semilla=semilla,
        repo_fuente=fuente_path,
        n_marco=n_marco,
        duracion_clip=duracion_clip,
        ajuste_borde_max=ajuste_borde_max,
        clips_b=3,
        clips_a=1,
        colchon_s=colchon_s,
        manifests_previos=[prev_piloto, prev_medio],
    )

    verificar_sin_solapamiento_manifests(
        [manifest_piloto, manifest_medio, manifest_seguro], colchon_s=colchon_s
    )
    return manifest_medio, manifest_seguro


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera manifests incrementales sin solapamiento (Medio +32 y Seguro +32)."
    )
    parser.add_argument(
        "--piloto",
        type=Path,
        default=_ETAPA_DIR / "muestreo" / "manifest_piloto.json",
        help="Ruta al manifest del piloto congelado.",
    )
    parser.add_argument(
        "--repo-fuente",
        type=Path,
        default=None,
        help="Override opcional de ruta de solo lectura a CodeCursos.",
    )
    parser.add_argument(
        "--salida-medio",
        type=Path,
        default=_ETAPA_DIR / "muestreo" / "manifest_ampliacion_medio.json",
    )
    parser.add_argument(
        "--salida-seguro",
        type=Path,
        default=_ETAPA_DIR / "muestreo" / "manifest_ampliacion_seguro.json",
    )
    parser.add_argument("--semilla", type=int, default=20261124)
    parser.add_argument("--colchon-s", type=float, default=30.0)
    parser.add_argument("--sobrescribir", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.piloto.is_file():
        print(f"ERROR: No existe el manifest piloto: {args.piloto}")
        return 1

    if (args.salida_medio.exists() or args.salida_seguro.exists()) and not args.sobrescribir:
        print("ERROR: Ya existen manifests de ampliacion. Use --sobrescribir para regenerarlos.")
        return 2

    try:
        m_medio, m_seguro = generar_manifests_ampliacion(
            ruta_piloto=args.piloto,
            repo_fuente=args.repo_fuente,
            semilla=args.semilla,
            colchon_s=args.colchon_s,
        )
    except Exception as exc:
        print(f"ERROR generando ampliacion: {exc}")
        return 1

    for ruta, data in ((args.salida_medio, m_medio), (args.salida_seguro, m_seguro)):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    print("Ampliacion anidada generada sin solapamiento.")
    print(f"Lote Medio: {args.salida_medio} ({len(m_medio['clips'])} clips, sha256={m_medio['sha256_manifest']})")
    print(f"Lote Seguro (reserva): {args.salida_seguro} ({len(m_seguro['clips'])} clips, sha256={m_seguro['sha256_manifest']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
