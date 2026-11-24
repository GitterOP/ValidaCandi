"""Pruebas para el diseno muestral anidado (Piloto + Medio + Seguro) y consolidacion."""

from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

_ETAPA_DIR = Path(__file__).resolve().parents[1]
if str(_ETAPA_DIR) not in sys.path:
    sys.path.insert(0, str(_ETAPA_DIR))

from app.cargador_clips import autodetectar_manifest_desde_zip, descubrir_manifests_disponibles
from app.estado_anotacion import construir_payload_exportacion, crear_estado_inicial
from core.hashes import sha256_bytes, sha256_manifest_canonico
from core.validacion_esquemas import (
    EsquemaInvalidoError,
    validar_manifest,
    verificar_sin_solapamiento_manifests,
)
from metricas.calcular_metricas import ejecutar_evaluacion


def test_manifests_reales_anidados_sin_solapamiento() -> None:
    ruta_p = _ETAPA_DIR / "muestreo" / "manifest_piloto.json"
    ruta_m = _ETAPA_DIR / "muestreo" / "manifest_ampliacion_medio.json"
    ruta_s = _ETAPA_DIR / "muestreo" / "manifest_ampliacion_seguro.json"

    m_p = json.loads(ruta_p.read_text(encoding="utf-8"))
    m_m = json.loads(ruta_m.read_text(encoding="utf-8"))
    m_s = json.loads(ruta_s.read_text(encoding="utf-8"))

    for m in (m_p, m_m, m_s):
        validar_manifest(m, verificar_hash=True)

    assert len(m_p["clips"]) == 24
    assert len(m_m["clips"]) == 32
    assert len(m_s["clips"]) == 32

    # Verificar linaje exacto
    assert m_m["linaje_muestreo"]["manifests_previos"][0]["sha256_manifest"] == m_p["sha256_manifest"]
    assert m_s["linaje_muestreo"]["manifests_previos"][0]["sha256_manifest"] == m_p["sha256_manifest"]
    assert m_s["linaje_muestreo"]["manifests_previos"][1]["sha256_manifest"] == m_m["sha256_manifest"]

    # Verificar cero solapamiento con colchon de 30 s en los 88 clips
    verificar_sin_solapamiento_manifests([m_p, m_m, m_s], colchon_s=30.0)

    # Verificar conteo por candidato y cobertura de las 80 entrevistas
    todos = m_p["clips"] + m_m["clips"] + m_s["clips"]
    entrevistas_unicas = {c["entrevista"] for c in todos}
    assert len(entrevistas_unicas) == 80

    for cid in range(1, 9):
        c_clips = [c for c in todos if c["candidato_cid"] == cid]
        assert len(c_clips) == 11
        assert sum(1 for c in c_clips if c["estrato"] == "B") == 7
        assert sum(1 for c in c_clips if c["estrato"] == "A") == 4


def test_rechaza_solapamiento_en_misma_entrevista() -> None:
    m1 = {
        "clips": [
            {"clip_id": "P001", "entrevista": "1_1_keiko", "inicio_s": 100.0, "fin_s": 160.0}
        ]
    }
    m2_solapado = {
        "clips": [
            {"clip_id": "M001", "entrevista": "1_1_keiko", "inicio_s": 150.0, "fin_s": 210.0}
        ]
    }
    with pytest.raises(EsquemaInvalidoError, match="Solapamiento"):
        verificar_sin_solapamiento_manifests([m1, m2_solapado], colchon_s=0.0)

    m2_cerca = {
        "clips": [
            {"clip_id": "M001", "entrevista": "1_1_keiko", "inicio_s": 175.0, "fin_s": 235.0}
        ]
    }
    with pytest.raises(EsquemaInvalidoError, match="Solapamiento"):
        verificar_sin_solapamiento_manifests([m1, m2_cerca], colchon_s=30.0)

    # A 40 s de distancia (> 30 s) si pasa
    m2_lejos = {
        "clips": [
            {"clip_id": "M001", "entrevista": "1_1_keiko", "inicio_s": 200.0, "fin_s": 260.0}
        ]
    }
    verificar_sin_solapamiento_manifests([m1, m2_lejos], colchon_s=30.0)


def test_autodetectar_manifest_desde_zip() -> None:
    manifests = descubrir_manifests_disponibles(_ETAPA_DIR / "muestreo")
    m_medio = next(m for m in manifests if m["fase"] == "ampliacion_medio")

    # Simular ZIP con nombres del Lote Medio (tomando hashes reales del primer clip si existe)
    buf = io.BytesIO()
    ruta_mp3_real = _ETAPA_DIR / "muestreo" / "clips" / m_medio["clips"][0]["archivo_clip"]
    with zipfile.ZipFile(buf, "w") as zf:
        for idx, clip in enumerate(m_medio["clips"]):
            if idx == 0 and ruta_mp3_real.is_file():
                zf.writestr(clip["archivo_clip"], ruta_mp3_real.read_bytes())
            else:
                zf.writestr(clip["archivo_clip"], b"dummy")

    detectado = autodetectar_manifest_desde_zip(buf.getvalue(), manifests)
    assert detectado is not None
    assert detectado["sha256_manifest"] == m_medio["sha256_manifest"]


