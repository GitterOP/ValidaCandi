"""Pruebas unitarias con soluciones analiticas conocidas para metricas e inferencia."""

from __future__ import annotations

import math
from pathlib import Path
import sys

import pandas as pd

_ETAPA_DIR = Path(__file__).resolve().parents[1]
if str(_ETAPA_DIR) not in sys.path:
    sys.path.insert(0, str(_ETAPA_DIR))

from metricas.calculo_asr import calcular_metricas_asr_clip
from metricas.calculo_diarizacion import (
    calcular_cpwer,
    calcular_fragmentacion_lt10,
    calcular_metricas_diarizacion_clip,
    calcular_wder,
)
from metricas.inferencia import bootstrap_metricas, dimensionar_muestra_final
from reporte.generar_reporte import construir_markdown_informe


def test_asr_perfecto_y_entidades() -> None:
    turnos_ref = [
        {"turno_id": 1, "hablante": "H1", "texto": "La ONPE reporto 15% en Lima."}
    ]
    res_ok = calcular_metricas_asr_clip(turnos_ref, "La ONPE reporto 15% en Lima.")
    assert res_ok["WER"] == 0.0
    assert res_ok["CER"] == 0.0
    assert res_ok["entidades_ref"] == 3
    assert res_ok["entidades_err"] == 0

    res_err = calcular_metricas_asr_clip(turnos_ref, "La oficina reporto 50% en Lima.")
    assert res_err["S"] == 2
    assert res_err["entidades_ref"] == 3
    assert res_err["entidades_err"] == 2
    assert math.isclose(res_err["tasa_err_entidades"], 2 / 3, rel_tol=1e-6)


def test_diarizacion_invariante_a_etiquetas_y_sobresegmentacion() -> None:
    turnos_ref = [
        {"turno_id": 1, "hablante": "H1", "texto": "uno dos tres cuatro"},
        {"turno_id": 2, "hablante": "H2", "texto": "cinco seis siete ocho"},
    ]
    turnos_hip_perm = [
        {"turno_id": 1, "hablante": "SPEAKER_07", "texto": "uno dos tres cuatro"},
        {"turno_id": 2, "hablante": "SPEAKER_02", "texto": "cinco seis siete ocho"},
    ]
    m_perm = calcular_metricas_diarizacion_clip(turnos_ref, turnos_hip_perm, turnos_hip_perm)
    assert m_perm["WDER_seg"] == 0.0
    assert m_perm["cpWER_seg"] == 0.0
    assert m_perm["delta_hablantes_seg"] == 0

    # Caso clasico de sobresegmentacion: 1 hablante partido en 2 iguales
    ref_1 = [{"turno_id": 1, "hablante": "H1", "texto": "uno dos tres cuatro"}]
    hip_2 = [
        {"turno_id": 1, "hablante": "SPEAKER_00", "texto": "uno dos"},
        {"turno_id": 2, "hablante": "SPEAKER_01", "texto": "tres cuatro"},
    ]
    m_over = calcular_metricas_diarizacion_clip(ref_1, hip_2, hip_2)
    assert m_over["delta_hablantes_seg"] == 1
    assert math.isclose(m_over["WDER_seg"], 0.5, rel_tol=1e-6)
    # En cpWER, SPEAKER_00 coincide con 'uno dos' (2 borrados) y SPEAKER_01 queda contra '' (2 inserciones) -> 4/4 = 1.0
    assert math.isclose(m_over["cpWER_seg"], 1.0, rel_tol=1e-6)


def test_fragmentacion_interna_lt10() -> None:
    turnos = [
        {"turno_id": 1, "hablante": "H1", "texto": "corte borde inicial"},  # borde: excluido
        {"turno_id": 2, "hablante": "H2", "texto": "solo cuatro palabras aqui"},  # interno <10: 4 pal
        {"turno_id": 3, "hablante": "H1", "texto": " ".join(["palabra"] * 12)},  # interno >=10: 12 pal
        {"turno_id": 4, "hablante": "H2", "texto": "corte final"},  # borde: excluido
    ]
    frag = calcular_fragmentacion_lt10(turnos)
    assert frag["palabras_frag_lt10"] == 4
    assert math.isclose(frag["tasa_frag_lt10"], 4 / 21, rel_tol=1e-6)


