"""Lectura de archivos Diario/*.json con interpolacion y herencia determinista."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PalabraAlineada:
    """Representa una palabra alineada temporalmente con etiqueta de hablante."""

    word: str
    start: float
    end: float
    speaker: str
    score: float | None = None


def cargar_json_diario(ruta_json: Path | str) -> dict[str, Any]:
    """Carga y valida la estructura basica de un archivo de WhisperX en Diario/.

    Args:
        ruta_json: Ruta al archivo JSON en modo solo lectura.

    Returns:
        Diccionario JSON parseado.

    Raises:
        FileNotFoundError: Si no existe el archivo.
        ValueError: Si el JSON es invalido o carece de segmentos no vacios.
    """
    path = Path(ruta_json)
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo Diario JSON: {path}")

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON corrupto en {path}: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("segments"), list) or not data["segments"]:
        raise ValueError(f"El archivo {path} no contiene una lista 'segments' valida y no vacia.")
    return data


def duracion_diario_s(diario_data: dict[str, Any]) -> float:
    """Devuelve la duracion cubierta por los segmentos del JSON en segundos."""
    segments = diario_data.get("segments", [])
    if not segments:
        return 0.0
    return max(float(seg.get("end", 0.0)) for seg in segments)


def _limpiar_speaker(valor: Any, respaldo: str = "UNKNOWN") -> str:
    if isinstance(valor, str):
        limpio = valor.strip()
        if limpio:
            return limpio
    return respaldo


def _interpolar_tiempos_bloque(
    palabras_raw: list[dict[str, Any]],
    seg_start: float,
    seg_end: float,
) -> list[tuple[float, float]]:
    """Interpola linealmente timestamps faltantes dentro de un segmento."""
    n = len(palabras_raw)
    tiempos: list[tuple[float, float] | None] = []
    for w in palabras_raw:
        s = w.get("start")
        e = w.get("end")
        if s is not None and e is not None:
            s_f = float(s)
            e_f = max(float(e), s_f)
            tiempos.append((s_f, e_f))
        else:
            tiempos.append(None)

    idx = 0
    while idx < n:
        if tiempos[idx] is not None:
            idx += 1
            continue
        fin = idx
        while fin + 1 < n and tiempos[fin + 1] is None:
            fin += 1

        t_izq = tiempos[idx - 1][1] if idx > 0 and tiempos[idx - 1] is not None else seg_start
        t_der = tiempos[fin + 1][0] if fin + 1 < n and tiempos[fin + 1] is not None else seg_end
        t_izq = max(t_izq, seg_start)
        t_der = max(t_der, t_izq)

        m = fin - idx + 1
        paso = (t_der - t_izq) / m if m > 0 else 0.0
        for j in range(m):
            tiempos[idx + j] = (t_izq + j * paso, t_izq + (j + 1) * paso)
        idx = fin + 1

    return [t if t is not None else (seg_start, seg_end) for t in tiempos]


def interpolar_palabras_segmento(
    segmento: dict[str, Any],
    vista: str = "segment",
) -> list[PalabraAlineada]:
    """Convierte un segmento de WhisperX en palabras con tiempo y hablante resueltos.

    Args:
        segmento: Diccionario de un segmento de ``segments``.
        vista: ``"segment"`` (replica ``general.py`` usando ``segment["speaker"]``)
            o ``"word"`` (usa ``words[].speaker`` con herencia determinista).

    Returns:
        Lista de ``PalabraAlineada`` en orden cronologico.
    """
    if vista not in {"segment", "word"}:
        raise ValueError(f"Vista desconocida: {vista}. Use 'segment' o 'word'.")

    seg_start = float(segmento.get("start", 0.0))
    seg_end = max(float(segmento.get("end", seg_start)), seg_start)
    seg_spk = _limpiar_speaker(segmento.get("speaker"), "UNKNOWN")

    words_raw = segmento.get("words") or []
    if not words_raw:
        tokens = str(segmento.get("text", "")).strip().split()
        if not tokens:
            return []
        paso = (seg_end - seg_start) / len(tokens)
        return [
            PalabraAlineada(
                word=tok,
                start=seg_start + i * paso,
                end=seg_start + (i + 1) * paso,
                speaker=seg_spk,
                score=None,
            )
            for i, tok in enumerate(tokens)
        ]

    # Filtrar entradas vacias sin texto conservando orden
    validas: list[dict[str, Any]] = [
        w for w in words_raw if isinstance(w, dict) and str(w.get("word", "")).strip() != ""
    ]
    if not validas:
        return []

    tiempos = _interpolar_tiempos_bloque(validas, seg_start, seg_end)

    # Resolver hablantes para vista "word"
    n = len(validas)
    speakers_word: list[str] = [""] * n
    if vista == "word":
        ultimo_valido: str | None = None
        for i, w in enumerate(validas):
            sp = _limpiar_speaker(w.get("speaker"), "")
            if sp:
                speakers_word[i] = sp
                ultimo_valido = sp
            elif ultimo_valido is not None:
                speakers_word[i] = ultimo_valido

        siguiente_valido: str | None = None
        for i in range(n - 1, -1, -1):
            if speakers_word[i]:
                siguiente_valido = speakers_word[i]
            else:
                speakers_word[i] = siguiente_valido if siguiente_valido is not None else seg_spk

    resultado: list[PalabraAlineada] = []
    for i, w in enumerate(validas):
        start_i, end_i = tiempos[i]
        spk_i = seg_spk if vista == "segment" else speakers_word[i]
        score_raw = w.get("score")
        score_val = float(score_raw) if score_raw is not None else None
        resultado.append(
            PalabraAlineada(
                word=str(w.get("word", "")).strip(),
                start=start_i,
                end=end_i,
                speaker=spk_i,
                score=score_val,
            )
        )
    return resultado


def extraer_palabras_diario(
    diario_data: dict[str, Any],
    vista: str = "segment",
) -> list[PalabraAlineada]:
    """Extrae todas las palabras del archivo Diario JSON segun la vista indicada."""
    palabras: list[PalabraAlineada] = []
    for seg in diario_data.get("segments", []):
        palabras.extend(interpolar_palabras_segmento(seg, vista=vista))
    return palabras


def detectar_cambios_turno_segmento(diario_data: dict[str, Any]) -> list[float]:
    """Detecta los instantes de cambio de turno a nivel segment['speaker'].

    Replica el criterio de fusion de ``general.py`` (``merge_diarization``).
    """
    segments = diario_data.get("segments", [])
    if len(segments) < 2:
        return []

    cambios: list[float] = []
    prev_spk = _limpiar_speaker(segments[0].get("speaker"), "UNKNOWN")
    prev_end = float(segments[0].get("end", 0.0))

    for seg in segments[1:]:
        curr_spk = _limpiar_speaker(seg.get("speaker"), "UNKNOWN")
        curr_start = float(seg.get("start", prev_end))
        curr_end = float(seg.get("end", curr_start))
        if curr_spk != prev_spk:
            t_cambio = 0.5 * (prev_end + curr_start) if curr_start >= prev_end else curr_start
            cambios.append(max(0.0, t_cambio))
        prev_spk = curr_spk
        prev_end = curr_end
    return cambios


def recortar_palabras_clip(
    palabras: list[PalabraAlineada],
    inicio_s: float,
    fin_s: float,
) -> list[PalabraAlineada]:
    """Selecciona palabras cuyo punto medio cae dentro de [inicio_s, fin_s]."""
    seleccion: list[PalabraAlineada] = []
    for p in palabras:
        medio = 0.5 * (p.start + p.end)
        if inicio_s <= medio <= fin_s:
            seleccion.append(p)
    return seleccion


def agrupar_en_turnos(
    palabras: list[PalabraAlineada],
    mapear_genericos: bool = True,
) -> list[dict[str, Any]]:
    """Agrupa palabras contiguas del mismo hablante en tarjetas de turno.

    Args:
        palabras: Palabras ordenadas cronologicamente dentro del clip.
        mapear_genericos: Si es True, remapea los hablantes a ``H1``, ``H2``, ...
            en orden de primera aparicion.

    Returns:
        Lista de diccionarios ``{"turno_id": int, "hablante": str, "texto": str}``.
    """
    if not palabras:
        return []

    mapa_hablantes: dict[str, str] = {}
    turnos: list[dict[str, Any]] = []
    hablante_actual: str | None = None
    tokens_actuales: list[str] = []

    def _resolver(spk: str) -> str:
        if not mapear_genericos:
            return spk
        if spk not in mapa_hablantes:
            mapa_hablantes[spk] = f"H{len(mapa_hablantes) + 1}"
        return mapa_hablantes[spk]

    for p in palabras:
        etiqueta = _resolver(p.speaker)
        if hablante_actual is None:
            hablante_actual = etiqueta
            tokens_actuales = [p.word]
        elif etiqueta == hablante_actual:
            tokens_actuales.append(p.word)
        else:
            turnos.append(
                {
                    "turno_id": len(turnos) + 1,
                    "hablante": hablante_actual,
                    "texto": " ".join(tokens_actuales).strip(),
                }
            )
            hablante_actual = etiqueta
            tokens_actuales = [p.word]

    if hablante_actual is not None and tokens_actuales:
        turnos.append(
            {
                "turno_id": len(turnos) + 1,
                "hablante": hablante_actual,
                "texto": " ".join(tokens_actuales).strip(),
            }
        )
    return turnos


def calcular_confianza_clip(
    diario_data: dict[str, Any],
    inicio_s: float,
    fin_s: float,
) -> tuple[float | None, float | None]:
    """Calcula score medio de palabras y avg_logprob medio de segmentos del clip."""
    palabras = recortar_palabras_clip(extraer_palabras_diario(diario_data, vista="word"), inicio_s, fin_s)
    scores = [p.score for p in palabras if p.score is not None]
    score_medio = sum(scores) / len(scores) if scores else None

    logprobs: list[float] = []
    for seg in diario_data.get("segments", []):
        s_ini = float(seg.get("start", 0.0))
        s_fin = float(seg.get("end", s_ini))
        if s_fin >= inicio_s and s_ini <= fin_s:
            lp = seg.get("avg_logprob")
            if lp is not None:
                logprobs.append(float(lp))
    avg_logprob_medio = sum(logprobs) / len(logprobs) if logprobs else None
    return score_medio, avg_logprob_medio


def _corta_alguna_palabra(t: float, palabras: list[PalabraAlineada], margen_interno: float = 0.01) -> bool:
    for p in palabras:
        if p.start + margen_interno < t < p.end - margen_interno:
            return True
    return False


def _ajustar_borde_unico(
    t_objetivo: float,
    palabras: list[PalabraAlineada],
    limite_min: float,
    limite_max: float,
    ajuste_max_s: float,
) -> float:
    """Ajusta un borde temporal al hueco entre palabras mas cercano dentro de +-ajuste_max_s."""
    t_clamped = min(max(t_objetivo, limite_min), limite_max)
    if not _corta_alguna_palabra(t_clamped, palabras):
        return round(t_clamped, 3)

    ventana_ini = max(limite_min, t_clamped - ajuste_max_s)
    ventana_fin = min(limite_max, t_clamped + ajuste_max_s)

    candidatos: list[float] = []
    for i in range(len(palabras) - 1):
        fin_prev = palabras[i].end
        ini_sig = palabras[i + 1].start
        if ini_sig >= fin_prev:
            hueco = 0.5 * (fin_prev + ini_sig)
        else:
            hueco = fin_prev
        if ventana_ini <= hueco <= ventana_fin:
            candidatos.append(hueco)

    # Considerar inicio de la primera palabra y fin de la ultima
    if palabras:
        if ventana_ini <= palabras[0].start <= ventana_fin:
            candidatos.append(palabras[0].start)
        if ventana_ini <= palabras[-1].end <= ventana_fin:
            candidatos.append(palabras[-1].end)

    if not candidatos:
        return round(t_clamped, 3)

    mejor = min(candidatos, key=lambda x: abs(x - t_clamped))
    return round(mejor, 3)


def ajustar_bordes_a_huecos(
    inicio_nominal_s: float,
    fin_nominal_s: float,
    palabras: list[PalabraAlineada],
    duracion_total_s: float,
    ajuste_max_s: float = 2.0,
) -> tuple[float, float]:
    """Ajusta inicio y fin del clip a huecos entre palabras sin superar +-ajuste_max_s."""
    inicio_adj = _ajustar_borde_unico(
        inicio_nominal_s, palabras, 0.0, max(0.0, duracion_total_s - 5.0), ajuste_max_s
    )
    fin_adj = _ajustar_borde_unico(
        fin_nominal_s, palabras, min(duracion_total_s, inicio_adj + 5.0), duracion_total_s, ajuste_max_s
    )
    if fin_adj <= inicio_adj:
        inicio_adj = round(max(0.0, inicio_nominal_s), 3)
        fin_adj = round(min(duracion_total_s, fin_nominal_s), 3)
    return inicio_adj, fin_adj

