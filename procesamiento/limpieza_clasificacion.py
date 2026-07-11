# -*- coding: utf-8 -*-
"""
    Limpieza, filtrado y clasificación de las noticias raspadas por el scraper.

    Traducción a módulo (desde procesamiento_busquedas_motor_final.ipynb) de:
        1) Apertura y acondicionamiento del libro (agrega columnas de trabajo)
        2) Limpieza y normalización de texto
        3) Filtrado de registros que no corresponden a Venezuela
        4) Clasificación por red social, zona, afectación y medios de logística
        5) NER (spaCy) para lugares y actores/autoridades
        6) Limpieza de entidades detectadas (blacklist + equivalencias)
"""

import re
from collections import Counter

import pandas as pd
from unidecode import unidecode

from procesamiento.diccionarios import (
    EMERGENCIAS,
    EQUIVALENCIAS_FRECUENCIA,
    CAMBIOS_VEHICULOS,
    ELIMINAR_VEHICULOS,
    VZLA_PATTERN,
    AMER_PATTERN,
    SIGNOS_PATTERN,
    REDES_SOCIALES,
    ESTADOS,
    BLACKLIST_LUGARES,
    EQUIVALENCIAS_LUGARES,
)

ZONAS = ['capital', 'andes', 'oriente', 'occidente', 'llanos', 'costa', 'barrio', 'urbanizacion']
AFECTACION = ['daños', 'victimas', 'rescate']
MEDIOS_LOGISTICA = ['aereo', 'acuatico', 'terrestre']


# --------------------------------------------------------------------------
# 1) Apertura y acondicionamiento
# --------------------------------------------------------------------------

def cargar_datos(ruta_excel):
    """Carga el xlsx generado por unir_partes_csv y agrega columnas de trabajo."""
    df = pd.read_excel(ruta_excel)
    df[['title_clean', 'snippet_full_clean', 'red_social']] = None, None, None
    return df


# --------------------------------------------------------------------------
# 2) Limpieza y normalización
# --------------------------------------------------------------------------

def limpiar_y_normalizar(df):
    df = df.copy()
    df[['title', 'snippet_full']] = df[['title', 'snippet_full']].astype(str).map(lambda x: x.strip())
    df = df[~df['url'].str.contains(r'jabertur\.net', na=False)]
    df = df[(df['snippet_full'] != '') & (df['snippet_full'] != 'nan') & (df['snippet_full'].notna())]

    df[['title_clean', 'snippet_full_clean']] = df[['title', 'snippet_full']].map(lambda x: unidecode(x.lower()))
    df['snippet_full_clean'] = df['snippet_full_clean'].str.replace(SIGNOS_PATTERN, ' ', regex=True)
    df['snippet_full_clean'] = df['snippet_full_clean'].str.replace(r'[.,]', '', regex=True)
    df['snippet_full_clean'] = df['snippet_full_clean'].str.replace(r'\s+', ' ', regex=True).str.strip()
    return df


def normalizar_fecha(df):
    """
    Convierte la columna 'fecha' (string 'YYYY-MM-DD', ya corregida en el
    scraper) a un datetime real en 'fecha_dt'. Filas sin fecha reconocible
    quedan con NaT (no se descartan, para no perder la noticia).

    NUEVO respecto al notebook original — avisar si no se quiere.
    """
    df = df.copy()
    df['fecha_dt'] = pd.to_datetime(df.get('fecha'), format='%Y-%m-%d', errors='coerce')
    return df


# --------------------------------------------------------------------------
# 3) Filtrado geográfico (solo Venezuela, excluyendo otros países)
# --------------------------------------------------------------------------

def filtrar_venezuela(df):
    mask_vzla = df['snippet_full_clean'].str.contains(VZLA_PATTERN, case=False, na=False)
    mask_otros_paises = df['snippet_full_clean'].str.contains(AMER_PATTERN, case=False, na=False)
    return df[mask_vzla & ~mask_otros_paises]


# --------------------------------------------------------------------------
# 4) Clasificación: red social, zonas, afectación, logística
# --------------------------------------------------------------------------

def clasificar_red_social(df):
    df = df.copy()
    patron_red = f"({'|'.join(REDES_SOCIALES)})"
    df['red_social'] = df['url'].str.extract(patron_red, expand=False, flags=re.IGNORECASE)
    df['red_social'] = df['red_social'].fillna('web').str.lower()
    return df


