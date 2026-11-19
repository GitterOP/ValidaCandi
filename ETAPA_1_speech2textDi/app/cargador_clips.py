"""Carga y verificacion SHA-256 de clips de audio para la app de anotacion."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
from typing import Any
import urllib.request
import zipfile

_ETAPA_DIR = Path(__file__).resolve().parents[1]
if str(_ETAPA_DIR) not in sys.path:
    sys.path.insert(0, str(_ETAPA_DIR))

from core.hashes import sha256_archivo
from core.validacion_esquemas import validar_manifest

RUTA_MANIFEST_DEFAULT = _ETAPA_DIR / "muestreo" / "manifest_piloto.json"
DIR_CLIPS_LOCAL_DEFAULT = _ETAPA_DIR / "muestreo" / "clips"


def cargar_manifest_piloto(ruta_manifest: Path = RUTA_MANIFEST_DEFAULT) -> dict[str, Any]:
    """Carga y valida ``manifest_piloto.json`` desde el repositorio."""
    if not ruta_manifest.is_file():
        raise FileNotFoundError(f"No se encontro el manifest del piloto: {ruta_manifest}")
    with ruta_manifest.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    validar_manifest(manifest, verificar_hash=True)
    return manifest


def verificar_directorio_clips(
    manifest: dict[str, Any],
    dir_clips: Path,
) -> tuple[bool, list[str]]:
    """Verifica que todos los MP3 del manifest existan y coincidan en SHA-256."""
    if not dir_clips.is_dir():
        return False, [f"No existe el directorio de clips: {dir_clips}"]

    errores: list[str] = []
    for clip in manifest["clips"]:
        cid = clip["clip_id"]
        nombre = clip["archivo_clip"]
        esperado = clip.get("sha256_clip")
        ruta = dir_clips / nombre
        if not ruta.is_file():
            errores.append(f"{cid}: falta {nombre}")
            continue
        if esperado:
            actual = sha256_archivo(ruta)
            if actual != esperado:
                errores.append(
                    f"{cid}: hash SHA-256 no coincide (esperado {esperado[:10]}..., actual {actual[:10]}...)"
                )
    return len(errores) == 0, errores


def extraer_zip_y_verificar(
    zip_bytes: bytes,
    manifest: dict[str, Any],
    dir_destino: Path,
) -> tuple[bool, list[str]]:
    """Extrae los MP3 de un ZIP en ``dir_destino`` y verifica todos los SHA-256."""
    dir_destino.mkdir(parents=True, exist_ok=True)
    archivos_esperados = {c["archivo_clip"] for c in manifest["clips"]}

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                nombre_base = Path(info.filename).name
                if nombre_base in archivos_esperados:
                    destino = dir_destino / nombre_base
                    with zf.open(info, "r") as src, destino.open("wb") as dst:
                        dst.write(src.read())
    except zipfile.BadZipFile:
        return False, ["El archivo proporcionado no es un ZIP valido."]

    return verificar_directorio_clips(manifest, dir_destino)


def descargar_clips_desde_url(
    url: str,
    token: str | None,
    manifest: dict[str, Any],
    dir_destino: Path,
) -> tuple[bool, list[str]]:
    """Descarga un paquete ZIP de clips desde una URL privada y lo verifica."""
    # Si ya esta en cache efimera y es valido, reutilizarlo
    ok_previo, _ = verificar_directorio_clips(manifest, dir_destino)
    if ok_previo:
        return True, []

    headers = {"User-Agent": "ValidaCandi/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            zip_bytes = resp.read()
    except Exception as exc:
        return False, [f"Error descargando clips desde URL configurada: {exc}"]

    return extraer_zip_y_verificar(zip_bytes, manifest, dir_destino)

