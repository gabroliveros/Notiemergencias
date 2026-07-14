# -*- coding: utf-8 -*-
"""
Compila los CSV que genera cada worker del scraper (uno por proceso, ver
RUTA_CSV en prebusqueda_multinavegador_emergencia.py) en un único xlsx
acumulado, y lo fusiona con las corridas anteriores sin duplicar registros.

Traducción a módulo de unir_partes_csv.ipynb, con una diferencia importante:
el notebook original asumía siempre exactamente 4 archivos ('_part1' a
'_part4' hardcodeados). Como el número de workers (NUM_BROWSERS) cambia entre
corridas, aquí se detectan automáticamente todos los '_part*.csv' presentes
en la carpeta — así no se queda ningún worker sin compilar si corriste con
2, 4, o cualquier otro número de procesos.
"""

import glob
import os

import pandas as pd

# Debe coincidir con RUTA_CSV en el scraper: <base>_part{worker_id}.csv
PATRON_PARTES_DEFAULT = 'ddg_noticias_OPEN_part*.csv'


def encontrar_archivos_partes(carpeta, patron=PATRON_PARTES_DEFAULT):
    """Devuelve la lista ordenada de CSV de partes encontrados en `carpeta`."""
    ruta_patron = os.path.join(carpeta, patron)
    archivos = sorted(glob.glob(ruta_patron))
    return archivos


def cargar_y_unir_partes(rutas_csv):
    """
    Carga todos los CSV de partes y los concatena, deduplicando por 'url'
    (o 'source_url' si viene de raspado de redes sociales).
    """
    if not rutas_csv:
        raise FileNotFoundError(
            'No se encontraron archivos de partes. Verifica la carpeta y el patrón '
            f'(esperado tipo: {PATRON_PARTES_DEFAULT}).'
        )

    partes = []
    for ruta in rutas_csv:
        try:
            df_parte = pd.read_csv(ruta, on_bad_lines='skip')
            partes.append(df_parte)
            print(f'{os.path.basename(ruta)}: {df_parte.shape}')
        except Exception as e:
            print(f'ADVERTENCIA: no se pudo leer {ruta}: {e}')

    df_unido = pd.concat(partes, ignore_index=True)
    print('Total unido (con posibles duplicados):', df_unido.shape)

    if 'url' not in df_unido.columns:
        # Formato de raspado de redes sociales
        df_unido = df_unido.drop(columns=['profile_url'], errors='ignore')
        if 'likes' not in df_unido.columns:
            df_unido['likes'] = ''
        if 'comments' not in df_unido.columns:
            df_unido['comments'] = ''
        df_unido = df_unido.drop_duplicates('source_url').reset_index(drop=True)
    else:
        # Formato DuckDuckGo (el que usa el scraper actual)
        df_unido = df_unido.drop_duplicates('url').reset_index(drop=True)

    # Columna residual que a veces aparece en encabezados mal formados del CSV
    df_unido = df_unido.drop(columns=['_collected_at;;'], errors='ignore')

    # displayed_url/snippet/rich_type llegan vacías o redundantes (snippet
    # es el mismo texto truncado que ya está completo en snippet_full) —
    # se descartan aquí, en el primer punto donde se persiste el archivo
    # acumulado, para que ningún archivo posterior del pipeline las cargue.
    df_unido = df_unido.drop(columns=['displayed_url', 'snippet', 'rich_type'], errors='ignore')

    print('Total unido (sin duplicados):', df_unido.shape, df_unido.columns.tolist())
    return df_unido


def fusionar_con_archivo_existente(df_nuevo, ruta_archivo_acumulado):
    """
    Si ya existe un archivo acumulado de corridas anteriores, lo carga y
    fusiona con los resultados nuevos (deduplicando). Si no existe, lo crea.
    """
    if os.path.exists(ruta_archivo_acumulado):
        df_anterior = pd.read_excel(ruta_archivo_acumulado)
        print('Archivo acumulado existente:', df_anterior.shape, df_anterior.columns.tolist())
    else:
        df_anterior = pd.DataFrame(columns=df_nuevo.columns)
        print(f'No existía archivo acumulado, se creará: {ruta_archivo_acumulado}')

    df_final = pd.concat([df_anterior, df_nuevo], ignore_index=True)
    print('Total tras fusionar:', df_final.shape)

    columna_dedupe = 'url' if 'url' in df_final.columns else 'source_url'
    df_final = df_final.drop_duplicates(columna_dedupe).reset_index(drop=True)
    print('Total tras eliminar duplicados:', df_final.shape)

    return df_final


def pipeline_completo(carpeta, ruta_archivo_acumulado, patron=PATRON_PARTES_DEFAULT):
    """Ejecuta el flujo completo: detectar partes -> unir -> fusionar con
    acumulado existente -> guardar."""
    rutas = encontrar_archivos_partes(carpeta, patron)
    print(f'Archivos de partes encontrados ({len(rutas)}):')
    for r in rutas:
        print(' -', os.path.basename(r))

    df_nuevo = cargar_y_unir_partes(rutas)
    df_final = fusionar_con_archivo_existente(df_nuevo, ruta_archivo_acumulado)

    df_final.to_excel(ruta_archivo_acumulado, index=False)
    print(f'Guardado: {ruta_archivo_acumulado}')
    return df_final


if __name__ == '__main__':
    import sys

    carpeta_entrada = sys.argv[1] if len(sys.argv) > 1 else '.'
    archivo_salida = sys.argv[2] if len(sys.argv) > 2 else 'noticias_crudas.xlsx'

    resultado = pipeline_completo(carpeta_entrada, archivo_salida)
    print(f'\nListo: {resultado.shape[0]} registros totales en {archivo_salida}')