def _clasificar_ambiente(texto, lista_palabras):
    if pd.isna(texto):
        return ''
    pat = [p for p in lista_palabras if p in texto]
    return pat if pat else ''


def clasificar_categorias(df):
    """Agrega una columna por cada categoría de EMERGENCIAS (zona/afectación/
    logística/atención/eventos) con las palabras clave encontradas en cada registro."""
    df = df.copy()
    for categoria, palabras in EMERGENCIAS.items():
        df[categoria] = df['snippet_full_clean'].apply(lambda x: _clasificar_ambiente(x, palabras))
    return df


def frecuencias_por_columna(df, columna, agrupar_subcategorias=False):
    """Cuenta ocurrencias de una columna de listas (ej: 'aereo', 'eventos').
    Si agrupar_subcategorias=True, agrupa usando EQUIVALENCIAS_FRECUENCIA[columna]."""
    explot = df[columna].explode()
    limpio = explot.dropna().astype(str).str.strip().str.lower()

    if agrupar_subcategorias and columna in EQUIVALENCIAS_FRECUENCIA:
        equiv = EQUIVALENCIAS_FRECUENCIA[columna]
        for etiqueta, valores in equiv.items():
            limpio.loc[limpio.isin(valores)] = etiqueta

    conteo = limpio[limpio != ''].value_counts()
    conteo.index = conteo.index.str.capitalize()
    return conteo


def resumen_logistica_top10(df):
    """Top 10 de vehículos/maquinaria mencionados, unificando aéreo+acuático+terrestre."""
    c_aereo = frecuencias_por_columna(df, 'aereo')
    c_acuatico = frecuencias_por_columna(df, 'acuatico')
    c_terrestre = frecuencias_por_columna(df, 'terrestre')

    total = pd.concat([c_aereo, c_acuatico, c_terrestre]).groupby(level=0).sum()
    total = total.rename(index=CAMBIOS_VEHICULOS).groupby(level=0).sum()
    total = total.drop(labels=ELIMINAR_VEHICULOS, errors='ignore')
    return total.sort_values(ascending=False)[:10]


def generar_resumenes(df):
    """Genera todos los conteos/resúmenes exploratorios del notebook original.
    Devuelve un dict {nombre: pandas.Series} para imprimir o loguear."""
    resumenes = {
        'zonas_afectadas': df[ZONAS].apply(lambda x: x != '').sum().sort_values(ascending=False).rename(str.capitalize),
        'nivel_afectacion': df[AFECTACION].apply(lambda x: x != '').sum().sort_values(ascending=False).rename(str.capitalize),
        'logistica_categorias': df[MEDIOS_LOGISTICA].apply(lambda x: x != '').sum().sort_values(ascending=False).rename(str.capitalize),
        'vehiculos_top10': resumen_logistica_top10(df),
        'logistica_aerea': frecuencias_por_columna(df, 'aereo'),
        'logistica_acuatica': frecuencias_por_columna(df, 'acuatico'),
        'logistica_terrestre': frecuencias_por_columna(df, 'terrestre'),
        'centros_atencion': frecuencias_por_columna(df, 'atencion', agrupar_subcategorias=True),
        'tipos_eventos': frecuencias_por_columna(df, 'eventos', agrupar_subcategorias=True),
    }
    return resumenes


# --------------------------------------------------------------------------
# 5) NER — lugares y actores/autoridades
# --------------------------------------------------------------------------

def extraer_entidades_ner(df, columna='snippet_full_clean', modelo='es_core_news_lg'):
    """
    Carga spaCy (perezosamente, solo si se llama esta función) y extrae:
      - 'lugares': entidades LOC
      - 'autoridades_actores': entidades PER y ORG
    """
    import spacy

    nlp = spacy.load(modelo)
    lugares_por_celda = []
    actores_por_celda = []

    for doc in nlp.pipe(df[columna].astype(str), batch_size=50):
        lugares = [ent.text for ent in doc.ents if ent.label_ == 'LOC']
        actores = [ent.text for ent in doc.ents if ent.label_ in ('PER', 'ORG')]
        lugares_por_celda.append(lugares if lugares else '')
        actores_por_celda.append(actores if actores else '')

    df = df.copy()
    df['lugares'] = lugares_por_celda
    df['autoridades_actores'] = actores_por_celda
    return df


