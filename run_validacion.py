"""Script de línea de comandos: valida un CSV de ventas antes de cargarlo.

Uso:
    python run_validacion.py data/ventas.csv

Códigos de salida:
    0  todas las reglas se cumplen (se puede cargar)
    1  alguna regla falla (BLOQUEA la carga)
    2  el archivo no existe o no se pudo leer
"""
from __future__ import annotations

import sys

import pandas as pd

from validar_ventas import REGLAS, validar


def main(argv: list[str]) -> int:
    ruta = argv[1] if len(argv) > 1 else "data/ventas.csv"
    try:
        df = pd.read_csv(ruta)
    except (FileNotFoundError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        print(f"ERROR: no se pudo leer '{ruta}': {exc}")
        return 2

    print(f"Validando {ruta}: {len(df)} filas, {len(REGLAS)} reglas")
    incumplidas = validar(df)

    if incumplidas:
        print(f"\nVALIDACIÓN FALLIDA: {len(incumplidas)} regla(s) incumplida(s)")
        for mensaje in incumplidas:
            print(f"  - {mensaje}")
        print("\nLa carga al warehouse queda BLOQUEADA (código de salida 1).")
        return 1

    print("\nVALIDACIÓN EXITOSA: los datos pueden cargarse (código de salida 0).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
