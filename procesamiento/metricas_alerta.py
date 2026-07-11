# -*- coding: utf-8 -*-
"""
Calcula métricas y niveles de alerta por estado, a partir del xlsx ya
procesado por limpieza_clasificacion.py. La salida de este módulo es lo que
se sube a KoboToolbox (subir_a_kobo.py, pendiente) para que el tablero de
Power BI solo tenga que leer y mostrar, sin recalcular nada.

Reglas de alerta:
  - Ventana de tiempo:  últimas 48 horas (parámetro configurable).
  - Agregación:         por estado y tipo de evento canónico.
  - Rojo:               hay mención de víctimas, confirmada por >= 2 fuentes distintas.
  - Naranja:            hay rescate activo o daños estructurales mencionados (>=1 fuente).
  - Amarillo:           >= 2 noticias sobre el evento, sin víctimas/rescate/daños confirmados.
  - Verde:              1 sola noticia, sin señales de impacto. Informativo, no dispara acción.
"""

from urllib.parse import urlparse

import pandas as pd

from procesamiento.diccionarios import ESTADOS

VENTANA_HORAS_DEFAULT = 48

# Mapeo exacto de cada palabra clave de EMERGENCIAS['eventos'] a un tipo de
# evento canónico, para poder agrupar/alertar por tipo.
MAPA_EVENTO_CANONICO = {
    'sismo': 'sismo', 'terremoto': 'sismo', 'temblor': 'sismo', 'replica': 'sismo', 'escala richter': 'sismo',
    'inundacion': 'inundacion', 'anegacion': 'inundacion', 'desbordamiento': 'inundacion', 'crecida': 'inundacion',
    'deslave': 'deslave', 'derrumbe': 'deslave', 'deslizamiento': 'deslave', 'alud': 'deslave', 'barro': 'deslave',
    'aguacero': 'lluvias', 'tormenta': 'lluvias', 'precipitaciones': 'lluvias', 'vaguada': 'lluvias',
    'lluvia': 'lluvias', 'onda tropical': 'lluvias',
}

_ESTADOS_ORDENADOS = sorted(ESTADOS, key=len, reverse=True)  # más largos primero (ej: "la guaira" antes que "la")


def extraer_estado(criterio_busqueda):
    """
    Identifica el estado de Venezuela mencionado en criterio_busqueda (la
    query que generó el registro). Devuelve el nombre del estado o None si
    no se reconoce ninguno.
    """
    if not isinstance(criterio_busqueda, str):
        return None
    texto = criterio_busqueda.lower()
    for estado in _ESTADOS_ORDENADOS:
        if estado in texto:
            return estado
    return None


def extraer_dominio(url):
    """Extrae el dominio (sin 'www.') de una URL, para contar fuentes distintas."""
    if not isinstance(url, str) or not url:
        return None
    dominio = urlparse(url).netloc.lower()
    return dominio[4:] if dominio.startswith('www.') else dominio


def canonicalizar_eventos(lista_eventos):
    """Convierte la lista de palabras clave detectadas en df['eventos'] a
    una lista de tipos canónicos (sismo/inundacion/deslave/lluvias), sin duplicar."""
    if not isinstance(lista_eventos, list):
        return []
    canonicos = {MAPA_EVENTO_CANONICO[e] for e in lista_eventos if e in MAPA_EVENTO_CANONICO}
    return sorted(canonicos)


def preparar_dataframe_alertas(df):
    """
    Agrega columnas 'estado' y 'tipo_evento' y explota por tipo_evento
    (un registro que menciona lluvias E inundación cuenta para ambos grupos).
    Descarta registros sin estado o sin tipo de evento reconocido.
    """
    df = df.copy()
    df['estado'] = df['criterio_busqueda'].apply(extraer_estado)
    df['dominio'] = df['url'].apply(extraer_dominio)
    df['tipo_evento'] = df['eventos'].apply(canonicalizar_eventos)

    sin_estado = df['estado'].isna().sum()
    if sin_estado:
        print(f'ADVERTENCIA: {sin_estado} registros sin estado reconocible en criterio_busqueda (se excluyen).')

    df = df[df['estado'].notna()]
    df = df.explode('tipo_evento')
    df = df[df['tipo_evento'].notna()]
    return df


def _clasificar_nivel(grupo):
    """Aplica las reglas de alerta a un grupo (estado, tipo_evento) ya filtrado por ventana."""
    tiene_victimas = grupo['victimas'].apply(lambda x: bool(x)).any()
    tiene_rescate = grupo['rescate'].apply(lambda x: bool(x)).any()
    tiene_danios = grupo['daños'].apply(lambda x: bool(x)).any()

    fuentes_victimas = grupo.loc[grupo['victimas'].apply(bool), 'dominio'].dropna().nunique()

    if tiene_victimas and fuentes_victimas >= 2:
        return 'Rojo'
    if tiene_rescate or tiene_danios:
        return 'Naranja'
    if len(grupo) >= 2:
        return 'Amarillo'
    return 'Verde'


