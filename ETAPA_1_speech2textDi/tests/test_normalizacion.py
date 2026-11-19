"""Pruebas unitarias de normalizacion determinista de texto espanol."""

from __future__ import annotations

from pathlib import Path
import sys

_ETAPA_DIR = Path(__file__).resolve().parents[1]
if str(_ETAPA_DIR) not in sys.path:
    sys.path.insert(0, str(_ETAPA_DIR))

from core.normalizacion import normalizar_texto


def test_porcentajes_y_miles_unificados() -> None:
    r1 = normalizar_texto("Subiremos el 15% y 10.000 millones.")
    r2 = normalizar_texto("subiremos el 15 por ciento y 10,000 millones")
    assert r1.texto == r2.texto
    assert r1.texto == "subiremos el 15 porcentaje y 10000 millones"


def test_preserva_enie_y_quita_tildes() -> None:
    res = normalizar_texto("El Perú cambiará en el año 2026 con cañamo.")
    assert res.texto == "el peru cambiara en el año 2026 con cañamo"


def test_numeros_verbales_y_articulo_un() -> None:
    res = normalizar_texto("Necesitamos un pais con veinticinco hospitales y ciento cincuenta escuelas.")
    assert res.texto == "necesitamos un pais con 25 hospitales y 150 escuelas"

    res_mil = normalizar_texto("En dos mil veintiseis habra un millon de empleos.")
    assert res_mil.texto == "en 2026 habra 1 millon de empleos"

    res_seq = normalizar_texto("uno dos tres cuatro")
    assert res_seq.texto == "1 2 3 4"


def test_marcadores_especiales_y_muletillas() -> None:
    res = normalizar_texto("Eh, nosotros [inaudible] queremos mmm salud [solapado] y [musica] paz.")
    assert res.n_inaudible == 1
    assert res.n_solapado == 1
    assert res.n_musica == 1
    assert res.n_ruido == 0
    assert res.texto == "nosotros queremos salud y paz"