# --------------------------------------------------------------------------
# 6) Limpieza de entidades (lugares) — blacklist + equivalencias
# --------------------------------------------------------------------------

def _limpiar_lista_lugares(lista_lugares):
    if not isinstance(lista_lugares, list):
        return []

    limpios = []
    for lugar in lista_lugares:
        lugar = unidecode(lugar.lower().strip())
        lugar = EQUIVALENCIAS_LUGARES.get(lugar, lugar)
        if lugar.startswith('estado '):
            lugar = lugar.replace('estado ', '')
        if lugar.startswith('edo '):
            lugar = lugar.replace('edo ', '')
        if lugar.endswith(' venezuela'):
            lugar = lugar.replace(' venezuela', '')
        if lugar.endswith(' vzla'):
            lugar = lugar.replace(' vzla', '')
        if lugar.startswith('#'):
            lugar = lugar.replace('#', '')
        if lugar.endswith(' #'):
            lugar = lugar.replace(' #', '')

        if (
            lugar not in BLACKLIST_LUGARES
            and len(lugar) > 3
            and not re.match(r'^[^\w\s]+$', lugar)
        ):
            limpios.append(lugar.strip().capitalize())

    return limpios


def limpiar_entidades_lugares(df):
    df = df.copy()
    df['lugares_clean'] = df['lugares'].apply(_limpiar_lista_lugares)
    return df


def resumen_lugares_y_actores(df, top_lugares=100, top_actores=15):
    todos_los_lugares = [lug for sublista in df['lugares_clean'] for lug in sublista]
    frecuencias_lugares = Counter(todos_los_lugares).most_common()

    set_estados = set(ESTADOS)
    top_estados = []
    for lugar, count in frecuencias_lugares[:16]:
        if lugar.lower() == 'caracas':
            top_estados.append(('Distrito capital', count))
        if lugar.lower() in set_estados:
            top_estados.append((lugar, count))

    top_destinos = [(lugar, count) for lugar, count in frecuencias_lugares[:top_lugares] if lugar.lower() not in set_estados]

    todos_los_actores = []
    for c in df['autoridades_actores']:
        if isinstance(c, list):
            todos_los_actores.extend(c)
    frecuencias_actores = Counter(todos_los_actores).most_common(top_actores)

    return {
        'total_lugares': len(todos_los_lugares),
        'top_estados': top_estados,
        'top_destinos': top_destinos,
        'total_actores': len(todos_los_actores),
        'top_actores': frecuencias_actores,
    }


# --------------------------------------------------------------------------
# Pipeline completo
# --------------------------------------------------------------------------

def pipeline_completo(ruta_excel_entrada, ruta_excel_salida, aplicar_ner=False):
    """Ejecuta todo el flujo: carga -> limpieza -> filtrado -> clasificación
    -> (opcional) NER -> limpieza de entidades -> guardado."""
    df = cargar_datos(ruta_excel_entrada)
    df = limpiar_y_normalizar(df)
    df = normalizar_fecha(df)
    df = filtrar_venezuela(df)
    df = clasificar_red_social(df)
    df = clasificar_categorias(df)

    if aplicar_ner:
        df = extraer_entidades_ner(df)
        df = limpiar_entidades_lugares(df)

    df.to_excel(ruta_excel_salida, index=False)
    return df


if __name__ == '__main__':
    import sys

    entrada = sys.argv[1] if len(sys.argv) > 1 else 'noticias_vzla_lluvias.xlsx'
    salida = sys.argv[2] if len(sys.argv) > 2 else 'noticias_vzla_lluvias_procesada.xlsx'

    resultado = pipeline_completo(entrada, salida)
    print(f'Procesado: {resultado.shape[0]} registros -> {salida}')

    resumenes = generar_resumenes(resultado)
    for nombre, serie in resumenes.items():
        print(f'\n{nombre}:')
        print(serie.to_string(header=False))

    if 'lugares_clean' in resultado.columns:
        info = resumen_lugares_y_actores(resultado)
        print(f"\nTotal de lugares detectados: {info['total_lugares']}")
        print('Estados por frecuencia (Top 10):', info['top_estados'])
        print(f"\nTotal de menciones a autoridades/actores: {info['total_actores']}")
        print('Top actores:', info['top_actores'])