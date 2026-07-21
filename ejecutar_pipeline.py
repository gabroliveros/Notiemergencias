#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ejecuta el pipeline completo de forma automática:
  scraper -> unir_partes -> limpieza_clasificacion -> metricas_alerta -> subir_a_kobo

Cada fase queda registrada en un log (consola + archivo en descargas/logs/), con
timestamp de inicio/fin y traceback completo si falla. Si una fase falla,
las siguientes NO se ejecutan (cada una depende del resultado de la anterior)
y el proceso termina con código de salida distinto de 0 — útil para que un
programador de tareas (cron / Task Scheduler) detecte el fallo.

Carpeta de trabajo (`rutas.carpeta_descargas`, por defecto "descargas"):
todos los CSV/xlsx/logs de una corrida viven ahí, para no ensuciar la raíz
del proyecto. Al empezar, esa carpeta se limpia por completo — EXCEPTO si la
corrida anterior fue de la misma 'situacion', el mismo día, y hace menos de
`rutas.horas_reutilizar_descargas` horas (así una corrida que se corta a la
mitad no pierde lo ya descargado si la vuelves a lanzar poco después).

El registro de noticias ya enviadas a Kobo (`rutas.registro_envios_kobo`)
vive FUERA de descargas/, a propósito: es memoria de largo plazo entre
corridas para evitar reenvíos, no un archivo temporal de la corrida actual.

IMPORTANTE: el despliegue/reemplazo de los formularios de Kobo
(kobo.gestionar_formularios.upload_koboform) NO forma parte de este pipeline
automático a propósito — esa función borra las respuestas existentes cuando
se le pasa un asset_uid. Se corre aparte, manualmente, solo cuando cambias
la estructura del XLSForm.

Uso:
    python ejecutar_pipeline.py [ruta_a_env_prod.json]
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from procesamiento.unir_partes import pipeline_completo as unir_partes_pipeline
from procesamiento.limpieza_clasificacion import pipeline_completo as limpieza_pipeline
from procesamiento.metricas_alerta import pipeline_completo as metricas_pipeline
from kobo.subir_a_kobo import pipeline_completo as subir_kobo_pipeline, pipeline_precipitacion as subir_precipitacion_pipeline, pipeline_sismos as subir_sismos_pipeline
from kobo.gestionar_formularios import asegurar_formulario_desplegado
from OpenMeteo.openmeteo import escanear_riesgo_nacional
from USGS.sismos import escanear_sismos_nacional


tiempo_inicio = time.time()

NOMBRE_MARCADOR_CORRIDA = '.ultima_corrida.json'


class FaseFallidaError(Exception):
    """Se lanza cuando una fase del pipeline falla, para detener las siguientes."""


def cargar_config(ruta='env_prod.json'):
    if not Path(ruta).exists():
        raise FileNotFoundError(
            f"No se encontró '{ruta}'. Copia env_prod.json y completa 'api_token' con tu token real de Kobo."
        )
    with open(ruta, encoding='utf-8') as f:
        config = json.load(f)

    if config['kobo']['api_token'] in ('PON_AQUI_TU_API_TOKEN', '', None):
        raise ValueError(f"Falta configurar 'api_token' en {ruta} (todavía tiene el valor de plantilla).")

    if config['kobo'].get('username') in ('PON_AQUI_TU_USUARIO_KOBO', '', None):
        raise ValueError(f"Falta configurar 'kobo.username' en {ruta} (tu usuario de Kobo, el mismo de tu URL de bulk-submission-form).")

    return config