def calcular_metricas_alerta(df, ventana_horas=VENTANA_HORAS_DEFAULT, ahora=None):
    """
    Calcula, por (estado, tipo_evento), las métricas y el nivel de alerta
    dentro de la ventana de tiempo indicada.

    Requiere que `df` ya haya pasado por limpieza_clasificacion.pipeline_completo
    (necesita las columnas: fecha_dt, criterio_busqueda, url, eventos,
    victimas, rescate, daños, title).
    """
    ahora = ahora or pd.Timestamp.now()
    limite = ahora - pd.Timedelta(hours=ventana_horas)

    df_prep = preparar_dataframe_alertas(df)

    sin_fecha = df_prep['fecha_dt'].isna().sum()
    if sin_fecha:
        print(f'ADVERTENCIA: {sin_fecha} registros sin fecha reconocible, se excluyen del cálculo de alerta '
              f'(pero siguen disponibles en el xlsx de noticias completo).')

    df_ventana = df_prep[df_prep['fecha_dt'].notna() & (df_prep['fecha_dt'] >= limite) & (df_prep['fecha_dt'] <= ahora)]

    filas = []
    for (estado, tipo_evento), grupo in df_ventana.groupby(['estado', 'tipo_evento']):
        filas.append({
            'estado': estado,
            'tipo_evento': tipo_evento,
            'ventana_horas': ventana_horas,
            'fecha_calculo': ahora,
            'n_noticias': len(grupo),
            'n_fuentes_distintas': grupo['dominio'].dropna().nunique(),
            'tiene_victimas': bool(grupo['victimas'].apply(bool).any()),
            'tiene_rescate_activo': bool(grupo['rescate'].apply(bool).any()),
            'tiene_danios_estructurales': bool(grupo['daños'].apply(bool).any()),
            'fecha_mas_reciente': grupo['fecha_dt'].max(),
            'nivel_alerta': _clasificar_nivel(grupo),
            'urls_relacionadas': ' | '.join(grupo['url'].dropna().unique()),
        })

    resultado = pd.DataFrame(filas)
    if resultado.empty:
        print('Sin registros dentro de la ventana de tiempo indicada — no hay alertas que calcular.')
        return resultado

    orden_nivel = {'Rojo': 0, 'Naranja': 1, 'Amarillo': 2, 'Verde': 3}
    resultado['_orden'] = resultado['nivel_alerta'].map(orden_nivel)
    resultado = resultado.sort_values(['_orden', 'n_noticias'], ascending=[True, False]).drop(columns='_orden')
    return resultado.reset_index(drop=True)


def pipeline_completo(ruta_excel_procesado, ruta_excel_salida, ventana_horas=VENTANA_HORAS_DEFAULT):
    df = pd.read_excel(ruta_excel_procesado)

    # Las columnas de listas (eventos, victimas, rescate, daños) se guardan
    # como texto al pasar por xlsx; hay que reconstruirlas antes de calcular.
    columnas_lista = ['eventos', 'victimas', 'rescate', 'daños']
    for col in columnas_lista:
        if col in df.columns:
            df[col] = df[col].apply(_reconstruir_lista)

    if 'fecha_dt' in df.columns:
        df['fecha_dt'] = pd.to_datetime(df['fecha_dt'], errors='coerce')

    resultado = calcular_metricas_alerta(df, ventana_horas=ventana_horas)
    resultado.to_excel(ruta_excel_salida, index=False)
    print(f'Guardado: {ruta_excel_salida} ({len(resultado)} filas de alerta)')
    return resultado


def _reconstruir_lista(valor):
    """
    Las columnas de tipo lista (ej. ['inundacion', 'lluvia']) se guardan como
    el string "['inundacion', 'lluvia']" al pasar por to_excel/read_excel.
    Esta función las reconstruye a listas reales de Python.
    """
    if isinstance(valor, list):
        return valor
    if pd.isna(valor) or valor == '':
        return []
    if isinstance(valor, str):
        import ast
        try:
            reconstruido = ast.literal_eval(valor)
            return reconstruido if isinstance(reconstruido, list) else []
        except (ValueError, SyntaxError):
            return []
    return []


if __name__ == '__main__':
    import sys

    entrada = sys.argv[1] if len(sys.argv) > 1 else 'noticias_vzla_lluvias_procesada.xlsx'
    salida = sys.argv[2] if len(sys.argv) > 2 else 'alertas_por_estado.xlsx'
    ventana = int(sys.argv[3]) if len(sys.argv) > 3 else VENTANA_HORAS_DEFAULT

    resultado = pipeline_completo(entrada, salida, ventana_horas=ventana)
    if not resultado.empty:
        print('\nResumen de alertas:')
        print(resultado[['estado', 'tipo_evento', 'nivel_alerta', 'n_noticias', 'n_fuentes_distintas']].to_string(index=False))