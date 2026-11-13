"""Pruebas de las reglas de calidad de ventas.

Para cada regla hay al menos un caso válido (devuelve lista vacía) y uno
inválido (devuelve detalles). Al final hay pruebas de integración con los
archivos del anexo y con el script de línea de comandos.
"""
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run_validacion  # noqa: E402
from validar_ventas import (  # noqa: E402
    regla_canal,
    regla_columnas,
    regla_fecha,
    regla_id_venta,
    regla_monto_maximo,
    regla_monto_valido,
    regla_total_diario,
    validar,
)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ventas_validas() -> pd.DataFrame:
    """Tres días de ventas normales en ambos canales."""
    return pd.DataFrame(
        {
            "id_venta": [1, 2, 3, 4, 5, 6],
            "fecha": ["2025-11-25", "2025-11-25", "2025-11-26", "2025-11-26",
                      "2025-11-27", "2025-11-27"],
            "canal": ["tienda", "en_linea", "tienda", "en_linea", "tienda", "en_linea"],
            "monto": [120000.0, 180000.0, 100000.0, 200000.0, 150000.0, 210000.0],
        }
    )


def nombres(errores: list[str]) -> set[str]:
    return {e.split(":")[0] for e in errores}


# ---------------------------------------------------------------- datos válidos
def test_datos_validos_pasan_todas_las_reglas():
    assert validar(ventas_validas()) == []


# ---------------------------------------------------------------- regla columnas
def test_columnas_validas():
    assert regla_columnas(ventas_validas()) == []


def test_columnas_falta_una():
    df = ventas_validas().drop(columns=["monto"])
    assert regla_columnas(df) != []
    assert "columnas" in nombres(validar(df))


def test_columnas_sobra_una():
    df = ventas_validas().assign(descuento=0)
    assert regla_columnas(df) != []


# ---------------------------------------------------------------- regla id_venta
def test_id_venta_valido():
    assert regla_id_venta(ventas_validas()) == []


def test_id_venta_con_nulos():
    df = ventas_validas()
    df.loc[0, "id_venta"] = None
    assert any("nulos" in d for d in regla_id_venta(df))
    assert "id_venta" in nombres(validar(df))


def test_id_venta_duplicado():
    df = ventas_validas()
    df.loc[1, "id_venta"] = 1
    assert any("duplicados" in d for d in regla_id_venta(df))
    assert "id_venta" in nombres(validar(df))


# ---------------------------------------------------------------- regla canal
def test_canal_valido():
    assert regla_canal(ventas_validas()) == []


def test_canal_invalido():
    df = ventas_validas()
    df.loc[0, "canal"] = "marketplace"
    assert regla_canal(df) != []
    assert "canal" in nombres(validar(df))


def test_canal_distingue_mayusculas():
    df = ventas_validas()
    df.loc[0, "canal"] = "Tienda"
    assert regla_canal(df) != []


# ---------------------------------------------------------------- regla fecha
def test_fecha_valida():
    assert regla_fecha(ventas_validas()) == []


def test_fecha_invalida():
    df = ventas_validas()
    df.loc[0, "fecha"] = "28/11/2025"
    assert regla_fecha(df) != []
    assert "fecha" in nombres(validar(df))


# ---------------------------------------------------------------- regla monto válido
def test_monto_valido():
    assert regla_monto_valido(ventas_validas()) == []


def test_monto_no_numerico():
    df = ventas_validas()
    df["monto"] = df["monto"].astype(object)
    df.loc[0, "monto"] = "abc"
    assert regla_monto_valido(df) != []
    assert "monto_valido" in nombres(validar(df))


def test_monto_negativo_o_cero():
    df = ventas_validas()
    df.loc[0, "monto"] = -5.0
    df.loc[1, "monto"] = 0.0
    detalles = regla_monto_valido(df)
    assert any("menores o iguales a cero" in d for d in detalles)