def preparar_carpeta_descargas(config):
    """
    Prepara la carpeta de trabajo de esta corrida. La limpia por completo,
    salvo que la corrida anterior haya sido de la misma 'situacion', el
    mismo día, y hace menos de 'horas_reutilizar_descargas' horas — en ese
    caso se conserva tal cual (para no perder progreso de una corrida
    reciente cortada a la mitad).

    Se ejecuta ANTES de configurar el logging (así el log de esta corrida,
    que también vive dentro de esta carpeta, no se borra a sí mismo).
    """
    carpeta = config['rutas']['carpeta_descargas']
    situacion = config['scraper']['situacion']
    horas_reutilizar = config['rutas'].get('horas_reutilizar_descargas', 5)

    os.makedirs(carpeta, exist_ok=True)
    ruta_marcador = os.path.join(carpeta, NOMBRE_MARCADOR_CORRIDA)

    reutilizar = False
    if os.path.exists(ruta_marcador):
        try:
            with open(ruta_marcador, encoding='utf-8') as f:
                marca = json.load(f)
            timestamp_anterior = datetime.fromisoformat(marca['timestamp'])
            horas_transcurridas = (datetime.now() - timestamp_anterior).total_seconds() / 3600
            mismo_dia = marca.get('fecha') == datetime.now().strftime('%Y-%m-%d')
            misma_situacion = marca.get('situacion') == situacion

            if mismo_dia and misma_situacion and horas_transcurridas < horas_reutilizar:
                reutilizar = True
                print(f"[{carpeta}] Se reutiliza: misma situación ('{situacion}'), mismo día, "
                      f'última corrida hace {horas_transcurridas:.1f}h (< {horas_reutilizar}h).')
        except Exception as e:
            print(f'[{carpeta}] Marcador de corrida ilegible ({e}) — se limpia la carpeta por seguridad.')

    if not reutilizar:
        print(f"[{carpeta}] Limpiando (corrida nueva, distinta situación/día, o pasaron más de {horas_reutilizar}h).")
        for nombre in os.listdir(carpeta):
            ruta_item = os.path.join(carpeta, nombre)
            try:
                if os.path.isdir(ruta_item):
                    shutil.rmtree(ruta_item)
                else:
                    os.remove(ruta_item)
            except Exception as e:
                print(f'[{carpeta}] No se pudo borrar {ruta_item}: {e}')

    with open(ruta_marcador, 'w', encoding='utf-8') as f:
        json.dump(
            {'situacion': situacion, 'fecha': datetime.now().strftime('%Y-%m-%d'), 'timestamp': datetime.now().isoformat()},
            f,
        )

    return carpeta, reutilizar


def configurar_logging(carpeta_logs):
    Path(carpeta_logs).mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime('%Y%m%d_%H%M%S')
    ruta_log = Path(carpeta_logs) / f'pipeline_{marca}.log'

    logger = logging.getLogger('pipeline_alertas')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # evita handlers duplicados si main() se llama más de una vez

    formato = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    handler_archivo = logging.FileHandler(ruta_log, encoding='utf-8')
    handler_archivo.setFormatter(formato)
    logger.addHandler(handler_archivo)

    handler_consola = logging.StreamHandler(sys.stdout)
    handler_consola.setFormatter(formato)
    logger.addHandler(handler_consola)

    return logger, ruta_log


def ejecutar_fase(logger, nombre_fase, funcion, *args, **kwargs):
    """Envuelve una fase con logging de inicio/fin/duración y captura
    cualquier excepción con traceback completo antes de relanzarla como
    FaseFallidaError (para que main() sepa dónde detenerse)."""
    logger.info(f'=== INICIO fase: {nombre_fase} ===')
    inicio = time.time()
    try:
        resultado = funcion(*args, **kwargs)
    except Exception:
        duracion = time.time() - inicio
        logger.error(f'=== FALLO fase: {nombre_fase} (tras {duracion:.1f}s) ===')
        logger.exception(f'Traceback completo de la fase "{nombre_fase}":')
        raise FaseFallidaError(nombre_fase)

    duracion = time.time() - inicio
    logger.info(f'=== FIN fase: {nombre_fase} (OK, {duracion:.1f}s) ===')
    return resultado


