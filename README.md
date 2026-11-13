# AndesMercado: validación de calidad de datos con CI

Validaciones en Python que **bloquean la carga** de ventas defectuosas, como la
del Black Friday (monto en centavos cargado como pesos). Caso de estudio de
Arquitectura de Software, Universidad EAN.

## Contenido

| Ruta | Para qué sirve |
|---|---|
| `validar_ventas.py` | Una función por regla de calidad y `validar(df)` |
| `run_validacion.py` | Script: sale con código **1** si alguna regla falla |
| `tests/test_validar_ventas.py` | Pruebas pytest (caso válido e inválido por regla) |
| `data/ventas.csv` | Anexo del caso, **con el error** del 28 de noviembre |
| `data/ventas_corregido.csv` | Mismos datos con los 3 montos corregidos |
| `.github/workflows/ci.yml` | GitHub Actions: pytest y luego validación de `ventas.csv` |
| `contratos/ventas_contrato.yaml` | Contrato de datos e-commerce / datos |
| `evidencia/` | Salida real de la ejecución local (ver más abajo) |

## Reglas implementadas

| Regla | Qué verifica |
|---|---|
| `columnas` | Exactamente `id_venta, fecha, canal, monto` |
| `id_venta` | Sin nulos ni duplicados |
| `canal` | Solo `tienda` o `en_linea` |
| `monto_maximo` | Ninguna venta supera COP 5.000.000 |
| `total_diario` | Total diario por canal ≤ 3 veces el promedio de los días anteriores |
| `fecha`, `monto_valido` | Reglas adicionales: fecha AAAA-MM-DD y monto numérico mayor que cero |

## Paso a paso (local)

Requisitos: Python 3.10 o superior y Git.

```bash
# 1. Descomprimir y entrar a la carpeta
unzip andesmercado-calidad-datos.zip
cd andesmercado-calidad-datos

# 2. Crear y activar un entorno virtual
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar las pruebas (deben pasar las 27)
python -m pytest -v

# 5. Validar el archivo con el error: debe FALLAR
python run_validacion.py data/ventas.csv
echo $?                            # Windows PowerShell: echo $LASTEXITCODE  -> 1

# 6. Validar el archivo corregido: debe PASAR
python run_validacion.py data/ventas_corregido.csv
echo $?                            # -> 0
```

Resultado esperado del paso 5: fallan `monto_maximo` (ventas 1012, 1013 y 1014)
y `total_diario` (canal `en_linea`, 2025-11-28). El error **no llega** al tablero.

## Paso a paso (GitHub Actions y evidencia del CI)

1. Crear un repositorio vacío en GitHub (por ejemplo `andesmercado-calidad-datos`).
2. Subir el proyecto:
   ```bash
   git init
   git add .
   git commit -m "Validaciones de calidad de datos y CI"
   git branch -M main
   git remote add origin https://github.com/<usuario>/andesmercado-calidad-datos.git
   git push -u origin main
   ```
3. Abrir la pestaña **Actions** del repositorio. El primer flujo termina en
   **rojo**: las pruebas pasan, pero el paso *Validar datos de ventas* falla
   porque `data/ventas.csv` contiene el error. **Captura 1** (flujo fallando).
4. Corregir los datos y subirlos:
   ```bash
   cp data/ventas_corregido.csv data/ventas.csv     # Windows: copy /Y
   git add data/ventas.csv
   git commit -m "Corregir montos en centavos del 28-nov"
   git push
   ```
5. En **Actions** el nuevo flujo termina en **verde**. **Captura 2** (flujo pasando).
6. Incluir ambas capturas en el informe o en el repositorio.

Opcional (recomendado): en *Settings > Branches* proteger `main` y exigir que el
flujo pase antes de hacer merge. Así ningún cambio llega a producción sin validación.

## Cómo usarlo en el pipeline real

Ejecutar `python run_validacion.py <archivo.csv>` **antes** de cargar al
warehouse. Si el código de salida es distinto de 0, el orquestador debe detener la
carga y enviar una alerta. Para la regla `total_diario` en producción, pasar el
histórico ya cargado: `validar(df, historico=df_warehouse)`.
