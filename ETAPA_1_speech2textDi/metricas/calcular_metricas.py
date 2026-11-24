"""CLI principal para calcular metricas del piloto de la Etapa 1."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd

_ETAPA_DIR = Path(__file__).resolve().parents[1]
if str(_ETAPA_DIR) not in sys.path:
    sys.path.insert(0, str(_ETAPA_DIR))

from core.hashes import sha256_archivo
from core.io_diario import (
    agrupar_en_turnos,
    calcular_confianza_clip,
    cargar_json_diario,
    extraer_palabras_diario,
    recortar_palabras_clip,
)
from core.validacion_esquemas import (
    EsquemaInvalidoError,
    fusionar_turnos_consecutivos,
    validar_anotacion,
    validar_manifest,
    verificar_sin_solapamiento_manifests,
)
from metricas.calculo_asr import calcular_metricas_asr_clip
from metricas.calculo_diarizacion import calcular_metricas_diarizacion_clip
from metricas.inferencia import (
    bootstrap_metricas,
    correlaciones_confianza,
    dimensionar_muestra_final,
    resumen_hablantes,
)

COLUMNAS_CSV = [
    "clip_id",
    "entrevista",
    "candidato_cid",
    "candidato_slug",
    "estrato",
    "estado",
    "motivo_no_anotable",
    "n_inaudible",
    "n_solapado",
    "N_ref",
    "N_hip",
    "S",
    "D",
    "I",
    "H",
    "WER",
    "CER",
    "entidades_ref",
    "entidades_err",
    "tasa_err_entidades",
    "n_hablantes_ref",
    "n_hablantes_hip_seg",
    "delta_hablantes_seg",
    "pares_alineados_seg",
    "err_spk_seg",
    "WDER_seg",
    "cpWER_errores_seg",
    "cpWER_seg",
    "delta_diar_seg",
    "n_hablantes_hip_word",
    "delta_hablantes_word",
    "pares_alineados_word",
    "err_spk_word",
    "WDER_word",
    "cpWER_errores_word",
    "cpWER_word",
    "palabras_frag_lt10",
    "tasa_frag_lt10",
    "score_medio",
    "avg_logprob_medio",
    "tiempo_anotacion_s",
]


def _verificar_fuentes(manifest: dict[str, Any], repo_fuente: Path) -> list[str]:
    """Verifica SHA-256 de JSONs (y WAVs si existen) en CodeCursos/Resultados/."""
    dir_diario = repo_fuente / manifest["fuente"]["dir_diario"]
    dir_audios = repo_fuente / manifest["fuente"]["dir_audios"]
    errores: list[str] = []
    verificados_json: dict[str, str] = {}
    verificados_wav: dict[str, str] = {}

    for clip in manifest["clips"]:
        ent = clip["entrevista"]
        ruta_json = dir_diario / f"{ent}.json"
        if not ruta_json.is_file():
            errores.append(f"Falta JSON fuente: {ruta_json}")
        else:
            if ent not in verificados_json:
                verificados_json[ent] = sha256_archivo(ruta_json)
            if verificados_json[ent] != clip["sha256_json"]:
                errores.append(f"sha256_json modificado en {ent}.json")

        ruta_wav = dir_audios / f"{ent}.wav"
        if not ruta_wav.is_file():
            errores.append(f"Falta WAV fuente: {ruta_wav}")
        else:
            if ent not in verificados_wav:
                verificados_wav[ent] = sha256_archivo(ruta_wav)
            if verificados_wav[ent] != clip["sha256_wav"]:
                errores.append(f"sha256_wav modificado en {ent}.wav")
    return errores


def _fila_vacia(clip: dict[str, Any], estado: str, motivo: str | None, tiempo_s: float) -> dict[str, Any]:
    fila: dict[str, Any] = {col: math.nan for col in COLUMNAS_CSV}
    fila.update(
        {
            "clip_id": clip["clip_id"],
            "entrevista": clip["entrevista"],
            "candidato_cid": clip["candidato_cid"],
            "candidato_slug": clip["candidato_slug"],
            "estrato": clip["estrato"],
            "estado": estado,
            "motivo_no_anotable": motivo if motivo else "",
            "tiempo_anotacion_s": tiempo_s,
        }
    )
    return fila


def ejecutar_evaluacion(
    ruta_manifest: Path | list[Path],
    ruta_anotacion: Path | list[Path],
    repo_fuente: Path | None = None,
    semilla_bootstrap: int = 20261119,
    n_bootstrap: int = 10000,
    margen_objetivo: float = 0.03,
    permitir_incompleto: bool = False,
    permitir_obsoletos: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Ejecuta validacion de trazabilidad (1 o varios lotes) y calcula CSV y JSON."""
    rutas_m = [ruta_manifest] if isinstance(ruta_manifest, Path) else list(ruta_manifest)
    rutas_a = [ruta_anotacion] if isinstance(ruta_anotacion, Path) else list(ruta_anotacion)
    if not rutas_m or len(rutas_m) != len(rutas_a):
        raise ValueError("Debe proporcionar la misma cantidad de archivos --manifest y --anotacion.")

    manifests: list[dict[str, Any]] = []
    anotaciones: list[dict[str, Any]] = []
    incompletos_totales: list[str] = []

    for r_m, r_a in zip(rutas_m, rutas_a):
        with r_m.open("r", encoding="utf-8") as fh:
            m = json.load(fh)
        validar_manifest(m, verificar_hash=True)
        with r_a.open("r", encoding="utf-8") as fh:
            a = json.load(fh)
        inc = validar_anotacion(a, m, exigir_todos_terminados=not permitir_incompleto)
        manifests.append(m)
        anotaciones.append(a)
        incompletos_totales.extend(inc)

    verificar_sin_solapamiento_manifests(manifests, colchon_s=0.0)

    fuente_path = repo_fuente if repo_fuente is not None else Path(manifests[0]["fuente"]["repo_path"])
    errores_fuentes: list[str] = []
    for m in manifests:
        errores_fuentes.extend(_verificar_fuentes(m, fuente_path))
    if errores_fuentes and not permitir_obsoletos:
        raise ValueError(
            "Insumos obsoletos o faltantes en CodeCursos: " + "; ".join(errores_fuentes[:5])
        )

    cache_diario: dict[str, dict[str, Any]] = {}
    filas: list[dict[str, Any]] = []
    dir_diario = fuente_path / manifests[0]["fuente"]["dir_diario"]

    pares_clips = [
        (clip, anot)
        for m, anot in zip(manifests, anotaciones)
        for clip in m["clips"]
    ]
    for clip, anotacion in sorted(pares_clips, key=lambda item: item[0]["clip_id"]):
        cid = clip["clip_id"]
        entry = anotacion["clips"].get(cid, {"estado": "pendiente", "turnos": [], "tiempo_anotacion_s": 0.0})
        estado = entry.get("estado", "pendiente")
        tiempo_s = float(entry.get("tiempo_anotacion_s", 0.0))

        if estado != "completo":
            filas.append(_fila_vacia(clip, estado, entry.get("motivo_no_anotable"), tiempo_s))
            continue

        ent = clip["entrevista"]
        if ent not in cache_diario:
            cache_diario[ent] = cargar_json_diario(dir_diario / f"{ent}.json")
        diario_data = cache_diario[ent]

        ini_s = float(clip["inicio_s"])
        fin_s = float(clip["fin_s"])

        pals_seg = recortar_palabras_clip(extraer_palabras_diario(diario_data, vista="segment"), ini_s, fin_s)
        pals_word = recortar_palabras_clip(extraer_palabras_diario(diario_data, vista="word"), ini_s, fin_s)
        turnos_hip_seg = agrupar_en_turnos(pals_seg, mapear_genericos=False)
        turnos_hip_word = agrupar_en_turnos(pals_word, mapear_genericos=False)
        texto_hip_completo = " ".join(t["texto"] for t in turnos_hip_seg).strip()

        turnos_ref = fusionar_turnos_consecutivos(entry["turnos"])
        asr_m = calcular_metricas_asr_clip(turnos_ref, texto_hip_completo)
        diar_m = calcular_metricas_diarizacion_clip(turnos_ref, turnos_hip_seg, turnos_hip_word)
        score_medio, logprob_medio = calcular_confianza_clip(diario_data, ini_s, fin_s)

        delta_diar_seg = (
            diar_m["cpWER_seg"] - asr_m["WER"]
            if (not math.isnan(diar_m["cpWER_seg"]) and not math.isnan(asr_m["WER"]))
            else math.nan
        )

        fila = {
            "clip_id": cid,
            "entrevista": ent,
            "candidato_cid": clip["candidato_cid"],
            "candidato_slug": clip["candidato_slug"],
            "estrato": clip["estrato"],
            "estado": estado,
            "motivo_no_anotable": "",
            **asr_m,
            **diar_m,
            "delta_diar_seg": delta_diar_seg,
            "score_medio": score_medio if score_medio is not None else math.nan,
            "avg_logprob_medio": logprob_medio if logprob_medio is not None else math.nan,
            "tiempo_anotacion_s": tiempo_s,
        }
        filas.append(fila)

    df = pd.DataFrame(filas, columns=COLUMNAS_CSV)
    df_eval = df[(df["estado"] == "completo") & (df["N_ref"] > 0)].copy()

    n_completos = int((df["estado"] == "completo").sum())
    n_no_anot = int((df["estado"] == "no_anotable").sum())
    df_b = df_eval[df_eval["estrato"] == "B"]
    df_a = df_eval[df_eval["estrato"] == "A"]

    tiempos = df[df["estado"].isin(["completo", "no_anotable"])]["tiempo_anotacion_s"].dropna()
    tiempo_medio = float(tiempos.mean()) if not tiempos.empty else None
    tiempo_total_h = float(tiempos.sum() / 3600.0) if not tiempos.empty else 0.0

    # Desagregacion exploratoria por candidato
    por_cand: dict[str, dict[str, Any]] = {}
    for slug, grp in df_eval.groupby("candidato_slug", sort=True):
        agg_c = bootstrap_metricas(grp, n_bootstrap=1, semilla=semilla_bootstrap)
        por_cand[str(slug)] = {
            "n_eval": int(len(grp)),
            "WER": agg_c["WER"]["puntual"],
            "WDER_seg": agg_c["WDER_seg"]["puntual"],
            "cpWER_seg": agg_c["cpWER_seg"]["puntual"],
            "delta_hablantes_medio": round(float(grp["delta_hablantes_seg"].mean()), 3),
        }

    # Estratos con s_WER_clip
    estratos_res: dict[str, Any] = {}
    for est_nombre, sub in (("B", df_b), ("A", df_a)):
        res_est = bootstrap_metricas(sub, n_bootstrap=n_bootstrap, semilla=semilla_bootstrap)
        wers_est = sub["WER"].dropna().tolist()
        res_est["s_WER_clip"] = (
            round(float(pd.Series(wers_est).std(ddof=1)), 6) if len(wers_est) >= 2 else None
        )
        estratos_res[est_nombre] = res_est

    wers_b = df_b["WER"].dropna().tolist()
    resumen = {
        "version_esquema": "1.0",
        "fecha_calculo": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "parcial": bool(incompletos_totales),
        "trazabilidad": {
            "sha256_manifest": manifests[0]["sha256_manifest"] if len(manifests) == 1 else "consolidado",
            "manifests": [
                {"archivo": str(rm), "fase": m["fase"], "sha256_manifest": m["sha256_manifest"], "n_clips": len(m["clips"])}
                for rm, m in zip(rutas_m, manifests)
            ],
            "archivo_anotacion": str(rutas_a[0]) if len(rutas_a) == 1 else ", ".join(str(ra) for ra in rutas_a),
            "archivos_anotacion": [
                {"archivo": str(ra), "sha256_anotacion": sha256_archivo(ra)}
                for ra in rutas_a
            ],
            "sha256_anotacion": sha256_archivo(rutas_a[0]) if len(rutas_a) == 1 else "consolidado",
            "version_guia": anotaciones[0].get("version_guia", ""),
            "fuentes_validadas_ok": len(errores_fuentes) == 0,
            "semilla_bootstrap": semilla_bootstrap,
            "n_bootstrap": n_bootstrap,
        },
        "cobertura": {
            "n_total_manifest": len(df),
            "n_completos": n_completos,
            "n_no_anotables": n_no_anot,
            "n_evaluables": len(df_eval),
            "n_estrato_b_eval": len(df_b),
            "n_estrato_a_eval": len(df_a),
            "tiempo_medio_clip_s": round(tiempo_medio, 2) if tiempo_medio is not None else None,
            "tiempo_total_h": round(tiempo_total_h, 3),
        },
        "metricas_globales": bootstrap_metricas(
            df_eval, n_bootstrap=n_bootstrap, semilla=semilla_bootstrap
        ),
        "hablantes_seg": resumen_hablantes(df_eval),
        "por_estrato": estratos_res,
        "por_candidato_exploratorio": por_cand,
        "correlacion_confianza": correlaciones_confianza(df_eval),
        "dimensionamiento_muestra_final": dimensionar_muestra_final(
            wers_b=wers_b,
            margen_objetivo_e=margen_objetivo,
            tiempo_medio_clip_s=tiempo_medio,
        ),
    }
    return df, resumen


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calcula metricas ASR, diarizacion textual e IC bootstrap del piloto."
    )
    parser.add_argument("--manifest", type=Path, nargs="+", required=True, help="Ruta(s) a manifest_*.json.")
    parser.add_argument("--anotacion", type=Path, nargs="+", required=True, help="Ruta(s) a gold/**/anot_*.json.")
    parser.add_argument("--repo-fuente", type=Path, default=None, help="Override ruta a CodeCursos.")
    parser.add_argument(
        "--salida-csv",
        type=Path,
        default=_ETAPA_DIR / "metricas" / "resultados_piloto.csv",
        help="Ruta de salida CSV por clip.",
    )
    parser.add_argument(
        "--salida-resumen",
        type=Path,
        default=_ETAPA_DIR / "metricas" / "resumen_piloto.json",
        help="Ruta de salida JSON resumen.",
    )
    parser.add_argument("--semilla-bootstrap", type=int, default=20261119)
    parser.add_argument("--n-bootstrap", type=int, default=10000)
    parser.add_argument("--margen-objetivo", type=float, default=0.03)
    parser.add_argument("--permitir-incompleto", action="store_true")
    parser.add_argument("--permitir-obsoletos", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if len(args.manifest) != len(args.anotacion):
        print("ERROR: --manifest y --anotacion deben tener el mismo numero de archivos.")
        return 1
    if any(not p.is_file() for p in args.manifest) or any(not p.is_file() for p in args.anotacion):
        print("ERROR: Alguno de los archivos manifest o anotacion indicados no existe.")
        return 1

    try:
        df, resumen = ejecutar_evaluacion(
            ruta_manifest=args.manifest,
            ruta_anotacion=args.anotacion,
            repo_fuente=args.repo_fuente,
            semilla_bootstrap=args.semilla_bootstrap,
            n_bootstrap=args.n_bootstrap,
            margen_objetivo=args.margen_objetivo,
            permitir_incompleto=args.permitir_incompleto,
            permitir_obsoletos=args.permitir_obsoletos,
        )
    except EsquemaInvalidoError as exc:
        msg = str(exc)
        if "Aun existen" in msg:
            print(f"ERROR (piloto incompleto): {msg}")
            return 2
        print(f"ERROR de esquema/trazabilidad: {msg}")
        return 1
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    args.salida_csv.parent.mkdir(parents=True, exist_ok=True)
    args.salida_resumen.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(args.salida_csv, index=False, encoding="utf-8")
    with args.salida_resumen.open("w", encoding="utf-8") as fh:
        json.dump(resumen, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    mg = resumen["metricas_globales"]
    print("Calculo de metricas finalizado.")
    print(f"Clips evaluables: {resumen['cobertura']['n_evaluables']} / {resumen['cobertura']['n_total_manifest']}")
    for metrica in ("WER", "CER", "WDER_seg", "cpWER_seg", "delta_diar_seg"):
        val = mg[metrica]["puntual"]
        ic = mg[metrica]["ic95"]
        if val is not None:
            print(f"  {metrica}: {val:.4f} (IC95: [{ic[0]:.4f}, {ic[1]:.4f}])")
    dim = resumen["dimensionamiento_muestra_final"]
    print(f"Dimensionamiento final (E=+-{dim['margen_objetivo_E']*100:.1f} pp): n_B={dim['n_B_recomendado']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