def ejecutar_scraper(logger, config):
    """Corre el scraper como subproceso aparte (usa multiprocessing propio)
    y vuelca toda su salida al log, línea por línea.

    Se fuerza PYTHONIOENCODING=utf-8 en el entorno del subproceso: por
    defecto, cuando la salida de un proceso hijo en Windows se captura por
    un pipe (en vez de ir a una consola real), Python usa cp1252 en lugar
    de UTF-8 — y cp1252 no puede codificar los emojis que imprime el
    scraper (🔎, etc.), lo que lo hacía morir antes de escribir cualquier
    resultado."""
    script = config['rutas']['scraper_script']
    logger.info(f'Lanzando scraper como subproceso: {script}')

    entorno = os.environ.copy()
    entorno['PYTHONIOENCODING'] = 'utf-8'

    resultado = subprocess.run(
        [sys.executable, script],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        env=entorno,
    )

    for linea in resultado.stdout.splitlines():
        logger.info(f'[scraper] {linea}')
    for linea in resultado.stderr.splitlines():
        logger.warning(f'[scraper][stderr] {linea}')

    if resultado.returncode != 0:
        raise RuntimeError(f'El scraper terminó con código de salida {resultado.returncode}')


def _asegurar_ambos_formularios(logger, kobo_cfg):
    """Crea en Kobo los formularios que falten (solo la primera vez). Si ya
    existen, no los toca — nunca borra datos ya subidos."""
    for nombre_xlsform, form_id in [
        (kobo_cfg['form_id_noticias'], kobo_cfg['form_id_noticias']),
        (kobo_cfg['form_id_metricas'], kobo_cfg['form_id_metricas']),
        (kobo_cfg['form_id_precipitacion'], kobo_cfg['form_id_precipitacion']),
        (kobo_cfg['form_id_sismos'], kobo_cfg['form_id_sismos']),
    ]:
        creado, _ = asegurar_formulario_desplegado(
            nombre_xlsform, form_id, kobo_cfg['api_token'], server=kobo_cfg['server']
        )
        if creado:
            logger.info(f"Formulario '{form_id}' no existía — se creó y desplegó ahora.")
        else:
            logger.info(f"Formulario '{form_id}' ya existía — sin cambios, solo se subirán datos.")


