"""Recorte determinista de clips MP3 con ffmpeg y empaquetado ZIP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

_ETAPA_DIR = Path(__file__).resolve().parents[1]
if str(_ETAPA_DIR) not in sys.path:
    sys.path.insert(0, str(_ETAPA_DIR))

from core.hashes import sha256_archivo, sha256_manifest_canonico
from core.validacion_esquemas import EsquemaInvalidoError, validar_manifest


def _verificar_clips_existentes(manifest: dict, dir_clips: Path) -> int:
    """Verifica que todos los MP3 existan y coincidan con sha256_clip."""
    errores = 0
    for clip in manifest["clips"]:
        cid = clip["clip_id"]
        nombre = clip["archivo_clip"]
        esperado = clip.get("sha256_clip")
        ruta = dir_clips / nombre
        if not esperado:
            print(f"FALLO {cid}: sha256_clip es null en el manifest.")
            errores += 1
            continue
        if not ruta.is_file():
            print(f"FALLO {cid}: falta el archivo {ruta}.")
            errores += 1
            continue
        actual = sha256_archivo(ruta)
        if actual != esperado:
            print(f"FALLO {cid}: hash distinto (esperado={esperado[:12]}, actual={actual[:12]}).")
            errores += 1
    if errores:
        print(f"Verificacion fallida: {errores} clip(s) con problemas.")
        return 1
    print(f"Verificacion exitosa: {len(manifest['clips'])} clips intactos en {dir_clips}.")
    return 0


def _recortar_clip_ffmpeg(
    ruta_wav: Path,
    ruta_mp3: Path,
    inicio_s: float,
    duracion_s: float,
    canales: int,
    frecuencia_hz: int,
    bitrate_kbps: int,
) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{inicio_s:.3f}",
        "-t",
        f"{duracion_s:.3f}",
        "-i",
        str(ruta_wav),
        "-ac",
        str(canales),
        "-ar",
        str(frecuencia_hz),
        "-b:a",
        f"{bitrate_kbps}k",
        "-map_metadata",
        "-1",
        str(ruta_mp3),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg fallo para {ruta_mp3.name}: {res.stderr.strip()}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recorta clips MP3 desde los WAV de CodeCursos y crea clips_piloto.zip."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_ETAPA_DIR / "muestreo" / "manifest_piloto.json",
        help="Ruta al manifest_piloto.json.",
    )
    parser.add_argument(
        "--repo-fuente",
        type=Path,
        default=None,
        help="Override opcional de la ruta de solo lectura a CodeCursos.",
    )
    parser.add_argument(
        "--dir-clips",
        type=Path,
        default=_ETAPA_DIR / "muestreo" / "clips",
        help="Directorio local donde guardar los MP3.",
    )
    parser.add_argument(
        "--zip-salida",
        type=Path,
        default=None,
        help="Ruta del archivo ZIP generado (por defecto <dir-clips>/clips_piloto.zip).",
    )
    parser.add_argument(
        "--solo-verificar",
        action="store_true",
        help="Solo verifica hashes de los MP3 existentes sin recortar.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.manifest.is_file():
        print(f"ERROR: No existe el manifest: {args.manifest}")
        return 1

    try:
        with args.manifest.open("r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        validar_manifest(manifest, verificar_hash=True)
    except (json.JSONDecodeError, EsquemaInvalidoError) as exc:
        print(f"ERROR: Manifest invalido: {exc}")
        return 1

    if args.solo_verificar:
        return _verificar_clips_existentes(manifest, args.dir_clips)

    if shutil.which("ffmpeg") is None:
        print("ERROR: No se encontro 'ffmpeg' en PATH.")
        return 2

    repo_fuente = args.repo_fuente if args.repo_fuente is not None else Path(manifest["fuente"]["repo_path"])
    dir_audios = repo_fuente / manifest["fuente"]["dir_audios"]

    # Verificar primero integridad de todos los WAV fuente (solo lectura)
    for clip in manifest["clips"]:
        ruta_wav = dir_audios / f"{clip['entrevista']}.wav"
        if not ruta_wav.is_file():
            print(f"ERROR: Falta WAV fuente: {ruta_wav}")
            return 1
        sha_actual = sha256_archivo(ruta_wav)
        if sha_actual != clip["sha256_wav"]:
            print(
                f"ERROR de integridad en {clip['clip_id']} ({ruta_wav.name}): "
                "sha256_wav cambio respecto al manifest."
            )
            return 1

    fmt = manifest["parametros"]["formato_clip"]
    canales = int(fmt["canales"])
    frecuencia_hz = int(fmt["frecuencia_hz"])
    bitrate_kbps = int(fmt["bitrate_kbps"])

    args.dir_clips.mkdir(parents=True, exist_ok=True)
    zip_salida = args.zip_salida if args.zip_salida is not None else (args.dir_clips / "clips_piloto.zip")
    zip_salida.parent.mkdir(parents=True, exist_ok=True)

    rutas_mp3: list[Path] = []
    for idx, clip in enumerate(manifest["clips"], start=1):
        ruta_wav = dir_audios / f"{clip['entrevista']}.wav"
        ruta_mp3 = args.dir_clips / clip["archivo_clip"]
        try:
            _recortar_clip_ffmpeg(
                ruta_wav=ruta_wav,
                ruta_mp3=ruta_mp3,
                inicio_s=float(clip["inicio_s"]),
                duracion_s=float(clip["duracion_s"]),
                canales=canales,
                frecuencia_hz=frecuencia_hz,
                bitrate_kbps=bitrate_kbps,
            )
        except RuntimeError as exc:
            print(f"ERROR de recorte: {exc}")
            return 2

        clip["sha256_clip"] = sha256_archivo(ruta_mp3)
        rutas_mp3.append(ruta_mp3)
        print(f"[{idx}/{len(manifest['clips'])}] Recortado {clip['archivo_clip']} ({clip['duracion_s']:.2f} s)")

    # Confirmar que sha256_manifest canonico permanece intacto
    if sha256_manifest_canonico(manifest) != manifest["sha256_manifest"]:
        print("ERROR interno: sha256_manifest cambio inesperadamente.")
        return 1

    with args.manifest.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    with zipfile.ZipFile(zip_salida, "w", compression=zipfile.ZIP_STORED) as zf:
        for mp3 in rutas_mp3:
            zf.write(mp3, arcname=mp3.name)

    tamano_mb = zip_salida.stat().st_size / (1024.0 * 1024.0)
    print("Recorte y empaquetado finalizados correctamente.")
    print(f"ZIP generado: {zip_salida} ({tamano_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

