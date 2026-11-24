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

from core.hashes import sha256_archivo, sha256_bytes
from core.validacion_esquemas import validar_manifest

RUTA_MANIFEST_DEFAULT = _ETAPA_DIR / "muestreo" / "manifest_piloto.json"
DIR_MUESTREO_DEFAULT = _ETAPA_DIR / "muestreo"
DIR_CLIPS_LOCAL_DEFAULT = _ETAPA_DIR / "muestreo" / "clips"

_ORDEN_FASES = {
    "ampliacion_medio": 0,
    "ampliacion_seguro": 1,
    "piloto": 2,
}


def cargar_manifest_piloto(ruta_manifest: Path = RUTA_MANIFEST_DEFAULT) -> dict[str, Any]:
    """Carga y valida un archivo de manifest desde el repositorio."""
    if not ruta_manifest.is_file():
        raise FileNotFoundError(f"No se encontro el manifest: {ruta_manifest}")
    with ruta_manifest.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    validar_manifest(manifest, verificar_hash=True)
    return manifest


def descubrir_manifests_disponibles(
    dir_muestreo: Path = DIR_MUESTREO_DEFAULT,
) -> list[dict[str, Any]]:
    """Descubre todos los manifests validos en ``muestreo/`` priorizando el lote activo."""
    if not dir_muestreo.is_dir():
        return []
    encontrados: list[dict[str, Any]] = []
    for ruta in sorted(dir_muestreo.glob("manifest_*.json")):
        try:
            m = cargar_manifest_piloto(ruta)
            encontrados.append(m)
        except Exception:
            continue
    encontrados.sort(key=lambda m: (_ORDEN_FASES.get(str(m.get("fase", "")), 99), str(m.get("fase", ""))))
    return encontrados


def autodetectar_manifest_desde_zip(
    zip_bytes: bytes,
    manifests: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Identifica que manifest coincide con los MP3 contenidos en un ZIP."""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            nombres_zip = {
                Path(info.filename).name
                for info in zf.infolist()
                if not info.is_dir() and info.filename.lower().endswith(".mp3")
            }
            if not nombres_zip:
                return None
            # Intentar match exacto por conjunto de archivos y validar al menos 1 hash
            for m in manifests:
                esperados = {c["archivo_clip"] for c in m["clips"]}
                if esperados.issubset(nombres_zip):
                    primer_clip = m["clips"][0]
                    if primer_clip.get("sha256_clip"):
                        for info in zf.infolist():
                            if Path(info.filename).name == primer_clip["archivo_clip"]:
                                with zf.open(info, "r") as fh:
                                    if sha256_bytes(fh.read()) == primer_clip["sha256_clip"]:
                                        return m
                    else:
                        return m
    except zipfile.BadZipFile:
        return None
    return None


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