def test_evaluacion_consolidada_multilote(tmp_path: Path) -> None:
    repo = tmp_path / "repo_fuente"
    (repo / "Resultados" / "Audios").mkdir(parents=True)
    (repo / "Resultados" / "Diario").mkdir(parents=True)

    wav_bytes = b"RIFF_DUMMY_WAV"
    (repo / "Resultados" / "Audios" / "1_1_keiko.wav").write_bytes(wav_bytes)
    diario_obj = {
        "segments": [
            {
                "start": 0.0,
                "end": 120.0,
                "speaker": "SPEAKER_00",
                "avg_logprob": -0.1,
                "text": "Uno dos tres cuatro.",
                "words": [
                    {"word": "Uno", "start": 1.0, "end": 2.0, "score": 0.9, "speaker": "SPEAKER_00"},
                    {"word": "dos", "start": 2.1, "end": 3.0, "score": 0.9, "speaker": "SPEAKER_00"},
                    {"word": "tres", "start": 70.0, "end": 71.0, "score": 0.9, "speaker": "SPEAKER_00"},
                    {"word": "cuatro.", "start": 71.1, "end": 72.0, "score": 0.9, "speaker": "SPEAKER_00"},
                ],
            }
        ]
    }
    json_bytes = json.dumps(diario_obj).encode("utf-8")
    (repo / "Resultados" / "Diario" / "1_1_keiko.json").write_bytes(json_bytes)

    base = {
        "version_esquema": "1.0",
        "etapa": "ETAPA_1_speech2textDi",
        "semilla": 20261119,
        "fuente": {"repo_path": str(repo), "dir_diario": "Resultados/Diario", "dir_audios": "Resultados/Audios"},
        "parametros": {"duracion_clip_s": 60.0},
    }

    m1 = copy.deepcopy(base)
    m1["fase"] = "piloto"
    m1["clips"] = [
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
            "precarga_ui": [{"turno_id": 1, "hablante": "H1", "texto": "Uno dos"}],
        }
    ]
    m1["sha256_manifest"] = sha256_manifest_canonico(m1)

    m2 = copy.deepcopy(base)
    m2["fase"] = "ampliacion_medio"
    m2["clips"] = [
        {
            "clip_id": "M001",
            "orden_anotacion": 1,
            "entrevista": "1_1_keiko",
            "candidato_cid": 1,
            "candidato_slug": "1_keiko",
            "estrato": "A",
            "inicio_s": 60.0,
            "fin_s": 80.0,
            "sha256_wav": sha256_bytes(wav_bytes),
            "sha256_json": sha256_bytes(json_bytes),
            "archivo_clip": "M001.mp3",
            "sha256_clip": None,
            "precarga_ui": [{"turno_id": 1, "hablante": "H1", "texto": "tres cuatro."}],
        }
    ]
    m2["sha256_manifest"] = sha256_manifest_canonico(m2)

    r_m1, r_m2 = tmp_path / "m1.json", tmp_path / "m2.json"
    r_m1.write_text(json.dumps(m1), encoding="utf-8")
    r_m2.write_text(json.dumps(m2), encoding="utf-8")

    e1 = crear_estado_inicial(m1)
    e1["P001"]["estado"] = "completo"
    e1["P001"]["tiempo_anotacion_s"] = 30.0
    _, a1_str = construir_payload_exportacion(m1, "jd", e1)

    e2 = crear_estado_inicial(m2)
    e2["M001"]["estado"] = "completo"
    e2["M001"]["tiempo_anotacion_s"] = 40.0
    _, a2_str = construir_payload_exportacion(m2, "jd", e2)

    r_a1, r_a2 = tmp_path / "a1.json", tmp_path / "a2.json"
    r_a1.write_text(a1_str, encoding="utf-8")
    r_a2.write_text(a2_str, encoding="utf-8")

    df, resumen = ejecutar_evaluacion([r_m1, r_m2], [r_a1, r_a2], n_bootstrap=50)
    assert len(df) == 2
    assert set(df["clip_id"]) == {"P001", "M001"}
    assert resumen["cobertura"]["n_total_manifest"] == 2
    assert len(resumen["trazabilidad"]["manifests"]) == 2
