# -*- coding: utf-8 -*-
"""
Orquestador final del pipeline de alertas: toma el xlsx de noticias ya
procesado (limpieza_clasificacion) y el xlsx de métricas de alerta
(metricas_alerta), selecciona las noticias relevantes, prepara ambos
conjuntos de datos en el formato que esperan los XLSForm de Kobo, y los
envía usando kobo/gestionar_formularios.py.

Histórico: ninguna corrida borra datos de Kobo (eso solo lo hace
gestionar_formularios.upload_koboform, y a propósito no forma parte de este
pipeline). Las métricas de alerta se acumulan corrida tras corrida 
deduplicando por estado|tipo_evento|día|nivel. Las noticias se deduplican 
contra un registro local (registro_envios_kobo, ver RUTA_REGISTRO_ENVIOS_DEFAULT)
para no subir el mismo enlace repetido en cada corrida solo porque sigue 
cayendo dentro de la ventana de xxhoras.

Uso:
    python -m kobo.subir_a_kobo <noticias_procesadas.xlsx> <alertas.xlsx> <api_token> [minimo_noticias]
"""

import json
import os
import sys

import pandas as pd

from procesamiento.metricas_alerta import (canonicalizar_eventos, extraer_dominio, extraer_estado, 
                                           _reconstruir_lista, filtrar_eventos_por_situacion)
from kobo.xlsform_builder import nombre_choice
from kobo.gestionar_formularios import enviar_filas

FORM_ID_NOTICIAS = 'noticias_emergencia'
FORM_ID_METRICAS = 'metricas_alerta'
FORM_ID_PRECIPITACION = 'precipitacion_nacional'

ORDEN_NIVEL = {'Rojo': 0, 'Naranja': 1, 'Amarillo': 2, 'Verde': 3}

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'env_prod.json'), encoding='utf-8') as f:
    _CFG_RUTAS = json.load(f).get('rutas', {})

RUTA_REGISTRO_ENVIOS_DEFAULT = _CFG_RUTAS.get('registro_envios_kobo')
RUTA_REGISTRO_ALERTAS_DEFAULT = _CFG_RUTAS.get('registro_alertas_kobo')

def cargar_registro_envios(ruta=RUTA_REGISTRO_ENVIOS_DEFAULT):
    """Devuelve el conjunto de URLs de noticias que ya se subieron a Kobo en
    corridas anteriores (para no duplicarlas)."""
    if os.path.exists(ruta):
        with open(ruta, encoding='utf-8') as f:
            return set(json.load(f))
    return set()


def guardar_registro_envios(urls, ruta=RUTA_REGISTRO_ENVIOS_DEFAULT):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(sorted(urls), f, ensure_ascii=False, indent=2)


def construir_clave_alerta(estado, tipo_evento, fecha_calculo, nivel_alerta):
    """Identifica de forma única un (estado, tipo_evento, nivel) dentro de un
    mismo día calendario. Mientras el nivel no cambie el mismo día, la clave
    se repite y la alerta no se vuelve a subir a Kobo."""
    fecha = pd.Timestamp(fecha_calculo).strftime('%Y-%m-%d')
    return f'{estado}|{tipo_evento}|{fecha}|{nivel_alerta}'


def cargar_registro_alertas(ruta=RUTA_REGISTRO_ALERTAS_DEFAULT):
    if os.path.exists(ruta):
        with open(ruta, encoding='utf-8') as f:
            return set(json.load(f))
    return set()


def guardar_registro_alertas(claves, ruta=RUTA_REGISTRO_ALERTAS_DEFAULT):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(sorted(claves), f, ensure_ascii=False, indent=2)


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
    df['estado'] = df['estado'].fillna(df['texto_clasificacion'].apply(extraer_estado))
    df['tipos_evento_canonico'] = df['eventos'].apply(canonicalizar_eventos)
    df = df[df['estado'].notna() & df['tipos_evento_canonico'].map(len).gt(0)].copy()

    if df.empty:
        df['tipo_evento'] = pd.Series(dtype=object)
        df['nivel_alerta_asociado'] = pd.Series(dtype=object)
        return df

    mapa_alerta = {(r.estado, r.tipo_evento): r.nivel_alerta for r in df_alertas.itertuples()}

    def _mejor_match(row):
        candidatos = [(tipo, mapa_alerta.get((row['estado'], tipo))) for tipo in row['tipos_evento_canonico']]
        candidatos = [(tipo, nivel) for tipo, nivel in candidatos if nivel is not None]
        if not candidatos:
            # La noticia no cayó en ninguna ventana de alerta activa (ej: muy vieja)
            return pd.Series({'tipo_evento': row['tipos_evento_canonico'][0], 'nivel_alerta_asociado': 'Verde'})
        tipo, nivel = min(candidatos, key=lambda x: ORDEN_NIVEL.get(x[1], 99))
        return pd.Series({'tipo_evento': tipo, 'nivel_alerta_asociado': nivel})

    df[['tipo_evento', 'nivel_alerta_asociado']] = df.apply(_mejor_match, axis=1, result_type='expand')
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


