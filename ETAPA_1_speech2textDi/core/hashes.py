"""Calculo y verificacion determinista de hashes SHA-256."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_bytes(datos: bytes) -> str:
    """Calcula el hash SHA-256 hexadecimal de un bloque de bytes."""
    return hashlib.sha256(datos).hexdigest()


def sha256_archivo(ruta: Path | str, tamano_bloque: int = 1024 * 1024) -> str:
    """Calcula el SHA-256 de un archivo leyendolo por bloques.

    Args:
        ruta: Ruta al archivo en disco.
        tamano_bloque: Tamano de lectura en bytes (por defecto 1 MiB).

    Returns:
        Cadena hexadecimal de 64 caracteres.
    """
    path = Path(ruta)
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo para calcular SHA-256: {path}")

    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            bloque = fh.read(tamano_bloque)
            if not bloque:
                break
            hasher.update(bloque)
    return hasher.hexdigest()


def sha256_manifest_canonico(manifest: dict[str, Any]) -> str:
    """Calcula el hash canonico de identidad del manifest.

    Excluye los campos ``sha256_manifest`` y ``sha256_clip`` de cada clip para
    que el identificador del diseno muestral no cambie al regenerar los MP3.

    Args:
        manifest: Diccionario completo del manifest.

    Returns:
        Cadena hexadecimal SHA-256 de 64 caracteres.
    """
    copia = copy.deepcopy(manifest)
    copia.pop("sha256_manifest", None)
    clips = copia.get("clips")
    if isinstance(clips, list):
        for clip in clips:
            if isinstance(clip, dict):
                clip.pop("sha256_clip", None)

    serializado = json.dumps(
        copia,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256_bytes(serializado.encode("utf-8"))

