"""Pruebas de esquemas, hashes, edicion de turnos y evaluacion end-to-end."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

_ETAPA_DIR = Path(__file__).resolve().parents[1]
if str(_ETAPA_DIR) not in sys.path:
    sys.path.insert(0, str(_ETAPA_DIR))

from app.estado_anotacion import (
    acumular_tiempo_clip,
    construir_payload_exportacion,
    crear_estado_inicial,
    dividir_turno_en_indices,
    dividir_turno_en_marcador,
    dividir_turno_en_palabra,
    eliminar_turno,
    importar_y_fusionar_anotacion,
    unir_con_anterior,
)
from core.hashes import sha256_bytes, sha256_manifest_canonico
from core.validacion_esquemas import EsquemaInvalidoError, validar_anotacion, validar_manifest
from metricas.calcular_metricas import ejecutar_evaluacion


def test_sha256_manifest_invariante_a_sha256_clip() -> None:
    manifest = {
        "version_esquema": "1.0",
        "etapa": "ETAPA_1_speech2textDi",
        "fase": "piloto",
        "semilla": 20261119,
        "fuente": {"repo_path": "/tmp/x", "dir_diario": "Resultados/Diario", "dir_audios": "Resultados/Audios"},
        "parametros": {"duracion_clip_s": 60.0},
        "clips": [
            {
                "clip_id": "P001",
                "orden_anotacion": 1,
                "entrevista": "1_1_keiko",
                "candidato_cid": 1,
                "candidato_slug": "1_keiko",
                "estrato": "B",
                "inicio_s": 0.0,
                "fin_s": 60.0,
                "sha256_wav": "a" * 64,
                "sha256_json": "b" * 64,
                "archivo_clip": "P001.mp3",
                "sha256_clip": None,
                "precarga_ui": [{"turno_id": 1, "hablante": "H1", "texto": "Hola mundo"}],
            }
        ],
        "sha256_manifest": "",
    }
    h1 = sha256_manifest_canonico(manifest)
    manifest["sha256_manifest"] = h1
    validar_manifest(manifest, verificar_hash=True)

    manifest_con_clip = copy.deepcopy(manifest)
    manifest_con_clip["clips"][0]["sha256_clip"] = "c" * 64
    assert sha256_manifest_canonico(manifest_con_clip) == h1
    validar_manifest(manifest_con_clip, verificar_hash=True)


def test_edicion_turnos_y_roundtrip_export_import() -> None:
    turnos = [{"turno_id": 1, "hablante": "H1", "texto": "Pregunta. || Respuesta larga."}]
    div = dividir_turno_en_marcador(turnos, 0)
    assert len(div) == 2
    assert div[0] == {"turno_id": 1, "hablante": "H1", "texto": "Pregunta."}
    assert div[1] == {"turno_id": 2, "hablante": "H2", "texto": "Respuesta larga."}

    div_pal = dividir_turno_en_palabra(div, 1, 1)
    assert len(div_pal) == 3
    assert div_pal[1]["texto"] == "Respuesta"
    assert div_pal[2]["texto"] == "larga."

    unido = unir_con_anterior(div_pal, 2)
    assert len(unido) == 2
    assert unido[1]["texto"] == "Respuesta larga."

    reducido = eliminar_turno(unido, 1)
    assert len(reducido) == 1

    # Division en 3 cuadros cuando hay una interrupcion al medio (indices y marcadores)
    turno_largo = [
        {"turno_id": 1, "hablante": "H1", "texto": "Vamos a hacer pero con que plata cinco hospitales"}
    ]
    triple_idx = dividir_turno_en_indices(turno_largo, 0, [3, 7])
    assert len(triple_idx) == 3
    assert [t["hablante"] for t in triple_idx] == ["H1", "H2", "H1"]
    assert [t["texto"] for t in triple_idx] == [
        "Vamos a hacer",
        "pero con que plata",
        "cinco hospitales",
    ]

    turno_mk = [
        {"turno_id": 1, "hablante": "H1", "texto": "Vamos a hacer || pero con que plata || cinco hospitales"}
    ]
    triple_mk = dividir_turno_en_marcador(turno_mk, 0)
    assert triple_mk == triple_idx

    entrada = {"tiempo_anotacion_s": 10.0}
    acumular_tiempo_clip(entrada, 2000.0, tope_s=900.0)
    assert entrada["tiempo_anotacion_s"] == 910.0


def test_rechazo_hash_manifest_distinto_y_validacion_anotacion() -> None:
    ruta_manifest = _ETAPA_DIR / "muestreo" / "manifest_piloto.json"
    with ruta_manifest.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    validar_manifest(manifest, verificar_hash=True)

    # Verificar estructura del piloto real
    assert len(manifest["clips"]) == 24
    assert sum(1 for c in manifest["clips"] if c["estrato"] == "B") == 16
    assert sum(1 for c in manifest["clips"] if c["estrato"] == "A") == 8
    # 3 entrevistas distintas por candidato
    for cid in range(1, 9):
        c_clips = [c for c in manifest["clips"] if c["candidato_cid"] == cid]
        assert len(c_clips) == 3
        assert len({c["entrevista"] for c in c_clips}) == 3

    estado = crear_estado_inicial(manifest)
    for cid in estado:
        estado[cid]["estado"] = "completo"
    _, json_str = construir_payload_exportacion(manifest, "jd", estado)
    restaurado, anot = importar_y_fusionar_anotacion(json_str, manifest)
    assert anot == "jd"
    assert len(restaurado) == 24

    # Alterar sha256_manifest debe lanzar EsquemaInvalidoError
    bad_payload = json.loads(json_str)
    bad_payload["sha256_manifest"] = "0" * 64
    with pytest.raises(EsquemaInvalidoError):
        validar_anotacion(bad_payload, manifest, exigir_todos_terminados=True)


def test_evaluacion_end_to_end_con_fixture_sintetico(tmp_path: Path) -> None:
    repo = tmp_path / "repo_fuente"
    (repo / "Resultados" / "Audios").mkdir(parents=True)
    (repo / "Resultados" / "Diario").mkdir(parents=True)

    wav_bytes = b"RIFF_DUMMY_WAV"
    wav_path = repo / "Resultados" / "Audios" / "1_1_keiko.wav"
    wav_path.write_bytes(wav_bytes)

    diario_obj = {
        "segments": [
            {
                "start": 0.0,
                "end": 10.0,
                "speaker": "SPEAKER_00",
                "avg_logprob": -0.15,
                "text": "Proponemos 10 hospitales.",
                "words": [
                    {"word": "Proponemos", "start": 0.2, "end": 1.0, "score": 0.9, "speaker": "SPEAKER_00"},
                    {"word": "10"},
                    {"word": "hospitales.", "start": 1.5, "end": 2.4, "score": 0.88, "speaker": "SPEAKER_00"},
                ],
            }
        ]
    }
    json_path = repo / "Resultados" / "Diario" / "1_1_keiko.json"
    json_bytes = json.dumps(diario_obj).encode("utf-8")
    json_path.write_bytes(json_bytes)

    manifest = {
        "version_esquema": "1.0",
        "etapa": "ETAPA_1_speech2textDi",
        "fase": "piloto",
        "semilla": 20261119,
        "fuente": {"repo_path": str(repo), "dir_diario": "Resultados/Diario", "dir_audios": "Resultados/Audios"},
        "parametros": {"duracion_clip_s": 60.0},
        "clips": [
            {
                "clip_id": "P001",
                "orden_anotacion": 1,
                "entrevista": "1_1_keiko",
                "candidato_cid": 1,
                "candidato_slug": "1_keiko",
                "estrato": "B",
                "inicio_s": 0.0,
                "fin_s": 10.0,
                "sha256_wav": sha256_bytes(wav_bytes),
                "sha256_json": sha256_bytes(json_bytes),
                "archivo_clip": "P001.mp3",
                "sha256_clip": None,
                "precarga_ui": [{"turno_id": 1, "hablante": "H1", "texto": "Proponemos 10 hospitales."}],
            }
        ],
        "sha256_manifest": "",
    }
    manifest["sha256_manifest"] = sha256_manifest_canonico(manifest)

    ruta_manifest = tmp_path / "manifest.json"
    ruta_manifest.write_text(json.dumps(manifest), encoding="utf-8")

    estado = crear_estado_inicial(manifest)
    estado["P001"]["estado"] = "completo"
    estado["P001"]["tiempo_anotacion_s"] = 45.0
    _, anot_str = construir_payload_exportacion(manifest, "tester", estado)
    ruta_anot = tmp_path / "anot.json"
    ruta_anot.write_text(anot_str, encoding="utf-8")

    df, resumen = ejecutar_evaluacion(
        ruta_manifest=ruta_manifest,
        ruta_anotacion=ruta_anot,
        n_bootstrap=100,
    )
    assert len(df) == 1
    assert df.iloc[0]["WER"] == 0.0
    assert df.iloc[0]["WDER_seg"] == 0.0
    assert resumen["trazabilidad"]["fuentes_validadas_ok"] is True

    # Si cambia el JSON fuente en repo, debe fallar por obsolescencia
    json_path.write_bytes(b'{"segments": []}')
    with pytest.raises(ValueError, match="obsoletos"):
        ejecutar_evaluacion(ruta_manifest=ruta_manifest, ruta_anotacion=ruta_anot)

