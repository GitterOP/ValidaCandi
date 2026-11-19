"""Muestreo estratificado y determinista de clips para el piloto de Etapa 1."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
from typing import Any

# Permitir ejecucion directa como script desde cualquier directorio de trabajo
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
from core.validacion_esquemas import validar_manifest


def _parsear_identidad_archivo(stem: str) -> tuple[int, int, str]:
    """Extrae (video_id, candidato_cid, candidato_slug) de '{ID}_{CID}_{nombre}'."""
    partes = stem.split("_")
    if len(partes) < 3:
        raise ValueError(f"Nombre de archivo no sigue patron '{{ID}}_{{CID}}_{{nombre}}': {stem}")
    vid_id = int(partes[0])
    cid = int(partes[1])
    slug = f"{cid}_{'_'.join(partes[2:])}"
    return vid_id, cid, slug


def _descubrir_parejas(repo_fuente: Path) -> dict[int, list[dict[str, Any]]]:
    """Verifica correspondencia 1 a 1 entre WAVs y JSONs y agrupa por candidato."""
    dir_audios = repo_fuente / "Resultados" / "Audios"
    dir_diario = repo_fuente / "Resultados" / "Diario"
    if not dir_audios.is_dir() or not dir_diario.is_dir():
        raise FileNotFoundError(
            f"No se encontraron directorios Resultados/Audios y Resultados/Diario en {repo_fuente}"
        )

    wavs = {p.stem: p for p in sorted(dir_audios.glob("*.wav"))}
    jsons = {p.stem: p for p in sorted(dir_diario.glob("*.json"))}

    if set(wavs.keys()) != set(jsons.keys()):
        solo_wav = sorted(set(wavs.keys()) - set(jsons.keys()))
        solo_json = sorted(set(jsons.keys()) - set(wavs.keys()))
        raise ValueError(
            f"Desajuste entre Audios y Diario. Solo WAV: {solo_wav[:5]}; Solo JSON: {solo_json[:5]}"
        )
    if not wavs:
        raise ValueError("No se encontraron parejas WAV/JSON en el repositorio fuente.")

    por_candidato: dict[int, list[dict[str, Any]]] = {}
    for stem in sorted(wavs.keys()):
        vid_id, cid, slug = _parsear_identidad_archivo(stem)
        por_candidato.setdefault(cid, []).append(
            {
                "entrevista": stem,
                "vid_id": vid_id,
                "candidato_cid": cid,
                "candidato_slug": slug,
                "ruta_wav": wavs[stem],
                "ruta_json": jsons[stem],
            }
        )

    for cid in por_candidato:
        por_candidato[cid].sort(key=lambda x: (x["vid_id"], x["entrevista"]))
    return dict(sorted(por_candidato.items()))


def _muestrear_estrato_b(
    rng: random.Random,
    diario_data: dict[str, Any],
    palabras_seg: list[Any],
    duracion_total: float,
    duracion_clip: float,
    ajuste_borde_max: float,
) -> tuple[float, float, list[dict[str, Any]]]:
    """Sortea un clip aleatorio de Estrato B evitando ventanas sin palabras."""
    max_inicio = duracion_total - duracion_clip
    if max_inicio < 0:
        raise ValueError(f"Entrevista demasiado corta ({duracion_total:.2f} s) para clip de {duracion_clip:.2f} s.")

    for _ in range(50):
        inicio_nom = rng.uniform(0.0, max_inicio)
        fin_nom = inicio_nom + duracion_clip
        inicio_s, fin_s = ajustar_bordes_a_huecos(
            inicio_nom, fin_nom, palabras_seg, duracion_total, ajuste_borde_max
        )
        pals_clip = recortar_palabras_clip(palabras_seg, inicio_s, fin_s)
        turnos = agrupar_en_turnos(pals_clip, mapear_genericos=True)
        if turnos:
            return inicio_s, fin_s, turnos

    raise ValueError("No se encontro una ventana con palabras en Estrato B tras 50 intentos.")


def _muestrear_estrato_a(
    rng: random.Random,
    diario_data: dict[str, Any],
    palabras_seg: list[Any],
    duracion_total: float,
    duracion_clip: float,
    ajuste_borde_max: float,
) -> tuple[float, float, float, list[dict[str, Any]]]:
    """Sortea un clip anclado a un cambio de turno detectado a nivel de segmento."""
    cambios = detectar_cambios_turno_segmento(diario_data)
    cambios_validos = [t for t in cambios if 45.0 <= t <= duracion_total - 45.0]
    if not cambios_validos:
        cambios_validos = [t for t in cambios if 15.0 <= t <= duracion_total - 15.0]
    if not cambios_validos:
        raise ValueError("La entrevista no contiene cambios de turno elegibles para Estrato A.")

    candidatos_tc = list(cambios_validos)
    rng.shuffle(candidatos_tc)
    for t_c in candidatos_tc:
        offset = rng.uniform(15.0, 45.0)
        inicio_nom = max(0.0, min(duracion_total - duracion_clip, t_c - offset))
        fin_nom = inicio_nom + duracion_clip
        inicio_s, fin_s = ajustar_bordes_a_huecos(
            inicio_nom, fin_nom, palabras_seg, duracion_total, ajuste_borde_max
        )
        pals_clip = recortar_palabras_clip(palabras_seg, inicio_s, fin_s)
        turnos = agrupar_en_turnos(pals_clip, mapear_genericos=True)
        if turnos:
            return round(t_c, 3), inicio_s, fin_s, turnos

    raise ValueError("No se encontro una ventana valida con palabras en Estrato A.")


def generar_manifest_piloto(
    repo_fuente: Path,
    semilla: int = 20261119,
    clips_b: int = 2,
    clips_a: int = 1,
    duracion_clip: float = 60.0,
    ajuste_borde_max: float = 2.0,
) -> dict[str, Any]:
    """Ejecuta el muestreo estratificado y construye el diccionario completo del manifest."""
    por_candidato = _descubrir_parejas(repo_fuente)
    requeridas = clips_b + clips_a
    for cid, lista in por_candidato.items():
        if len(lista) < requeridas:
            raise ValueError(
                f"Candidato {cid} solo tiene {len(lista)} entrevistas y requiere {requeridas}."
            )

    rng = random.Random(semilla)
    seleccionados: list[dict[str, Any]] = []
    n_marco = sum(len(v) for v in por_candidato.values())

    for cid, entrevistas in por_candidato.items():
        barajadas = list(entrevistas)
        rng.shuffle(barajadas)
        elegidas = barajadas[:requeridas]

        for idx_ent, item in enumerate(elegidas):
            estrato = "B" if idx_ent < clips_b else "A"
            diario_data = cargar_json_diario(item["ruta_json"])
            dur_total = duracion_diario_s(diario_data)
            palabras_seg = extraer_palabras_diario(diario_data, vista="segment")

            if estrato == "B":
                ancla = None
                inicio_s, fin_s, precarga = _muestrear_estrato_b(
                    rng, diario_data, palabras_seg, dur_total, duracion_clip, ajuste_borde_max
                )
            else:
                ancla, inicio_s, fin_s, precarga = _muestrear_estrato_a(
                    rng, diario_data, palabras_seg, dur_total, duracion_clip, ajuste_borde_max
                )

            sha_wav = sha256_archivo(item["ruta_wav"])
            sha_json = sha256_archivo(item["ruta_json"])
            seleccionados.append(
                {
                    "entrevista": item["entrevista"],
                    "candidato_cid": item["candidato_cid"],
                    "candidato_slug": item["candidato_slug"],
                    "estrato": estrato,
                    "cambio_turno_ancla_s": ancla,
                    "inicio_s": inicio_s,
                    "fin_s": fin_s,
                    "duracion_s": round(fin_s - inicio_s, 3),
                    "sha256_wav": sha_wav,
                    "sha256_json": sha_json,
                    "sha256_clip": None,
                    "precarga_ui": precarga,
                }
            )

    # Permutacion aleatoria del orden de anotacion para ocultar candidato y estrato
    rng.shuffle(seleccionados)
    clips_finales: list[dict[str, Any]] = []
    for idx, entry in enumerate(seleccionados, start=1):
        clip_id = f"P{idx:03d}"
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
        "fase": "piloto",
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
        "clips": clips_finales,
        "sha256_manifest": "",
    }
    manifest["sha256_manifest"] = sha256_manifest_canonico(manifest)
    validar_manifest(manifest, verificar_hash=True)
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Muestreo estratificado de clips para el piloto de Etapa 1."
    )
    parser.add_argument(
        "--repo-fuente",
        type=Path,
        default=Path("/home/jd/Escritorio/CodeCursos"),
        help="Ruta raiz de solo lectura al repositorio CodeCursos.",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=_ETAPA_DIR / "muestreo" / "manifest_piloto.json",
        help="Ruta de salida para manifest_piloto.json.",
    )
    parser.add_argument("--semilla", type=int, default=20261119, help="Semilla fija.")
    parser.add_argument("--clips-b", type=int, default=2, help="Clips Estrato B por candidato.")
    parser.add_argument("--clips-a", type=int, default=1, help="Clips Estrato A por candidato.")
    parser.add_argument("--duracion", type=float, default=60.0, help="Duracion nominal en segundos.")
    parser.add_argument(
        "--ajuste-borde-max",
        type=float,
        default=2.0,
        help="Ajuste maximo de bordes a huecos entre palabras (s).",
    )
    parser.add_argument(
        "--sobrescribir",
        action="store_true",
        help="Permite sobrescribir un manifest existente.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.salida.exists() and not args.sobrescribir:
        print(f"ERROR: El archivo de salida ya existe: {args.salida}. Use --sobrescribir.")
        return 2

    if args.duracion <= 0 or args.clips_b < 0 or args.clips_a < 0 or (args.clips_b + args.clips_a) < 1 or args.ajuste_borde_max < 0:
        print("ERROR: Parametros de muestreo fuera de rango.")
        return 2

    try:
        manifest = generar_manifest_piloto(
            repo_fuente=args.repo_fuente,
            semilla=args.semilla,
            clips_b=args.clips_b,
            clips_a=args.clips_a,
            duracion_clip=args.duracion,
            ajuste_borde_max=args.ajuste_borde_max,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR de validacion de insumos: {exc}")
        return 1

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with args.salida.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    n_b = sum(1 for c in manifest["clips"] if c["estrato"] == "B")
    n_a = sum(1 for c in manifest["clips"] if c["estrato"] == "A")
    print("Muestreo piloto completado correctamente.")
    print(f"Salida: {args.salida}")
    print(f"Total clips: {len(manifest['clips'])} (Estrato B={n_b}, Estrato A={n_a})")
    print(f"Semilla: {manifest['semilla']}")
    print(f"sha256_manifest: {manifest['sha256_manifest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