def main(ruta_config='env_prod.json'):
    config = cargar_config(ruta_config)

    # Se prepara ANTES del logging: el log de esta corrida vive dentro de
    # esta misma carpeta, no queremos que la limpieza se lo lleve.
    carpeta, datos_recientes_disponibles = preparar_carpeta_descargas(config)

    logger, ruta_log = configurar_logging(os.path.join(carpeta, 'logs'))
    logger.info(f'Iniciando pipeline completo. Carpeta de trabajo: {carpeta} | Log: {ruta_log}')

    rutas = config['rutas']
    parametros = config['parametros']
    kobo_cfg = config['kobo']

    ruta_noticias_crudas = os.path.join(carpeta, rutas['noticias_crudas'])
    ruta_noticias_procesadas = os.path.join(carpeta, rutas['noticias_procesadas'])
    ruta_alertas = os.path.join(carpeta, rutas['alertas'])
    # Fuera de 'carpeta' a propósito — ver docstring del módulo.
    ruta_registro_envios = rutas['registro_envios_kobo']

    scraper_cfg = config['scraper']
    if scraper_cfg.get('usar_fechas', True):
        if scraper_cfg.get('fecha_desde') and scraper_cfg.get('fecha_hasta'):
            fecha_desde = scraper_cfg['fecha_desde']
            fecha_hasta = scraper_cfg['fecha_hasta']
        else:
            hoy = datetime.now()
            fecha_hasta = hoy.strftime('%Y-%m-%d')
            fecha_desde = (hoy - timedelta(days=scraper_cfg['ventana_dias'])).strftime('%Y-%m-%d')
    else:
        fecha_desde = fecha_hasta = None

    try:
        if datos_recientes_disponibles and Path(ruta_noticias_crudas).exists():
            logger.info(
                f"Se omite scraper y unir_partes: ya existen datos recientes de la misma situación/día en '{ruta_noticias_crudas}'."
            )
        else:
            ejecutar_fase(logger, 'scraper', ejecutar_scraper, logger, config)

            ejecutar_fase(
                logger, 'unir_partes',
                unir_partes_pipeline, carpeta, ruta_noticias_crudas, rutas['csv_base'] + '_part*.csv',
            )

        ejecutar_fase(
            logger, 'limpieza_clasificacion',
            limpieza_pipeline, ruta_noticias_crudas, ruta_noticias_procesadas,
            fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
        )
        
        ejecutar_fase(
            logger, 'metricas_alerta',
            metricas_pipeline, ruta_noticias_procesadas, ruta_alertas,
            ventana_horas=parametros['ventana_horas_alerta'], situacion=config['scraper']['situacion']
        )

        # No borra ni recrea nada si el formulario ya existe — solo lo crea
        # la primera vez que no lo encuentra en Kobo.
        ejecutar_fase(
            logger, 'verificar_formularios_kobo',
            _asegurar_ambos_formularios, logger, kobo_cfg,
        )

        ejecutar_fase(
            logger, 'subir_a_kobo',
            subir_kobo_pipeline, ruta_noticias_procesadas, ruta_alertas,
            kobo_cfg['api_token'], kobo_cfg['username'], 
            situacion=config['scraper']['situacion'],
            minimo_noticias=parametros['minimo_noticias_a_subir'],
            form_id_noticias=kobo_cfg['form_id_noticias'],
            form_id_metricas=kobo_cfg['form_id_metricas'],
            ruta_registro_envios=ruta_registro_envios,
        )

        # Escaner de Precipitaciones Acumuladas de OpenMeteo
        df_precipitacion = ejecutar_fase(
            logger, 'escanear_precipitacion', escanear_riesgo_nacional,
            ventana_dias=config['precipitacion']['ventana_dias'],
            estados=config['precipitacion']['estados'],
        )

        ejecutar_fase(
            logger, 'subir_precipitacion_kobo',
            subir_precipitacion_pipeline, df_precipitacion,
            kobo_cfg['api_token'], kobo_cfg['username'],
            form_id_precipitacion=kobo_cfg['form_id_precipitacion'],
        )

        df_eventos_sismos, df_metricas_sismos = ejecutar_fase(
            logger, 'escanear_sismos', escanear_sismos_nacional,
            ventana_dias=config['sismos']['ventana_dias'],
            minmagnitude=config['sismos']['minmagnitude'],
            radio_km_maximo=config['sismos']['radio_km_maximo'],
            capitales=config['precipitacion']['estados'],
            umbrales_por_estado=config['sismos']['umbrales'],
        )

        ejecutar_fase(
            logger, 'subir_sismos_kobo',
            subir_sismos_pipeline, df_metricas_sismos,
            kobo_cfg['api_token'], kobo_cfg['username'],
            form_id_sismos=kobo_cfg['form_id_sismos'],
        )

        logger.info('=== PIPELINE COMPLETO: TODAS LAS FASES OK ===')

        tiempo_fin = time.time()
        tiempo_total = tiempo_fin - tiempo_inicio # Tiempo total en segundos
        
        # Formatear el tiempo en minutos y segundos
        minutos = int(tiempo_total // 60)
        segundos = int(tiempo_total % 60)
        print(f"⏱️  Tiempo total de ejecución: {minutos} min {segundos} seg")

        return 0

    except FaseFallidaError as e:
        logger.error(f'Pipeline detenido: la fase "{e}" falló. Revisa el traceback de esa fase más arriba en este mismo log.')
        return 1
    except Exception:
        logger.exception('Error inesperado fuera de una fase controlada:')
        return 1


if __name__ == '__main__':
    ruta_config_arg = sys.argv[1] if len(sys.argv) > 1 else 'env_prod.json'
    sys.exit(main(ruta_config_arg))