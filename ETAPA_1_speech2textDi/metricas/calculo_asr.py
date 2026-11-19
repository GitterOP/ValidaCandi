"""Calculo de metricas ASR (WER, CER) y tasa de error en cifras, siglas y entidades."""

from __future__ import annotations

import math
import re
from typing import Any

import jiwer

from core.normalizacion import normalizar_texto

_PATRON_DIGITO = re.compile(r"\d")
_PATRON_SOLO_LETRAS = re.compile(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")
_PATRON_NOMBRE_PROPIO = re.compile(r"^[A-ZÁÉÍÓÚÑ][a-záéíóúüñ]+$")
_ABREVIATURAS_NO_FINALES = frozenset({"sr.", "sra.", "dr.", "dra.", "ing.", "lic.", "nro.", "art.", "inc."})


def _extraer_spans_entidades_norm(
    turnos_ref: list[dict[str, Any]],
    tokens_ref_norm: list[str],
) -> list[tuple[int, int]]:
    """Extrae cifras, siglas y nombres propios internos de la referencia gold.

    Localiza cada entidad extraida como un rango [inicio, fin) dentro de
    ``tokens_ref_norm`` para cruzarla contra la alineacion de ``jiwer``.
    """
    candidatos_norm: list[list[str]] = []

    for turno in turnos_ref:
        texto = str(turno.get("texto", "")).strip()
        if not texto:
            continue
        en_inicio_oracion = True
        for raw_tok in texto.split():
            tok_sin_puntuacion = raw_tok.strip(".,;:¿?¡!\"'()[]—-")
            solo_letras = _PATRON_SOLO_LETRAS.sub("", raw_tok)

            es_cifra = bool(_PATRON_DIGITO.search(tok_sin_puntuacion))
            es_sigla = len(solo_letras) >= 2 and solo_letras.isupper()
            es_nombre = (
                not en_inicio_oracion
                and bool(_PATRON_NOMBRE_PROPIO.match(solo_letras))
                and len(solo_letras) >= 2
            )

            if es_cifra or es_sigla or es_nombre:
                norm_toks = normalizar_texto(raw_tok).tokens
                if norm_toks:
                    candidatos_norm.append(norm_toks)

            # Actualizar deteccion de fin de oracion
            raw_lower = raw_tok.lower()
            if raw_lower in _ABREVIATURAS_NO_FINALES:
                en_inicio_oracion = False
            elif raw_tok.endswith((".", "!", "?")) and not es_cifra:
                en_inicio_oracion = True
            else:
                en_inicio_oracion = False

    spans: list[tuple[int, int]] = []
    cursor = 0
    n_ref = len(tokens_ref_norm)
    for ent_toks in candidatos_norm:
        m = len(ent_toks)
        encontrado = False
        for pos in range(cursor, n_ref - m + 1):
            if tokens_ref_norm[pos : pos + m] == ent_toks:
                spans.append((pos, pos + m))
                cursor = pos + m
                encontrado = True
                break
        if not encontrado:
            # Si no se encontro secuencialmente desde cursor, avanzar sin romper
            continue
    return spans


def calcular_metricas_asr_clip(
    turnos_ref: list[dict[str, Any]],
    texto_hip: str,
) -> dict[str, Any]:
    """Calcula WER, CER, conteos S/D/I/H y tasa de error en entidades para un clip."""
    texto_ref_crudo = " ".join(str(t.get("texto", "")).strip() for t in turnos_ref).strip()
    norm_ref = normalizar_texto(texto_ref_crudo)
    norm_hip = normalizar_texto(texto_hip)

    n_ref = len(norm_ref.tokens)
    n_hip = len(norm_hip.tokens)
    spans_ent = _extraer_spans_entidades_norm(turnos_ref, norm_ref.tokens)
    entidades_ref = len(spans_ent)

    if n_ref == 0:
        return {
            "n_inaudible": norm_ref.n_inaudible,
            "n_solapado": norm_ref.n_solapado,
            "N_ref": 0,
            "N_hip": n_hip,
            "S": 0,
            "D": 0,
            "I": 0,
            "H": 0,
            "WER": math.nan,
            "CER": math.nan,
            "entidades_ref": 0,
            "entidades_err": 0,
            "tasa_err_entidades": math.nan,
        }

    if n_hip == 0:
        return {
            "n_inaudible": norm_ref.n_inaudible,
            "n_solapado": norm_ref.n_solapado,
            "N_ref": n_ref,
            "N_hip": 0,
            "S": 0,
            "D": n_ref,
            "I": 0,
            "H": 0,
            "WER": 1.0,
            "CER": 1.0,
            "entidades_ref": entidades_ref,
            "entidades_err": entidades_ref,
            "tasa_err_entidades": 1.0 if entidades_ref > 0 else math.nan,
        }

    out_w = jiwer.process_words(norm_ref.texto, norm_hip.texto)
    out_c = jiwer.process_characters(norm_ref.texto, norm_hip.texto)

    # Marcar indices de referencia con match exacto ("equal")
    ref_equal = [False] * n_ref
    for chunk in out_w.alignments[0]:
        if chunk.type == "equal":
            for pos in range(chunk.ref_start_idx, chunk.ref_end_idx):
                if pos < n_ref:
                    ref_equal[pos] = True

    entidades_err = 0
    for ini, fin in spans_ent:
        if not all(ref_equal[p] for p in range(ini, fin)):
            entidades_err += 1

    tasa_ent = (entidades_err / entidades_ref) if entidades_ref > 0 else math.nan
    return {
        "n_inaudible": norm_ref.n_inaudible,
        "n_solapado": norm_ref.n_solapado,
        "N_ref": n_ref,
        "N_hip": n_hip,
        "S": int(out_w.substitutions),
        "D": int(out_w.deletions),
        "I": int(out_w.insertions),
        "H": int(out_w.hits),
        "WER": float(out_w.wer),
        "CER": float(out_c.cer),
        "entidades_ref": entidades_ref,
        "entidades_err": entidades_err,
        "tasa_err_entidades": tasa_ent,
    }