def preparar_fila_precipitacion(fila):
    return {
        'fecha_calculo': pd.Timestamp(fila['fecha_calculo']).isoformat(),
        'estado': fila['estado'],
        'capital': fila['capital'],
        'precipitacion_30dias': float(fila['precipitacion_30dias']),
        'saturacion': float(fila['saturacion']),
        'nivel_alerta': fila['nivel_alerta'],
        'umbral_amarillo': float(fila['umbral_amarillo']),
        'umbral_naranja': float(fila['umbral_naranja']),
        'umbral_rojo': float(fila['umbral_rojo']),
    }


# --------------------------------------------------------------------------
# Pipeline completo
# --------------------------------------------------------------------------

def _situaciones_lista(situacion):
    """Normaliza 'situacion' (puede venir como str, lista, o None) a una lista."""
    if situacion is None:
        return [None]
    return [situacion] if isinstance(situacion, str) else list(situacion)


def pipeline_precipitacion(df_precipitacion, api_token, username, form_id_precipitacion=FORM_ID_PRECIPITACION):
    """Sube el snapshot de precipitación nacional a Kobo. Sin deduplicar:
    cada corrida agrega un snapshot nuevo a la línea de tiempo."""
    filas = [preparar_fila_precipitacion(fila) for _, fila in df_precipitacion.iterrows()]
    if not filas:
        print('No hay datos de precipitación para enviar.')
        return []
    print('\nEnviando datos de precipitación nacional...')
    return enviar_filas(form_id_precipitacion, filas, api_token, username)


