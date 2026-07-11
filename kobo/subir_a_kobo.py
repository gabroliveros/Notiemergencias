# -*- coding: utf-8 -*-
"""
Orquestador final del pipeline de alertas: toma el xlsx de noticias ya
procesado (limpieza_clasificacion) y el xlsx de métricas de alerta
(metricas_alerta), selecciona las noticias relevantes, prepara ambos
conjuntos de datos en el formato que esperan los XLSForm de Kobo, y los
envía usando kobo/gestionar_formularios.py.

Histórico: ninguna corrida borra datos de Kobo (eso solo lo hace
gestionar_formularios.upload_koboform, y a propósito no forma parte de este
pipeline). Las métricas de alerta se acumulan corrida tras corrida sin
deduplicar — eso es lo que arma la línea de tiempo en el tablero. Las
noticias sí se deduplican contra un registro local (registro_envios_kobo,
ver RUTA_REGISTRO_ENVIOS_DEFAULT) para no subir el mismo enlace repetido en
cada corrida solo porque sigue cayendo dentro de la ventana de 48h.

Uso:
    python -m kobo.subir_a_kobo <noticias_procesadas.xlsx> <alertas.xlsx> <api_token> [minimo_noticias]
"""

import json
import os
import sys

import pandas as pd

from procesamiento.metricas_alerta import canonicalizar_eventos, extraer_dominio, extraer_estado, _reconstruir_lista
from kobo.xlsform_builder import nombre_choice
from kobo.gestionar_formularios import enviar_filas

FORM_ID_NOTICIAS = 'noticias_emergencia_vzla'
FORM_ID_METRICAS = 'metricas_alerta_vzla'

ORDEN_NIVEL = {'Rojo': 0, 'Naranja': 1, 'Amarillo': 2, 'Verde': 3}

RUTA_REGISTRO_ENVIOS_DEFAULT = 'noticias_enviadas_kobo.json'


def cargar_registro_envios(ruta=RUTA_REGISTRO_ENVIOS_DEFAULT):
    """Devuelve el conjunto de URLs de noticias que ya se subieron a Kobo en
    corridas anteriores (para no duplicarlas)."""
    if os.path.exists(ruta):
        with open(ruta, encoding='utf-8') as f:
            return set(json.load(f))
    return set()


