"""Generador automatico del informe Markdown del piloto (Etapa 1)."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd

_ETAPA_DIR = Path(__file__).resolve().parents[1]


def _fmt_pct(val: float | None) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "N/D"
    return f"{val * 100:.2f}%"


def _fmt_ic_pct(entry: dict[str, Any] | None) -> str:
    if not entry:
        return "N/D"
    p = entry.get("puntual")
    ic = entry.get("ic95") or [None, None]
    if p is None:
        return "N/D"
    if ic[0] is None or ic[1] is None:
        return f"{p * 100:.2f}%"
    return f"{p * 100:.2f}% [{ic[0] * 100:.2f}%, {ic[1] * 100:.2f}%]"


def _fmt_num(val: float | None, dec: int = 2) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "N/D"
    return f"{val:.{dec}f}"


def construir_markdown_informe(df: pd.DataFrame, resumen: dict[str, Any]) -> str:
    """Construye el documento Markdown completo conforme a contracts/cli_reporte.md."""
    for clave in (
        "trazabilidad",
        "cobertura",
        "metricas_globales",
        "hablantes_seg",
        "por_estrato",
        "por_candidato_exploratorio",
        "correlacion_confianza",
        "dimensionamiento_muestra_final",
    ):
        if clave not in resumen:
            raise ValueError(f"Falta clave obligatoria en resumen JSON: '{clave}'.")

    traz = resumen["trazabilidad"]
    cob = resumen["cobertura"]
    mg = resumen["metricas_globales"]
    hab = resumen["hablantes_seg"]
    est_b = resumen["por_estrato"].get("B", {})
    est_a = resumen["por_estrato"].get("A", {})
    corr = resumen["correlacion_confianza"]
    dim = resumen["dimensionamiento_muestra_final"]

    parcial_nota = (
        "> **AVISO:** Corrida marcada como parcial (`parcial = true`); existen clips pendientes.\n\n"
        if resumen.get("parcial")
        else ""
    )

    lineas: list[str] = [
        "# Informe de Validacion — Etapa 1 (Piloto): ASR y Diarizacion Textual",
        "",
        parcial_nota.rstrip(),
        "## 1. Ficha tecnica y trazabilidad",
        "",
        "| Elemento | Valor |",
        "|:---------|:------|",
        f"| Fecha de calculo | `{resumen.get('fecha_calculo', 'N/D')}` |",
        f"| `sha256_manifest` | `{traz.get('sha256_manifest', 'N/D')}` |",
        f"| Archivo de anotacion | `{traz.get('archivo_anotacion', 'N/D')}` |",
        f"| `sha256_anotacion` | `{traz.get('sha256_anotacion', 'N/D')}` |",
        f"| Version de guia | `{traz.get('version_guia', 'N/D')}` |",
        f"| Fuentes `CodeCursos` intactas | `{'Si' if traz.get('fuentes_validadas_ok') else 'NO (obsoleto)'}` |",
        f"| Cobertura del piloto | {cob.get('n_completos', 0)} completos, {cob.get('n_no_anotables', 0)} no anotables (de {cob.get('n_total_manifest', 0)}) |",
        f"| Clips evaluables por estrato | Estrato B = {cob.get('n_estrato_b_eval', 0)}, Estrato A = {cob.get('n_estrato_a_eval', 0)} |",
        f"| Tiempo medio / total de anotacion | {_fmt_num(cob.get('tiempo_medio_clip_s'), 1)} s/clip ({_fmt_num(cob.get('tiempo_total_h'), 2)} h totales) |",
        f"| Bootstrap | B = {traz.get('n_bootstrap', 10000)} replicas (semilla `{traz.get('semilla_bootstrap', 'N/D')}`) |",
        "",
        "---",
        "",
        "## 2. Resultados primarios (global y por estrato)",
        "",
        "Todas las metricas se reportan como estimacion puntual agregada con **IC 95 % por bootstrap** remuestreando clips.",
        "",
        "| Metrica (vista `segment` = `general.py`) | Global | Estrato B (aleatorio) | Estrato A (anclado) |",
        "|:-----------------------------------------|:-------|:----------------------|:--------------------|",
        f"| **WER** | {_fmt_ic_pct(mg.get('WER'))} | {_fmt_ic_pct(est_b.get('WER'))} | {_fmt_ic_pct(est_a.get('WER'))} |",
        f"| **WDER** | {_fmt_ic_pct(mg.get('WDER_seg'))} | {_fmt_ic_pct(est_b.get('WDER_seg'))} | {_fmt_ic_pct(est_a.get('WDER_seg'))} |",
        f"| **cpWER** | {_fmt_ic_pct(mg.get('cpWER_seg'))} | {_fmt_ic_pct(est_b.get('cpWER_seg'))} | {_fmt_ic_pct(est_a.get('cpWER_seg'))} |",
        f"| **Brecha diarizacion (`cpWER - WER`)** | {_fmt_ic_pct(mg.get('delta_diar_seg'))} | {_fmt_ic_pct(est_b.get('delta_diar_seg'))} | {_fmt_ic_pct(est_a.get('delta_diar_seg'))} |",
        "",
        "### Distribucion del error en numero de hablantes (`ΔH = H_hip - H_ref`)",
        "",
        "| Indicador | Valor |",
        "|:----------|:------|",
        f"| Sesgo medio (`ΔH`) | {_fmt_num(hab.get('delta_medio'), 3)} hablantes/clip |",
        f"| Mediana (`ΔH`) | {_fmt_num(hab.get('delta_mediana'), 1)} |",
        f"| Clips exactos (`ΔH == 0`) | {_fmt_pct(hab.get('pct_exacto'))} |",
        f"| Clips sobresegmentados (`ΔH > 0`) | {_fmt_pct(hab.get('pct_sobresegmentado'))} |",
        f"| Clips subsegmentados (`ΔH < 0`) | {_fmt_pct(hab.get('pct_subsegmentado'))} |",
        "",
        "---",
        "",
        "## 3. Resultados secundarios y auditoria del flujo",
        "",
        "| Indicador | Estimacion global [IC 95 %] |",
        "|:----------|:----------------------------|",
        f"| **CER** | {_fmt_ic_pct(mg.get('CER'))} |",
        f"| **Error en cifras, siglas y nombres propios** | {_fmt_ic_pct(mg.get('tasa_err_entidades'))} |",
        f"| **Fragmentacion interna `< 10` palabras** | {_fmt_ic_pct(mg.get('tasa_frag_lt10'))} |",
        "",
        "### Auditoria del puente Paso 2 -> Paso 3 (`segment` vs. `word`)",
        "",
        "Compara la agrupacion actual de `general.py` (`segment['speaker']`) frente a la salida fina de palabras de WhisperX (`words[].speaker`).",
        "",
        "| Metrica | Vista `segment` (`general.py`) | Vista `word` (`words[].speaker`) |",
        "|:--------|:-------------------------------|:---------------------------------|",
        f"| **WDER** | {_fmt_ic_pct(mg.get('WDER_seg'))} | {_fmt_ic_pct(mg.get('WDER_word'))} |",
        f"| **cpWER** | {_fmt_ic_pct(mg.get('cpWER_seg'))} | {_fmt_ic_pct(mg.get('cpWER_word'))} |",
        "",
        "### Correlacion de confianza de WhisperX vs. WER (Spearman)",
        "",
        "| Variable de confianza | rho de Spearman | p-valor |",
        "|:----------------------|:----------------|:--------|",
        f"| `score_medio` (palabras) | {_fmt_num(corr.get('spearman_score_vs_WER', {}).get('rho'), 4)} | {_fmt_num(corr.get('spearman_score_vs_WER', {}).get('p_value'), 5)} |",
        f"| `avg_logprob_medio` (segmentos) | {_fmt_num(corr.get('spearman_logprob_vs_WER', {}).get('rho'), 4)} | {_fmt_num(corr.get('spearman_logprob_vs_WER', {}).get('p_value'), 5)} |",
        "",
        "---",
        "",
        "## 4. Desagregacion exploratoria por candidato",
        "",
        "> **Nota metodologica:** Con $n \\le 3$ clips por candidato en el piloto, estos valores son estrictamente **exploratorios** y no permiten inferir diferencias significativas entre candidatos.",
        "",
        "| Candidato | n eval | WER | WDER (`segment`) | cpWER (`segment`) | `ΔH` medio |",
        "|:----------|:------:|:----|:-----------------|:------------------|:-----------|",
    ]

    for slug, info in sorted(resumen["por_candidato_exploratorio"].items()):
        lineas.append(
            f"| `{slug}` | {info.get('n_eval', 0)} | {_fmt_pct(info.get('WER'))} | "
            f"{_fmt_pct(info.get('WDER_seg'))} | {_fmt_pct(info.get('cpWER_seg'))} | "
            f"{_fmt_num(info.get('delta_hablantes_medio'), 2)} |"
        )

    lineas.extend(
        [
            "",
            "---",
            "",
            "## 5. Inspeccion de los 5 peores clips",
            "",
        ]
    )

    df_eval = df[(df["estado"] == "completo") & (df["N_ref"] > 0)].copy() if not df.empty else pd.DataFrame()
    if not df_eval.empty:
        lineas.extend(
            [
                "### Por WER (peores 5)",
                "",
                "| Clip | Candidato | Estrato | WER | WDER (`seg`) | `ΔH` (`seg`) | Entidades err/ref |",
                "|:-----|:----------|:-------:|:----|:-------------|:-------------|:-----------------|",
            ]
        )
        for _, row in df_eval.sort_values("WER", ascending=False).head(5).iterrows():
            lineas.append(
                f"| `{row['clip_id']}` | `{row['candidato_slug']}` | {row['estrato']} | "
                f"{_fmt_pct(row['WER'])} | {_fmt_pct(row['WDER_seg'])} | "
                f"{int(row['delta_hablantes_seg'])} | {int(row['entidades_err'])}/{int(row['entidades_ref'])} |"
            )

        lineas.extend(
            [
                "",
                "### Por WDER (`segment`, peores 5)",
                "",
                "| Clip | Candidato | Estrato | WDER (`seg`) | cpWER (`seg`) | WER | `ΔH` (`seg`) |",
                "|:-----|:----------|:-------:|:-------------|:--------------|:----|:-------------|",
            ]
        )
        for _, row in df_eval.sort_values("WDER_seg", ascending=False).head(5).iterrows():
            lineas.append(
                f"| `{row['clip_id']}` | `{row['candidato_slug']}` | {row['estrato']} | "
                f"{_fmt_pct(row['WDER_seg'])} | {_fmt_pct(row['cpWER_seg'])} | "
                f"{_fmt_pct(row['WER'])} | {int(row['delta_hablantes_seg'])} |"
            )
    else:
        lineas.append("No hay clips evaluables para listar.")

    lineas.extend(
        [
            "",
            "---",
            "",
            "## 6. Dimensionamiento de la muestra final y cierre del piloto",
            "",
            "| Parametro | Valor |",
            "|:----------|:------|",
            f"| Margen objetivo $E$ | +-{(dim.get('margen_objetivo_E') or 0.03) * 100:.1f} pp |",
            f"| Clips Estrato B en el piloto | {dim.get('n_B_piloto', 0)} |",
            f"| Desviacion estandar $s_B$ (WER por clip en B) | {_fmt_num(dim.get('s_B_WER_clip'), 4)} |",
            f"| Limite superior al 80 % ($s_{{\\text{{UCL}}}}$) | {_fmt_num(dim.get('s_UCL_80'), 4)} |",
            f"| **Tamano final recomendado ($n_B$)** | **{dim.get('n_B_recomendado', 'N/D')}** |",
            f"| Horas adicionales estimadas de anotacion | {_fmt_num(dim.get('horas_anotacion_estimadas_adicionales'), 2)} h |",
            "",
            "### Registro de cierre del piloto (completar tras revision)",
            "",
            "- **Incidencias detectadas en la guia o la app:** *(completar)*",
            "- **Decision de integracion:** *(documentar si los 24 clips se suman a la muestra final o se excluyen por cambio en la guia)*",
            "",
        ]
    )

    return "\n".join(lineas)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera informe_piloto.md desde CSV y JSON.")
    parser.add_argument("--csv", type=Path, required=True, help="Ruta a resultados_piloto.csv.")
    parser.add_argument("--resumen", type=Path, required=True, help="Ruta a resumen_piloto.json.")
    parser.add_argument(
        "--salida",
        type=Path,
        default=_ETAPA_DIR / "reporte" / "informe_piloto.md",
        help="Ruta de salida para informe_piloto.md.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.csv.is_file() or not args.resumen.is_file():
        print("ERROR: No existe el archivo CSV o resumen JSON indicado.")
        return 1

    try:
        df = pd.read_csv(args.csv, encoding="utf-8")
        with args.resumen.open("r", encoding="utf-8") as fh:
            resumen = json.load(fh)
        contenido = construir_markdown_informe(df, resumen)
    except Exception as exc:
        print(f"ERROR generando el informe: {exc}")
        return 1

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(contenido, encoding="utf-8")
    print(f"Informe generado correctamente: {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

