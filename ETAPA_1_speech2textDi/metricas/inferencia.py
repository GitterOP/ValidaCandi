"""Inferencia estadistica: bootstrap no parametrico, Spearman y dimensionamiento n_B."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import chi2, spearmanr


def _ratio_seguro(num: float, den: float) -> float:
    return (num / den) if den > 0 else math.nan


def _calcular_agregados_subconjunto(df: pd.DataFrame) -> dict[str, float]:
    """Calcula las metricas agregadas de un subconjunto de clips evaluables."""
    n_ref_sum = float(df["N_ref"].sum())
    n_hip_sum = float(df["N_hip"].sum())
    wer = _ratio_seguro(float((df["S"] + df["D"] + df["I"]).sum()), n_ref_sum)

    # Para CER agregado ponderado por N_ref (aproximacion consistente al nivel clip)
    valid_cer = df.dropna(subset=["CER", "N_ref"])
    cer = _ratio_seguro(
        float((valid_cer["CER"] * valid_cer["N_ref"]).sum()),
        float(valid_cer["N_ref"].sum()),
    )

    tasa_ent = _ratio_seguro(float(df["entidades_err"].sum()), float(df["entidades_ref"].sum()))
    wder_seg = _ratio_seguro(float(df["err_spk_seg"].sum()), float(df["pares_alineados_seg"].sum()))
    cpwer_seg = _ratio_seguro(float(df["cpWER_errores_seg"].sum()), n_ref_sum)
    delta_diar_seg = (cpwer_seg - wer) if (not math.isnan(cpwer_seg) and not math.isnan(wer)) else math.nan

    wder_word = _ratio_seguro(float(df["err_spk_word"].sum()), float(df["pares_alineados_word"].sum()))
    cpwer_word = _ratio_seguro(float(df["cpWER_errores_word"].sum()), n_ref_sum)
    tasa_frag = _ratio_seguro(float(df["palabras_frag_lt10"].sum()), n_hip_sum)

    return {
        "WER": wer,
        "CER": cer,
        "tasa_err_entidades": tasa_ent,
        "WDER_seg": wder_seg,
        "cpWER_seg": cpwer_seg,
        "delta_diar_seg": delta_diar_seg,
        "WDER_word": wder_word,
        "cpWER_word": cpwer_word,
        "tasa_frag_lt10": tasa_frag,
    }


def bootstrap_metricas(
    df_eval: pd.DataFrame,
    n_bootstrap: int = 10000,
    semilla: int = 20261119,
) -> dict[str, dict[str, Any]]:
    """Calcula estimaciones puntuales e IC 95 % por bootstrap remuestreando clips."""
    puntuales = _calcular_agregados_subconjunto(df_eval)
    n_clips = len(df_eval)
    if n_clips == 0:
        return {k: {"puntual": None, "ic95": [None, None]} for k in puntuales}

    if n_clips == 1:
        return {
            k: {
                "puntual": None if math.isnan(v) else round(v, 6),
                "ic95": [None, None] if math.isnan(v) else [round(v, 6), round(v, 6)],
            }
            for k, v in puntuales.items()
        }

    rng = np.random.default_rng(semilla)
    muestras: dict[str, list[float]] = {k: [] for k in puntuales}

    # Pre-extraer arreglos numpy para bootstrap rapido
    arr_sdi = (df_eval["S"] + df_eval["D"] + df_eval["I"]).to_numpy(dtype=np.float64)
    arr_nref = df_eval["N_ref"].to_numpy(dtype=np.float64)
    arr_nhip = df_eval["N_hip"].to_numpy(dtype=np.float64)
    arr_cer = df_eval["CER"].fillna(0.0).to_numpy(dtype=np.float64)
    arr_cer_mask = (~df_eval["CER"].isna()).to_numpy(dtype=np.float64)
    arr_ent_err = df_eval["entidades_err"].to_numpy(dtype=np.float64)
    arr_ent_ref = df_eval["entidades_ref"].to_numpy(dtype=np.float64)
    arr_err_seg = df_eval["err_spk_seg"].to_numpy(dtype=np.float64)
    arr_par_seg = df_eval["pares_alineados_seg"].to_numpy(dtype=np.float64)
    arr_cp_seg = df_eval["cpWER_errores_seg"].to_numpy(dtype=np.float64)
    arr_err_word = df_eval["err_spk_word"].to_numpy(dtype=np.float64)
    arr_par_word = df_eval["pares_alineados_word"].to_numpy(dtype=np.float64)
    arr_cp_word = df_eval["cpWER_errores_word"].to_numpy(dtype=np.float64)
    arr_frag = df_eval["palabras_frag_lt10"].to_numpy(dtype=np.float64)

    indices_all = rng.integers(0, n_clips, size=(n_bootstrap, n_clips))
    for idx in indices_all:
        nref_b = arr_nref[idx].sum()
        nhip_b = arr_nhip[idx].sum()
        wer_b = _ratio_seguro(arr_sdi[idx].sum(), nref_b)
        cer_b = _ratio_seguro((arr_cer[idx] * arr_nref[idx] * arr_cer_mask[idx]).sum(), (arr_nref[idx] * arr_cer_mask[idx]).sum())
        ent_b = _ratio_seguro(arr_ent_err[idx].sum(), arr_ent_ref[idx].sum())
        wder_s_b = _ratio_seguro(arr_err_seg[idx].sum(), arr_par_seg[idx].sum())
        cp_s_b = _ratio_seguro(arr_cp_seg[idx].sum(), nref_b)
        delta_b = (cp_s_b - wer_b) if (not math.isnan(cp_s_b) and not math.isnan(wer_b)) else math.nan
        wder_w_b = _ratio_seguro(arr_err_word[idx].sum(), arr_par_word[idx].sum())
        cp_w_b = _ratio_seguro(arr_cp_word[idx].sum(), nref_b)
        frag_b = _ratio_seguro(arr_frag[idx].sum(), nhip_b)

        for clave, val in (
            ("WER", wer_b),
            ("CER", cer_b),
            ("tasa_err_entidades", ent_b),
            ("WDER_seg", wder_s_b),
            ("cpWER_seg", cp_s_b),
            ("delta_diar_seg", delta_b),
            ("WDER_word", wder_w_b),
            ("cpWER_word", cp_w_b),
            ("tasa_frag_lt10", frag_b),
        ):
            if not math.isnan(val):
                muestras[clave].append(val)

    salida: dict[str, dict[str, Any]] = {}
    for clave, punt in puntuales.items():
        vals = muestras[clave]
        if math.isnan(punt) or not vals:
            salida[clave] = {"puntual": None, "ic95": [None, None]}
        else:
            q_low, q_high = np.percentile(vals, [2.5, 97.5])
            salida[clave] = {
                "puntual": round(float(punt), 6),
                "ic95": [round(float(q_low), 6), round(float(q_high), 6)],
            }
    return salida


def resumen_hablantes(df_eval: pd.DataFrame) -> dict[str, float | None]:
    """Resume sesgo y tasas de sobre/subsegmentacion en numero de hablantes."""
    if df_eval.empty:
        return {
            "delta_medio": None,
            "delta_mediana": None,
            "pct_exacto": None,
            "pct_sobresegmentado": None,
            "pct_subsegmentado": None,
        }
    deltas = df_eval["delta_hablantes_seg"].astype(float)
    n = len(deltas)
    return {
        "delta_medio": round(float(deltas.mean()), 4),
        "delta_mediana": round(float(deltas.median()), 4),
        "pct_exacto": round(float((deltas == 0).sum() / n), 4),
        "pct_sobresegmentado": round(float((deltas > 0).sum() / n), 4),
        "pct_subsegmentado": round(float((deltas < 0).sum() / n), 4),
    }


def correlaciones_confianza(df_eval: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    """Calcula correlacion de Spearman entre metricas de confianza de WhisperX y WER."""
    salida: dict[str, dict[str, float | None]] = {}
    for col, nombre in (
        ("score_medio", "spearman_score_vs_WER"),
        ("avg_logprob_medio", "spearman_logprob_vs_WER"),
    ):
        sub = df_eval.dropna(subset=[col, "WER"])
        if len(sub) < 3 or sub[col].nunique() < 2 or sub["WER"].nunique() < 2:
            salida[nombre] = {"rho": None, "p_value": None}
        else:
            rho, pval = spearmanr(sub[col], sub["WER"])
            salida[nombre] = {
                "rho": None if math.isnan(rho) else round(float(rho), 4),
                "p_value": None if math.isnan(pval) else round(float(pval), 6),
            }
    return salida


def dimensionar_muestra_final(
    wers_b: list[float],
    margen_objetivo_e: float = 0.03,
    tiempo_medio_clip_s: float | None = None,
) -> dict[str, Any]:
    """Recalcula n_B final usando s_UCL al 80 % de la desviacion estandar del piloto."""
    n_b = len(wers_b)
    if n_b < 2:
        return {
            "margen_objetivo_E": margen_objetivo_e,
            "n_B_piloto": n_b,
            "s_B_WER_clip": None,
            "s_UCL_80": None,
            "n_B_recomendado": None,
            "horas_anotacion_estimadas_adicionales": None,
        }

    s_b = float(np.std(wers_b, ddof=1))
    chi2_val = float(chi2.ppf(0.20, df=n_b - 1))
    s_ucl = s_b * math.sqrt((n_b - 1) / chi2_val)
    n_rec = int(math.ceil(((1.96 * s_ucl) / margen_objetivo_e) ** 2))
    adicionales = max(0, n_rec - n_b)
    horas_adic = (
        round((adicionales * tiempo_medio_clip_s) / 3600.0, 2)
        if tiempo_medio_clip_s is not None
        else None
    )

    return {
        "margen_objetivo_E": margen_objetivo_e,
        "n_B_piloto": n_b,
        "s_B_WER_clip": round(s_b, 6),
        "s_UCL_80": round(s_ucl, 6),
        "n_B_recomendado": n_rec,
        "horas_anotacion_estimadas_adicionales": horas_adic,
    }

