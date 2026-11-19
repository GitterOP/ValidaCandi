"""Calculo de metricas de diarizacion textual: WDER, cpWER, delta H y fragmentacion."""

from __future__ import annotations

import math
from typing import Any

import jiwer
import numpy as np
from scipy.optimize import linear_sum_assignment

from core.normalizacion import normalizar_texto
from core.validacion_esquemas import fusionar_turnos_consecutivos


def _expandir_turnos_a_pares(turnos: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Convierte turnos en una lista cronologica de pares (token_normalizado, hablante)."""
    pares: list[tuple[str, str]] = []
    for turno in fusionar_turnos_consecutivos(turnos):
        hab = str(turno["hablante"])
        toks = normalizar_texto(str(turno["texto"])).tokens
        for tok in toks:
            pares.append((tok, hab))
    return pares


def calcular_wder(
    pares_ref: list[tuple[str, str]],
    pares_hip: list[tuple[str, str]],
) -> dict[str, Any]:
    """Calcula WDER (Word-level Diarization Error Rate) bajo asignacion 1-a-1 optima."""
    if not pares_ref or not pares_hip:
        return {"pares_alineados": 0, "err_spk": 0, "WDER": math.nan}

    ref_str = " ".join(tok for tok, _ in pares_ref)
    hip_str = " ".join(tok for tok, _ in pares_hip)
    out = jiwer.process_words(ref_str, hip_str)

    pares_spk: list[tuple[str, str]] = []
    for chunk in out.alignments[0]:
        if chunk.type in {"equal", "substitute"}:
            n_span = chunk.ref_end_idx - chunk.ref_start_idx
            for k in range(n_span):
                spk_r = pares_ref[chunk.ref_start_idx + k][1]
                spk_h = pares_hip[chunk.hyp_start_idx + k][1]
                pares_spk.append((spk_r, spk_h))

    n_pares = len(pares_spk)
    if n_pares == 0:
        return {"pares_alineados": 0, "err_spk": 0, "WDER": math.nan}

    spks_r = sorted({sr for sr, _ in pares_spk})
    spks_h = sorted({sh for _, sh in pares_spk})
    idx_r = {s: i for i, s in enumerate(spks_r)}
    idx_h = {s: j for j, s in enumerate(spks_h)}

    matriz = np.zeros((len(spks_r), len(spks_h)), dtype=np.int64)
    for sr, sh in pares_spk:
        matriz[idx_r[sr], idx_h[sh]] += 1

    fila_ind, col_ind = linear_sum_assignment(-matriz)
    aciertos = int(matriz[fila_ind, col_ind].sum())
    err_spk = n_pares - aciertos
    return {
        "pares_alineados": n_pares,
        "err_spk": err_spk,
        "WDER": err_spk / n_pares,
    }


def _distancia_edicion_palabras(txt_a: str, txt_b: str) -> int:
    if not txt_a and not txt_b:
        return 0
    if not txt_a:
        return len(txt_b.split())
    if not txt_b:
        return len(txt_a.split())
    out = jiwer.process_words(txt_a, txt_b)
    return int(out.substitutions + out.deletions + out.insertions)


def calcular_cpwer(
    pares_ref: list[tuple[str, str]],
    pares_hip: list[tuple[str, str]],
) -> dict[str, Any]:
    """Calcula cpWER exacto mediante asignacion lineal optima de hablantes."""
    n_ref = len(pares_ref)
    if n_ref == 0:
        return {"cpWER_errores": 0, "cpWER": math.nan}

    por_ref: dict[str, list[str]] = {}
    for tok, spk in pares_ref:
        por_ref.setdefault(spk, []).append(tok)

    por_hip: dict[str, list[str]] = {}
    for tok, spk in pares_hip:
        por_hip.setdefault(spk, []).append(tok)

    textos_r = [" ".join(v) for v in por_ref.values()]
    textos_h = [" ".join(v) for v in por_hip.values()]
    k = max(len(textos_r), len(textos_h))
    textos_r.extend([""] * (k - len(textos_r)))
    textos_h.extend([""] * (k - len(textos_h)))

    costos = np.zeros((k, k), dtype=np.int64)
    for i in range(k):
        for j in range(k):
            costos[i, j] = _distancia_edicion_palabras(textos_r[i], textos_h[j])

    fila_ind, col_ind = linear_sum_assignment(costos)
    errores = int(costos[fila_ind, col_ind].sum())
    return {
        "cpWER_errores": errores,
        "cpWER": errores / n_ref,
    }


def calcular_fragmentacion_lt10(turnos_hip: list[dict[str, Any]]) -> dict[str, Any]:
    """Calcula palabras de hipotesis atrapadas en turnos internos de < 10 palabras.

    Replica el umbral de ``fragmentador_oraciones.py`` excluyendo el primer y ultimo
    turno del clip para evitar penalizar cortes artificiales en los bordes de 60 s.
    """
    fusionados = fusionar_turnos_consecutivos(turnos_hip)
    if not fusionados:
        return {"palabras_frag_lt10": 0, "tasa_frag_lt10": math.nan}

    total_palabras = sum(len(str(t["texto"]).split()) for t in fusionados)
    if total_palabras == 0:
        return {"palabras_frag_lt10": 0, "tasa_frag_lt10": math.nan}

    frag_palabras = 0
    if len(fusionados) >= 3:
        for t in fusionados[1:-1]:
            n_pal = len(str(t["texto"]).split())
            if n_pal < 10:
                frag_palabras += n_pal

    return {
        "palabras_frag_lt10": frag_palabras,
        "tasa_frag_lt10": frag_palabras / total_palabras,
    }


def calcular_metricas_diarizacion_clip(
    turnos_ref: list[dict[str, Any]],
    turnos_hip_seg: list[dict[str, Any]],
    turnos_hip_word: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evalua ambas vistas de diarizacion (segment vs word) contra referencia gold."""
    pares_ref = _expandir_turnos_a_pares(turnos_ref)
    pares_seg = _expandir_turnos_a_pares(turnos_hip_seg)
    pares_word = _expandir_turnos_a_pares(turnos_hip_word)

    n_hab_ref = len({spk for _, spk in pares_ref})
    n_hab_seg = len({spk for _, spk in pares_seg})
    n_hab_word = len({spk for _, spk in pares_word})

    wder_seg = calcular_wder(pares_ref, pares_seg)
    cpwer_seg = calcular_cpwer(pares_ref, pares_seg)

    wder_word = calcular_wder(pares_ref, pares_word)
    cpwer_word = calcular_cpwer(pares_ref, pares_word)

    frag = calcular_fragmentacion_lt10(turnos_hip_seg)

    return {
        "n_hablantes_ref": n_hab_ref,
        "n_hablantes_hip_seg": n_hab_seg,
        "delta_hablantes_seg": n_hab_seg - n_hab_ref,
        "pares_alineados_seg": wder_seg["pares_alineados"],
        "err_spk_seg": wder_seg["err_spk"],
        "WDER_seg": wder_seg["WDER"],
        "cpWER_errores_seg": cpwer_seg["cpWER_errores"],
        "cpWER_seg": cpwer_seg["cpWER"],
        "n_hablantes_hip_word": n_hab_word,
        "delta_hablantes_word": n_hab_word - n_hab_ref,
        "pares_alineados_word": wder_word["pares_alineados"],
        "err_spk_word": wder_word["err_spk"],
        "WDER_word": wder_word["WDER"],
        "cpWER_errores_word": cpwer_word["cpWER_errores"],
        "cpWER_word": cpwer_word["cpWER"],
        "palabras_frag_lt10": frag["palabras_frag_lt10"],
        "tasa_frag_lt10": frag["tasa_frag_lt10"],
    }

