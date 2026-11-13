"""Reglas de calidad de datos para el archivo de ventas de AndesMercado.

Cada regla es una función que recibe un DataFrame y devuelve una lista de
mensajes de detalle. Lista vacía = la regla se cumple. La función ``validar``
ejecuta todas las reglas y devuelve las incumplidas con el formato
``"nombre_regla: detalle"``.

Las reglas son tolerantes: si falta una columna que necesitan, no fallan con
una excepción (esa ausencia ya la reporta ``regla_columnas``).
"""
from __future__ import annotations

import pandas as pd

COLUMNAS_ESPERADAS = ["id_venta", "fecha", "canal", "monto"]
CANALES_VALIDOS = {"tienda", "en_linea"}
MONTO_MAXIMO = 5_000_000          # COP, regla de negocio de AndesMercado
FACTOR_TOTAL_DIARIO = 3           # máximo 3x el promedio de días anteriores


# --------------------------------------------------------------------------
# Reglas individuales
# --------------------------------------------------------------------------
def regla_columnas(df: pd.DataFrame) -> list[str]:
    """El archivo tiene exactamente las columnas id_venta, fecha, canal y monto."""
    actuales = list(df.columns)
    faltan = [c for c in COLUMNAS_ESPERADAS if c not in actuales]
    sobran = [c for c in actuales if c not in COLUMNAS_ESPERADAS]
    repetidas = sorted({c for c in actuales if actuales.count(c) > 1})
    detalles = []
    if faltan:
        detalles.append(f"faltan columnas {faltan}")
    if sobran:
        detalles.append(f"columnas no esperadas {sobran}")
    if repetidas:
        detalles.append(f"columnas repetidas {repetidas}")
    return detalles


def regla_id_venta(df: pd.DataFrame) -> list[str]:
    """id_venta no tiene nulos ni duplicados."""
    if "id_venta" not in df.columns:
        return []
    detalles = []
    nulos = int(df["id_venta"].isna().sum())
    if nulos:
        detalles.append(f"{nulos} id_venta nulos")
    duplicados = df["id_venta"].dropna()
    duplicados = sorted(duplicados[duplicados.duplicated()].unique().tolist())
    if duplicados:
        detalles.append(f"id_venta duplicados {duplicados}")
    return detalles


def regla_canal(df: pd.DataFrame) -> list[str]:
    """canal solo toma los valores 'tienda' o 'en_linea'."""
    if "canal" not in df.columns:
        return []
    invalidos = df.loc[~df["canal"].isin(CANALES_VALIDOS), "canal"]
    if invalidos.empty:
        return []
    valores = sorted({str(v) for v in invalidos})
    return [f"{len(invalidos)} filas con canal inválido {valores}"]


def regla_fecha(df: pd.DataFrame) -> list[str]:
    """fecha es una fecha válida (regla adicional)."""
    if "fecha" not in df.columns:
        return []
    convertidas = pd.to_datetime(df["fecha"], errors="coerce", format="%Y-%m-%d")
    malas = int(convertidas.isna().sum())
    return [f"{malas} fechas nulas o con formato distinto de AAAA-MM-DD"] if malas else []


def regla_monto_valido(df: pd.DataFrame) -> list[str]:
    """monto es numérico y mayor que cero (regla adicional)."""
    if "monto" not in df.columns:
        return []
    montos = pd.to_numeric(df["monto"], errors="coerce")
    no_numericos = int(montos.isna().sum())
    no_positivos = int((montos <= 0).sum())
    detalles = []
    if no_numericos:
        detalles.append(f"{no_numericos} montos nulos o no numéricos")
    if no_positivos:
        detalles.append(f"{no_positivos} montos menores o iguales a cero")
    return detalles


def regla_monto_maximo(df: pd.DataFrame, maximo: float = MONTO_MAXIMO) -> list[str]:
    """Ninguna venta individual supera COP 5.000.000."""
    if "monto" not in df.columns:
        return []
    montos = pd.to_numeric(df["monto"], errors="coerce")
    excedidas = df.loc[montos > maximo]
    if excedidas.empty:
        return []
    ids = excedidas["id_venta"].tolist() if "id_venta" in df.columns else list(excedidas.index)
    return [f"{len(excedidas)} ventas superan COP {maximo:,.0f}: id_venta {ids}"]


def regla_total_diario(
    df: pd.DataFrame,
    factor: float = FACTOR_TOTAL_DIARIO,
    historico: pd.DataFrame | None = None,
) -> list[str]:
    """El total diario por canal no supera 3 veces el promedio de los días anteriores.

    Para cada (canal, día) se compara el total con ``factor`` veces el promedio
    de los totales diarios de los días anteriores del mismo canal. El primer día
    de cada canal no tiene historia y no se evalúa. Si se pasa ``historico``
    (por ejemplo las ventas ya cargadas en el warehouse), se usa además de los
    días del propio archivo.
    """
    if not {"fecha", "canal", "monto"}.issubset(df.columns):
        return []
    base = df if historico is None else pd.concat([historico, df], ignore_index=True)
    base = base[["fecha", "canal", "monto"]].copy()
    base["fecha"] = pd.to_datetime(base["fecha"], errors="coerce", format="%Y-%m-%d")
    base["monto"] = pd.to_numeric(base["monto"], errors="coerce")
    base = base.dropna()
    if base.empty:
        return []

    diario = base.groupby(["canal", "fecha"], as_index=False)["monto"].sum()
    fechas_archivo = set(
        pd.to_datetime(df["fecha"], errors="coerce", format="%Y-%m-%d").dropna()
    )
    detalles = []
    for canal, grupo in diario.groupby("canal"):
        grupo = grupo.sort_values("fecha")
        for i, fila in enumerate(grupo.itertuples(index=False)):
            if fila.fecha not in fechas_archivo or i == 0:
                continue
            promedio = grupo["monto"].iloc[:i].mean()
            umbral = factor * promedio
            if fila.monto > umbral:
                detalles.append(
                    f"canal {canal}, {fila.fecha:%Y-%m-%d}: total {fila.monto:,.2f} "
                    f"supera {factor}x el promedio previo ({promedio:,.2f}; umbral {umbral:,.2f})"
                )
    return detalles


# --------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------
REGLAS = [
    ("columnas", regla_columnas),
    ("id_venta", regla_id_venta),
    ("canal", regla_canal),
    ("fecha", regla_fecha),
    ("monto_valido", regla_monto_valido),
    ("monto_maximo", regla_monto_maximo),
    ("total_diario", regla_total_diario),
]


def validar(df: pd.DataFrame, historico: pd.DataFrame | None = None) -> list[str]:
    """Ejecuta todas las reglas y devuelve la lista de reglas incumplidas.

    Cada elemento tiene la forma ``"nombre_regla: detalle"``. Lista vacía
    significa que los datos pueden cargarse.
    """
    incumplidas: list[str] = []
    for nombre, regla in REGLAS:
        if nombre == "total_diario":
            detalles = regla(df, historico=historico)
        else:
            detalles = regla(df)
        incumplidas.extend(f"{nombre}: {d}" for d in detalles)
    return incumplidas