# ---------------------------------------------------------------- regla monto máximo
def test_monto_maximo_valido_incluye_el_limite():
    df = ventas_validas()
    df.loc[0, "monto"] = 5_000_000  # justo en el límite: permitido
    assert regla_monto_maximo(df) == []


def test_monto_maximo_excedido():
    df = ventas_validas()
    df.loc[0, "monto"] = 5_000_001
    assert regla_monto_maximo(df) != []
    assert "monto_maximo" in nombres(validar(df))


# ---------------------------------------------------------------- regla total diario
def test_total_diario_valido():
    assert regla_total_diario(ventas_validas()) == []


def test_total_diario_excede_tres_veces_el_promedio():
    df = ventas_validas()
    # Mismo día 27, canal en_linea: muchas ventas pequeñas (<5M c/u) que suman
    # mucho más que 3x el promedio previo (190.000). Solo esta regla debe saltar.
    extra = pd.DataFrame(
        {
            "id_venta": [100, 101, 102],
            "fecha": ["2025-11-27"] * 3,
            "canal": ["en_linea"] * 3,
            "monto": [400000.0, 400000.0, 400000.0],
        }
    )
    df = pd.concat([df, extra], ignore_index=True)
    assert regla_total_diario(df) != []
    assert nombres(validar(df)) == {"total_diario"}


def test_total_diario_exactamente_tres_veces_pasa():
    df = pd.DataFrame(
        {
            "id_venta": [1, 2],
            "fecha": ["2025-11-25", "2025-11-26"],
            "canal": ["tienda", "tienda"],
            "monto": [100000.0, 300000.0],  # 3 x 100.000: en el límite, permitido
        }
    )
    assert regla_total_diario(df) == []


def test_total_diario_usa_historico_del_warehouse():
    historico = ventas_validas()
    nuevo = pd.DataFrame(
        {"id_venta": [50], "fecha": ["2025-11-28"], "canal": ["en_linea"],
         "monto": [4_000_000.0]}
    )
    # Solo con el archivo nuevo no hay historia y no se puede comparar...
    assert regla_total_diario(nuevo) == []
    # ...pero con el histórico del warehouse la venta de 4M se detecta.
    assert regla_total_diario(nuevo, historico=historico) != []


def test_total_diario_primer_dia_no_se_evalua():
    df = ventas_validas()[ventas_validas()["fecha"] == "2025-11-25"]
    assert regla_total_diario(df) == []


# ---------------------------------------------------------------- integración: anexo
def test_anexo_incidente_es_detectado():
    df = pd.read_csv(os.path.join(RAIZ, "data", "ventas.csv"))
    errores = validar(df)
    assert nombres(errores) == {"monto_maximo", "total_diario"}
    assert any("1012" in e and "1013" in e and "1014" in e for e in errores)
    assert any("en_linea" in e and "2025-11-28" in e for e in errores)


def test_anexo_corregido_pasa():
    df = pd.read_csv(os.path.join(RAIZ, "data", "ventas_corregido.csv"))
    assert validar(df) == []


# ---------------------------------------------------------------- integración: script CLI
def _csv_temporal(df: pd.DataFrame) -> str:
    fd, ruta = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    df.to_csv(ruta, index=False)
    return ruta


def test_script_sale_con_0_si_los_datos_son_validos():
    ruta = _csv_temporal(ventas_validas())
    try:
        assert run_validacion.main(["run_validacion.py", ruta]) == 0
    finally:
        os.remove(ruta)


def test_script_sale_con_1_si_alguna_regla_falla():
    df = ventas_validas()
    df.loc[0, "canal"] = "marketplace"
    ruta = _csv_temporal(df)
    try:
        assert run_validacion.main(["run_validacion.py", ruta]) == 1
    finally:
        os.remove(ruta)


def test_script_sale_con_2_si_el_archivo_no_existe():
    assert run_validacion.main(["run_validacion.py", "no_existe.csv"]) == 2
