"""Normalizacion determinista de texto en espanol para metricas ASR y diarizacion."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

_PATRON_INAUDIBLE = re.compile(r"\[\s*inaudible\s*\]", re.IGNORECASE)
_PATRON_SOLAPADO = re.compile(r"\[\s*solapado\s*\]", re.IGNORECASE)
_PATRON_MUSICA = re.compile(r"\[\s*m[uú]sica\s*\]", re.IGNORECASE)
_PATRON_RUIDO = re.compile(r"\[\s*ruido\s*\]", re.IGNORECASE)

_MULETILLAS_CERRADAS = frozenset(
    {"eh", "ehm", "em", "mm", "mmm", "ah", "uh", "um", "hm", "hmm"}
)

_UNIDADES = {
    "cero": 0,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
}

_ESPECIALES_10_29 = {
    "diez": 10,
    "once": 11,
    "doce": 12,
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "dieciseis": 16,
    "diecisiete": 17,
    "dieciocho": 18,
    "diecinueve": 19,
    "veinte": 20,
    "veintiuno": 21,
    "veintiun": 21,
    "veintidos": 22,
    "veintitres": 23,
    "veinticuatro": 24,
    "veinticinco": 25,
    "veintiseis": 26,
    "veintisiete": 27,
    "veintiocho": 28,
    "veintinueve": 29,
}

_DECENAS = {
    "treinta": 30,
    "cuarenta": 40,
    "cincuenta": 50,
    "sesenta": 60,
    "setenta": 70,
    "ochenta": 80,
    "noventa": 90,
}

_CENTENAS = {
    "cien": 100,
    "ciento": 100,
    "doscientos": 200,
    "doscientas": 200,
    "trescientos": 300,
    "trescientas": 300,
    "cuatrocientos": 400,
    "cuatrocientas": 400,
    "quinientos": 500,
    "quinientas": 500,
    "seiscientos": 600,
    "seiscientas": 600,
    "setecientos": 700,
    "setecientas": 700,
    "ochocientos": 800,
    "ochocientas": 800,
    "novecientos": 900,
    "novecientas": 900,
}


@dataclass(frozen=True)
class NormalizacionResultado:
    """Resultado de normalizar un texto para evaluacion."""

    texto: str
    tokens: list[str]
    n_inaudible: int
    n_solapado: int
    n_musica: int
    n_ruido: int


def quitar_tildes_preservando_enie(texto: str) -> str:
    """Convierte a minusculas y elimina diacríticos preservando la letra n con virgulilla."""
    texto = texto.lower()
    marcador = "\u0000ENIE\u0000"
    texto = texto.replace("ñ", marcador)
    descompuesto = unicodedata.normalize("NFD", texto)
    sin_diacriticos = "".join(ch for ch in descompuesto if unicodedata.category(ch) != "Mn")
    return sin_diacriticos.replace(marcador, "ñ")


def _parsear_grupos_menores_1000(tokens: list[str], inicio: int) -> tuple[int, int] | None:
    """Parsea un numero espanol valido en [0, 999] respetando orden posicional."""
    n = len(tokens)
    i = inicio
    if i >= n:
        return None

    valor = 0
    tiene = False

    # 1. Centenas opcionales (maximo 1)
    if tokens[i] in _CENTENAS:
        cent = _CENTENAS[tokens[i]]
        # 'cien' solo es valido sin unidad/decena detras
        if tokens[i] == "cien":
            return 100, 1
        valor += cent
        tiene = True
        i += 1

    # 2. Parte < 100 opcional (maximo 1)
    if i < n:
        tok = tokens[i]
        if tok in _ESPECIALES_10_29:
            valor += _ESPECIALES_10_29[tok]
            tiene = True
            i += 1
        elif tok in _DECENAS:
            valor += _DECENAS[tok]
            tiene = True
            i += 1
            if i + 1 < n and tokens[i] == "y" and tokens[i + 1] in _UNIDADES:
                valor += _UNIDADES[tokens[i + 1]]
                i += 2
        elif tok in _UNIDADES:
            valor += _UNIDADES[tok]
            tiene = True
            i += 1
        elif tok in {"un", "una"} and (tiene or (i + 1 < n and tokens[i + 1] in {"mil", "millon", "millones", "porcentaje"})):
            valor += 1
            tiene = True
            i += 1

    if not tiene:
        return None
    return valor, i - inicio


def _parsear_bloque_numerico(tokens: list[str], inicio: int) -> tuple[int, int] | None:
    """Intenta parsear una secuencia de palabras numericas en [0, 999999].

    Respeta el orden posicional del espanol ([<1000] + 'mil' + [<1000]) para evitar
    sumar numeros adyacentes independientes como 'uno dos tres'.
    """
    n = len(tokens)
    if inicio >= n:
        return None

    # Caso 'mil ...' sin multiplicador explicito
    if tokens[inicio] == "mil":
        resto = _parsear_grupos_menores_1000(tokens, inicio + 1)
        if resto is not None:
            return 1000 + resto[0], 1 + resto[1]
        return 1000, 1

    primero = _parsear_grupos_menores_1000(tokens, inicio)
    if primero is None:
        return None

    val_1, cons_1 = primero
    idx_despues = inicio + cons_1
    if idx_despues < n and tokens[idx_despues] == "mil":
        miles = val_1 * 1000
        resto = _parsear_grupos_menores_1000(tokens, idx_despues + 1)
        if resto is not None:
            return miles + resto[0], cons_1 + 1 + resto[1]
        return miles, cons_1 + 1

    return val_1, cons_1


def _convertir_numeros_en_palabras(tokens: list[str]) -> list[str]:
    """Convierte secuencias numericas verbales en espanol a digitos de forma segura."""
    resultado: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok in {"un", "una"} and not (i + 1 < n and tokens[i + 1] in {"mil", "millon", "millones", "porcentaje"}):
            resultado.append(tok)
            i += 1
            continue
        parsed = _parsear_bloque_numerico(tokens, i)
        if parsed is not None:
            valor, consumidos = parsed
            resultado.append(str(valor))
            i += consumidos
        else:
            resultado.append(tok)
            i += 1
    return resultado


def normalizar_texto(texto: str) -> NormalizacionResultado:
    """Aplica la normalizacion determinista v1.0 definida en spec.md y research.md.

    Args:
        texto: Texto crudo en espanol (referencia gold o hipotesis ASR).

    Returns:
        Objeto ``NormalizacionResultado`` con texto normalizado, tokens y conteos
        de marcadores especiales encontrados.
    """
    if not texto:
        return NormalizacionResultado("", [], 0, 0, 0, 0)

    n_inaudible = len(_PATRON_INAUDIBLE.findall(texto))
    n_solapado = len(_PATRON_SOLAPADO.findall(texto))
    n_musica = len(_PATRON_MUSICA.findall(texto))
    n_ruido = len(_PATRON_RUIDO.findall(texto))

    limpio = _PATRON_INAUDIBLE.sub(" ", texto)
    limpio = _PATRON_SOLAPADO.sub(" ", limpio)
    limpio = _PATRON_MUSICA.sub(" ", limpio)
    limpio = _PATRON_RUIDO.sub(" ", limpio)

    # Minusculas y sin tildes (preservando ñ)
    limpio = quitar_tildes_preservando_enie(limpio)

    # Unificar porcentajes antes de limpiar puntuacion
    limpio = re.sub(r"(\d+(?:[.,]\d+)?)\s*%", r"\1 porcentaje ", limpio)
    limpio = re.sub(r"\bpor\s+ciento\b", " porcentaje ", limpio)

    # Separadores de miles: 10.000 / 10,000 -> 10000 (repetir por millones)
    while re.search(r"\b(\d{1,3})[.,](\d{3})\b", limpio):
        limpio = re.sub(r"\b(\d{1,3})[.,](\d{3})\b", r"\1\2", limpio)

    # Decimales con coma -> punto: 3,5 -> 3.5
    limpio = re.sub(r"\b(\d+),(\d+)\b", r"\1.\2", limpio)

    # Reemplazar guiones y barras por espacio
    limpio = re.sub(r"[-—_/]", " ", limpio)

    # Conservar solo [a-z0-9ñ.\s] y quitar puntos que no unan digitos
    limpio = re.sub(r"[^a-z0-9ñ.\s]", " ", limpio)
    limpio = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", limpio)

    tokens_crudos = [t for t in limpio.split() if t and t not in _MULETILLAS_CERRADAS]
    tokens_norm = _convertir_numeros_en_palabras(tokens_crudos)
    texto_norm = " ".join(tokens_norm)

    return NormalizacionResultado(
        texto=texto_norm,
        tokens=tokens_norm,
        n_inaudible=n_inaudible,
        n_solapado=n_solapado,
        n_musica=n_musica,
        n_ruido=n_ruido,
    )