def guardar_registro_envios(urls, ruta=RUTA_REGISTRO_ENVIOS_DEFAULT):
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(sorted(urls), f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# Selección y enriquecimiento de noticias
# --------------------------------------------------------------------------

def enriquecer_noticias_con_alerta(df_noticias, df_alertas):
    """
    Agrega a cada noticia su 'estado', 'tipo_evento' y 'nivel_alerta_asociado',
    tomando el nivel más severo entre los grupos (estado, tipo_evento) a los
    que pertenece esa noticia. Descarta noticias sin estado o sin tipo de
    evento reconocible.
    """
    df = df_noticias.copy()
    df['estado'] = df['criterio_busqueda'].apply(extraer_estado)
    df['tipos_evento_canonico'] = df['eventos'].apply(canonicalizar_eventos)
    df = df[df['estado'].notna() & df['tipos_evento_canonico'].map(len).gt(0)].copy()

    mapa_alerta = {(r.estado, r.tipo_evento): r.nivel_alerta for r in df_alertas.itertuples()}

    def _mejor_match(row):
        candidatos = [(tipo, mapa_alerta.get((row['estado'], tipo))) for tipo in row['tipos_evento_canonico']]
        candidatos = [(tipo, nivel) for tipo, nivel in candidatos if nivel is not None]
        if not candidatos:
            # La noticia no cayó en ninguna ventana de alerta activa (ej: muy vieja)
            return pd.Series({'tipo_evento': row['tipos_evento_canonico'][0], 'nivel_alerta_asociado': 'Verde'})
        tipo, nivel = min(candidatos, key=lambda x: ORDEN_NIVEL.get(x[1], 99))
        return pd.Series({'tipo_evento': tipo, 'nivel_alerta_asociado': nivel})

    df[['tipo_evento', 'nivel_alerta_asociado']] = df.apply(_mejor_match, axis=1)
    return df


def seleccionar_noticias(df_enriquecido, minimo=10):
    """Ordena por severidad de alerta (Rojo primero) y luego por fecha más
    reciente, devolviendo al menos `minimo` noticias (todas, si hay menos)."""
    df = df_enriquecido.copy()
    df['_orden'] = df['nivel_alerta_asociado'].map(ORDEN_NIVEL).fillna(9)
    df = df.sort_values(['_orden', 'fecha_dt'], ascending=[True, False])
    return df.head(minimo).drop(columns='_orden').reset_index(drop=True)


# --------------------------------------------------------------------------
# Preparación de filas en el formato exacto que espera cada XLSForm
# --------------------------------------------------------------------------

def preparar_fila_noticia(fila):
    fecha = fila['fecha_dt']
    fecha_str = fecha.strftime('%Y-%m-%d') if pd.notna(fecha) else ''

    return {
        'fecha': fecha_str,
        'titulo': fila.get('title', ''),
        'enlace': fila.get('url', ''),
        'estado': nombre_choice(fila['estado']),
        'tipo_evento': fila['tipo_evento'],
        'medio': extraer_dominio(fila.get('url', '')) or '',
        'nivel_alerta_asociado': fila['nivel_alerta_asociado'].lower(),
        'criterio_busqueda': fila.get('criterio_busqueda', ''),
    }


def preparar_fila_metrica(fila):
    fecha_calculo = pd.Timestamp(fila['fecha_calculo'])
    fecha_reciente = fila['fecha_mas_reciente']

    return {
        'fecha_calculo': fecha_calculo.isoformat(),
        'estado': nombre_choice(fila['estado']),
        'tipo_evento': fila['tipo_evento'],
        'ventana_horas': int(fila['ventana_horas']),
        'n_noticias': int(fila['n_noticias']),
        'n_fuentes_distintas': int(fila['n_fuentes_distintas']),
        'tiene_victimas': 'si' if fila['tiene_victimas'] else 'no',
        'tiene_rescate_activo': 'si' if fila['tiene_rescate_activo'] else 'no',
        'tiene_danios_estructurales': 'si' if fila['tiene_danios_estructurales'] else 'no',
        'fecha_mas_reciente': pd.Timestamp(fecha_reciente).isoformat() if pd.notna(fecha_reciente) else '',
        'nivel_alerta': fila['nivel_alerta'].lower(),
        'urls_relacionadas': fila.get('urls_relacionadas', ''),
    }


# --------------------------------------------------------------------------
# Pipeline completo
# --------------------------------------------------------------------------

def pipeline_completo(ruta_noticias_procesadas, ruta_alertas, api_token, minimo_noticias=10,
                       ruta_registro_envios=RUTA_REGISTRO_ENVIOS_DEFAULT):
    df_noticias = pd.read_excel(ruta_noticias_procesadas)
    for col in ['eventos', 'victimas', 'rescate', 'daños']:
        if col in df_noticias.columns:
            df_noticias[col] = df_noticias[col].apply(_reconstruir_lista)
    if 'fecha_dt' in df_noticias.columns:
        df_noticias['fecha_dt'] = pd.to_datetime(df_noticias['fecha_dt'], errors='coerce')

    df_alertas = pd.read_excel(ruta_alertas)

    if df_alertas.empty:
        print('El archivo de alertas está vacío — no hay nada que subir.')
        return

    # --- Noticias: se deduplican contra lo ya enviado en corridas anteriores ---
    urls_ya_enviadas = cargar_registro_envios(ruta_registro_envios)
    enriquecidas = enriquecer_noticias_con_alerta(df_noticias, df_alertas)
    enriquecidas_nuevas = enriquecidas[~enriquecidas['url'].isin(urls_ya_enviadas)]

    omitidas = len(enriquecidas) - len(enriquecidas_nuevas)
    if omitidas:
        print(f'{omitidas} noticias de la ventana ya se habían subido en corridas anteriores — se omiten.')

    seleccion = seleccionar_noticias(enriquecidas_nuevas, minimo=minimo_noticias)
    print(f'Noticias nuevas seleccionadas para subir: {len(seleccion)}')

    filas_noticias = [preparar_fila_noticia(fila) for _, fila in seleccion.iterrows()]

    # --- Métricas: SIN deduplicar, cada corrida agrega su snapshot (línea de tiempo) ---
    filas_metricas = [preparar_fila_metrica(fila) for _, fila in df_alertas.iterrows()]

    errores_noticias = []
    if filas_noticias:
        print('\nEnviando noticias...')
        errores_noticias = enviar_filas(FORM_ID_NOTICIAS, filas_noticias, api_token)

        indices_fallidos = {i for i, _, _ in errores_noticias}
        urls_enviadas_ok = {
            seleccion.iloc[i]['url'] for i in range(len(seleccion)) if i not in indices_fallidos
        }
        guardar_registro_envios(urls_ya_enviadas | urls_enviadas_ok, ruta_registro_envios)
    else:
        print('\nNo hay noticias nuevas por enviar en esta corrida.')

    print('\nEnviando métricas de alerta (snapshot de esta corrida, se acumula para el histórico)...')
    errores_metricas = enviar_filas(FORM_ID_METRICAS, filas_metricas, api_token)

    if errores_noticias:
        print('\nErrores al enviar noticias:', errores_noticias[:3], '...' if len(errores_noticias) > 3 else '')
    if errores_metricas:
        print('\nErrores al enviar métricas:', errores_metricas[:3], '...' if len(errores_metricas) > 3 else '')

    return errores_noticias, errores_metricas


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('Uso: python -m kobo.subir_a_kobo <noticias_procesadas.xlsx> <alertas.xlsx> <api_token> [minimo_noticias]')
        sys.exit(1)

    ruta_noticias = sys.argv[1]
    ruta_alertas_arg = sys.argv[2]
    token = sys.argv[3]
    minimo = int(sys.argv[4]) if len(sys.argv) > 4 else 10

    pipeline_completo(ruta_noticias, ruta_alertas_arg, token, minimo_noticias=minimo)