def pipeline_completo(
    ruta_noticias_procesadas,
    ruta_alertas,
    api_token,
    username,
    minimo_noticias=10,
    form_id_noticias=FORM_ID_NOTICIAS,
    form_id_metricas=FORM_ID_METRICAS,
    ruta_registro_envios=RUTA_REGISTRO_ENVIOS_DEFAULT,
    ruta_registro_alertas=RUTA_REGISTRO_ALERTAS_DEFAULT,
    situacion=None
):
    df_noticias = pd.read_excel(ruta_noticias_procesadas)
    for col in ['eventos', 'victimas', 'rescate', 'daños']:
        if col in df_noticias.columns:
            df_noticias[col] = df_noticias[col].apply(_reconstruir_lista)
    if 'fecha_dt' in df_noticias.columns:
        df_noticias['fecha_dt'] = pd.to_datetime(df_noticias['fecha_dt'], errors='coerce')

    df_alertas = pd.read_excel(ruta_alertas)

    if df_alertas.empty:
        print('El archivo de alertas está vacío — se subirán noticias relevantes sin nivel de alerta.')

    if df_noticias.empty:
        print('No hay noticias relevantes en esta corrida — se omite el envío de noticias.')
        filas_noticias = []
        seleccion = df_noticias
    else:
        # Noticias: se procesan y seleccionan por separado para cada
        # situación activa, para que ninguna le quite espacio a otra en el
        # top de noticias a subir
        urls_ya_enviadas = cargar_registro_envios(ruta_registro_envios)
        df_noticias['tipos_evento_canonico'] = df_noticias['eventos'].apply(canonicalizar_eventos)

        selecciones = []
        for sit in _situaciones_lista(situacion):
            if sit is not None:
                df_situacion = df_noticias[
                    df_noticias['tipos_evento_canonico'].apply(
                        lambda x: len(filtrar_eventos_por_situacion(x, sit)) > 0
                    )
                ]
            else:
                df_situacion = df_noticias

            if df_situacion.empty:
                print(f"'{sit}': ninguna noticia de esta corrida menciona esta situación.")
                continue

            enriquecidas = enriquecer_noticias_con_alerta(df_situacion, df_alertas)
            enriquecidas_nuevas = enriquecidas[~enriquecidas['url'].isin(urls_ya_enviadas)]

            omitidas = len(enriquecidas) - len(enriquecidas_nuevas)
            if omitidas:
                print(f"'{sit}': {omitidas} noticias ya se habían subido en corridas anteriores — se omiten.")

            if enriquecidas_nuevas.empty:
                print(f"'{sit}': sin noticias nuevas por subir en esta corrida.")
                continue

            seleccion_sit = seleccionar_noticias(enriquecidas_nuevas, minimo=minimo_noticias)
            print(f"'{sit}': {len(seleccion_sit)} noticias seleccionadas para subir.")
            selecciones.append(seleccion_sit)

        seleccion = pd.concat(selecciones, ignore_index=True).drop_duplicates(subset='url') if selecciones else df_noticias.iloc[0:0]
        filas_noticias = [preparar_fila_noticia(fila) for _, fila in seleccion.iterrows()]

    # --- Métricas: SIN deduplicar, cada corrida agrega su snapshot (línea de tiempo) ---
    # --- Métricas: se sube cada (estado, tipo_evento, día, nivel) una sola vez.
    # Si el nivel cambia el mismo día, o cambia el día, se considera una alerta
    # nueva y sí se sube; así se arma la línea de tiempo sin repetir snapshots
    # idénticos corrida tras corrida ---
    claves_alerta_ya_enviadas = cargar_registro_alertas(ruta_registro_alertas)
    df_alertas = df_alertas.copy()
    df_alertas['_clave_alerta'] = df_alertas.apply(
        lambda fila: construir_clave_alerta(fila['estado'], fila['tipo_evento'], fila['fecha_calculo'], fila['nivel_alerta']),
        axis=1
    )
    df_alertas_nuevas = df_alertas[~df_alertas['_clave_alerta'].isin(claves_alerta_ya_enviadas)]

    omitidas_alertas = len(df_alertas) - len(df_alertas_nuevas)
    if omitidas_alertas:
        print(f'{omitidas_alertas} alertas ya se habían subido en corridas anteriores (mismo estado/tipo_evento/día/nivel) — se omiten.')

    filas_metricas = [preparar_fila_metrica(fila) for _, fila in df_alertas_nuevas.iterrows()]

    errores_noticias = []
    if filas_noticias:
        print('\nEnviando noticias...')
        errores_noticias = enviar_filas(form_id_noticias, filas_noticias, api_token, username)

        indices_fallidos = {i for i, _, _ in errores_noticias}
        urls_enviadas_ok = {
            seleccion.iloc[i]['url'] for i in range(len(seleccion)) if i not in indices_fallidos
        }
        guardar_registro_envios(urls_ya_enviadas | urls_enviadas_ok, ruta_registro_envios)
    else:
        print('\nNo hay noticias nuevas por enviar en esta corrida.')

    if filas_metricas:
        print('\nEnviando métricas de alerta nuevas (snapshot de esta corrida, se acumula para el histórico)...')
        errores_metricas = enviar_filas(form_id_metricas, filas_metricas, api_token, username)

        indices_fallidos_metricas = {i for i, _, _ in errores_metricas}
        claves_enviadas_ok = {
            df_alertas_nuevas.iloc[i]['_clave_alerta'] for i in range(len(df_alertas_nuevas)) if i not in indices_fallidos_metricas
        }
        guardar_registro_alertas(claves_alerta_ya_enviadas | claves_enviadas_ok, ruta_registro_alertas)
    else:
        print('\nNo hay alertas nuevas por enviar en esta corrida.')
        errores_metricas = []

    if errores_noticias:
        print('\nErrores al enviar noticias:', errores_noticias[:3], '...' if len(errores_noticias) > 3 else '')
    if errores_metricas:
        print('\nErrores al enviar métricas:', errores_metricas[:3], '...' if len(errores_metricas) > 3 else '')

    return errores_noticias, errores_metricas


if __name__ == '__main__':
    if len(sys.argv) < 5:
        print('Uso: python -m kobo.subir_a_kobo <noticias_procesadas.xlsx> <alertas.xlsx> <api_token> <username_kobo> [minimo_noticias] [form_id_noticias] [form_id_metricas]')
        sys.exit(1)

    ruta_noticias = sys.argv[1]
    ruta_alertas_arg = sys.argv[2]
    token = sys.argv[3]
    username_arg = sys.argv[4]
    minimo = int(sys.argv[5]) if len(sys.argv) > 5 else 10
    form_id_noticias = sys.argv[6] if len(sys.argv) > 6 else FORM_ID_NOTICIAS
    form_id_metricas = sys.argv[7] if len(sys.argv) > 7 else FORM_ID_METRICAS

    pipeline_completo(
        ruta_noticias,
        ruta_alertas_arg,
        token,
        username_arg,
        minimo_noticias=minimo,
        form_id_noticias=form_id_noticias,
        form_id_metricas=form_id_metricas,
    )