"""Pruebas unitarias para core/io_diario.py (interpolacion, herencia y vistas)."""

from __future__ import annotations

from pathlib import Path
import sys

_ETAPA_DIR = Path(__file__).resolve().parents[1]
if str(_ETAPA_DIR) not in sys.path:
    sys.path.insert(0, str(_ETAPA_DIR))

from core.io_diario import (
    agrupar_en_turnos,
    ajustar_bordes_a_huecos,
    detectar_cambios_turno_segmento,
    extraer_palabras_diario,
    interpolar_palabras_segmento,
    recortar_palabras_clip,
)


def _diario_sintetico() -> dict:
    return {
        "segments": [
            {
                "start": 0.0,
                "end": 5.0,
                "speaker": "SPEAKER_01",
                "avg_logprob": -0.1,
                "text": "Unos 10 años al 55%, gracias.",
                "words": [
                    {"word": "Unos", "start": 0.2, "end": 0.6, "score": 0.9, "speaker": "SPEAKER_01"},
                    {"word": "10"},
                    {"word": "años", "start": 1.2, "end": 1.8, "score": 0.8, "speaker": "SPEAKER_01"},
                    {"word": "al", "start": 1.9, "end": 2.1, "score": 0.9, "speaker": "SPEAKER_01"},
                    {"word": "55%,"},
                    {"word": "gracias.", "start": 3.2, "end": 4.0, "score": 0.85, "speaker": "SPEAKER_02"},
                ],
            },
            {
                "start": 5.5,
                "end": 8.0,
                "speaker": "SPEAKER_02",
                "avg_logprob": -0.2,
                "text": "De acuerdo.",
                "words": [
                    {"word": "De", "start": 5.6, "end": 5.9, "score": 0.95, "speaker": "SPEAKER_02"},
                    {"word": "acuerdo.", "start": 6.0, "end": 6.8, "score": 0.92, "speaker": "SPEAKER_02"},
                ],
            },
        ]
    }


def test_interpola_numeros_sin_descartar() -> None:
    diario = _diario_sintetico()
    pals_seg = interpolar_palabras_segmento(diario["segments"][0], vista="segment")
    assert [p.word for p in pals_seg] == ["Unos", "10", "años", "al", "55%,", "gracias."]
    # La palabra '10' debe quedar interpolada en [0.6, 1.2]
    assert pals_seg[1].start == 0.6
    assert pals_seg[1].end == 1.2
    # La palabra '55%,' en [2.1, 3.2]
    assert pals_seg[4].start == 2.1
    assert pals_seg[4].end == 3.2


def test_vistas_segment_vs_word_y_herencia_speaker() -> None:
    diario = _diario_sintetico()
    pals_seg = extraer_palabras_diario(diario, vista="segment")
    pals_word = extraer_palabras_diario(diario, vista="word")

    # En vista segment, todo el segmento 0 es SPEAKER_01
    assert [p.speaker for p in pals_seg[:6]] == ["SPEAKER_01"] * 6
    # En vista word, '55%,' hereda de 'al' (SPEAKER_01), mientras 'gracias.' es SPEAKER_02
    assert pals_word[4].speaker == "SPEAKER_01"
    assert pals_word[5].speaker == "SPEAKER_02"


def test_cambios_turno_y_agrupacion() -> None:
    diario = _diario_sintetico()
    cambios = detectar_cambios_turno_segmento(diario)
    assert len(cambios) == 1
    assert 5.0 <= cambios[0] <= 5.5

    pals = extraer_palabras_diario(diario, vista="segment")
    recorte = recortar_palabras_clip(pals, 0.0, 8.0)
    turnos = agrupar_en_turnos(recorte, mapear_genericos=True)
    assert len(turnos) == 2
    assert turnos[0]["hablante"] == "H1"
    assert turnos[1]["hablante"] == "H2"


def test_ajuste_bordes_no_corta_palabra() -> None:
    diario = _diario_sintetico()
    pals = extraer_palabras_diario(diario, vista="segment")
    # 3.6 cae en medio de 'gracias.' [3.2, 4.0]
    ini, fin = ajustar_bordes_a_huecos(0.0, 3.6, pals, duracion_total_s=8.0, ajuste_max_s=2.0)
    for p in pals:
        assert not (p.start + 0.01 < fin < p.end - 0.01)
    assert ini == 0.0