def test_dimensionamiento_tabla_guia_sdd() -> None:
    # Con n_B=16 y s=0.10, chi2(0.20, df=15)=10.30696 -> s_UCL=0.120637 -> n_B=63 para E=0.03
    base = [0.0] * 8 + [0.19364916731037085] * 8
    dim = dimensionar_muestra_final(base, margen_objetivo_e=0.03, tiempo_medio_clip_s=300.0)
    assert dim["n_B_piloto"] == 16
    assert math.isclose(dim["s_B_WER_clip"], 0.10, abs_tol=1e-4)
    assert math.isclose(dim["s_UCL_80"], 0.120637, abs_tol=1e-4)
    assert dim["n_B_recomendado"] == 63


def test_bootstrap_reproducible_y_reporte() -> None:
    df = pd.DataFrame(
        [
            {
                "clip_id": "P001",
                "candidato_slug": "1_keiko",
                "estrato": "B",
                "estado": "completo",
                "N_ref": 100,
                "N_hip": 100,
                "S": 5,
                "D": 2,
                "I": 3,
                "H": 93,
                "WER": 0.10,
                "CER": 0.05,
                "entidades_ref": 5,
                "entidades_err": 1,
                "pares_alineados_seg": 98,
                "err_spk_seg": 4,
                "WDER_seg": 4 / 98,
                "cpWER_errores_seg": 12,
                "cpWER_seg": 0.12,
                "delta_hablantes_seg": 0,
                "pares_alineados_word": 98,
                "err_spk_word": 3,
                "WDER_word": 3 / 98,
                "cpWER_errores_word": 11,
                "palabras_frag_lt10": 0,
                "score_medio": 0.85,
                "avg_logprob_medio": -0.2,
            },
            {
                "clip_id": "P002",
                "candidato_slug": "2_rla",
                "estrato": "B",
                "estado": "completo",
                "N_ref": 100,
                "N_hip": 100,
                "S": 2,
                "D": 1,
                "I": 1,
                "H": 97,
                "WER": 0.04,
                "CER": 0.02,
                "entidades_ref": 5,
                "entidades_err": 0,
                "pares_alineados_seg": 99,
                "err_spk_seg": 0,
                "WDER_seg": 0.0,
                "cpWER_errores_seg": 4,
                "cpWER_seg": 0.04,
                "delta_hablantes_seg": 1,
                "pares_alineados_word": 99,
                "err_spk_word": 0,
                "WDER_word": 0.0,
                "cpWER_errores_word": 4,
                "palabras_frag_lt10": 5,
                "score_medio": 0.92,
                "avg_logprob_medio": -0.1,
            },
        ]
    )
    b1 = bootstrap_metricas(df, n_bootstrap=500, semilla=20261119)
    b2 = bootstrap_metricas(df, n_bootstrap=500, semilla=20261119)
    assert b1 == b2
    assert math.isclose(b1["WER"]["puntual"], 0.07, abs_tol=1e-6)

    resumen_mock = {
        "fecha_calculo": "2026-11-19T16:00:00-05:00",
        "parcial": False,
        "trazabilidad": {
            "sha256_manifest": "a" * 64,
            "archivo_anotacion": "gold/test.json",
            "sha256_anotacion": "b" * 64,
            "version_guia": "1.0",
            "fuentes_validadas_ok": True,
            "semilla_bootstrap": 20261119,
            "n_bootstrap": 500,
        },
        "cobertura": {
            "n_total_manifest": 2,
            "n_completos": 2,
            "n_no_anotables": 0,
            "n_estrato_b_eval": 2,
            "n_estrato_a_eval": 0,
            "tiempo_medio_clip_s": 250.0,
            "tiempo_total_h": 0.14,
        },
        "metricas_globales": b1,
        "hablantes_seg": {
            "delta_medio": 0.5,
            "delta_mediana": 0.5,
            "pct_exacto": 0.5,
            "pct_sobresegmentado": 0.5,
            "pct_subsegmentado": 0.0,
        },
        "por_estrato": {"B": b1, "A": {}},
        "por_candidato_exploratorio": {
            "1_keiko": {"n_eval": 1, "WER": 0.10, "WDER_seg": 0.04, "cpWER_seg": 0.12, "delta_hablantes_medio": 0.0}
        },
        "correlacion_confianza": {
            "spearman_score_vs_WER": {"rho": None, "p_value": None},
            "spearman_logprob_vs_WER": {"rho": None, "p_value": None},
        },
        "dimensionamiento_muestra_final": dimensionar_muestra_final([0.10, 0.04]),
    }
    md = construir_markdown_informe(df, resumen_mock)
    assert "## 1. Ficha tecnica y trazabilidad" in md
    assert "## 6. Dimensionamiento de la muestra final y cierre del piloto" in md
