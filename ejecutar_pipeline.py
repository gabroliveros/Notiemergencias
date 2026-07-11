# -*- coding: utf-8 -*-
"""
Ejecuta el pipeline completo de forma automática:
  scraper -> unir_partes -> limpieza_clasificacion -> metricas_alerta -> subir_a_kobo

Cada fase queda registrada en un log (consola + archivo en logs/), con
timestamp de inicio/fin y traceback completo si falla. Si una fase falla,
las siguientes NO se ejecutan (cada una depende del resultado de la anterior)
y el proceso termina con código de salida distinto de 0 — útil para que un
programador de tareas (cron / Task Scheduler) detecte el fallo.

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
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from procesamiento.unir_partes import pipeline_completo as unir_partes_pipeline
from procesamiento.limpieza_clasificacion import pipeline_completo as limpieza_pipeline
from procesamiento.metricas_alerta import pipeline_completo as metricas_pipeline
from kobo.subir_a_kobo import pipeline_completo as subir_kobo_pipeline


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

    return config


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
    y vuelca toda su salida al log, línea por línea."""
    script = config['rutas']['scraper_script']
    logger.info(f'Lanzando scraper como subproceso: {script}')

    resultado = subprocess.run([sys.executable, script], capture_output=True, text=True)

    for linea in resultado.stdout.splitlines():
        logger.info(f'[scraper] {linea}')
    for linea in resultado.stderr.splitlines():
        logger.warning(f'[scraper][stderr] {linea}')

    if resultado.returncode != 0:
        raise RuntimeError(f'El scraper terminó con código de salida {resultado.returncode}')


def main(ruta_config='env_prod.json'):
    config = cargar_config(ruta_config)
    logger, ruta_log = configurar_logging(config['rutas']['carpeta_logs'])
    logger.info(f'Iniciando pipeline completo. Log de esta corrida: {ruta_log}')

    rutas = config['rutas']
    parametros = config['parametros']
    kobo_cfg = config['kobo']

    try:
        ejecutar_fase(logger, 'scraper', ejecutar_scraper, logger, config)

        ejecutar_fase(
            logger, 'unir_partes',
            unir_partes_pipeline, rutas['carpeta_base'], rutas['noticias_crudas'],
        )

        ejecutar_fase(
            logger, 'limpieza_clasificacion',
            limpieza_pipeline, rutas['noticias_crudas'], rutas['noticias_procesadas'],
        )

        ejecutar_fase(
            logger, 'metricas_alerta',
            metricas_pipeline, rutas['noticias_procesadas'], rutas['alertas'],
            ventana_horas=parametros['ventana_horas_alerta'],
        )

        ejecutar_fase(
            logger, 'subir_a_kobo',
            subir_kobo_pipeline, rutas['noticias_procesadas'], rutas['alertas'],
            kobo_cfg['api_token'], minimo_noticias=parametros['minimo_noticias_a_subir'],
            ruta_registro_envios=rutas['registro_envios_kobo'],
        )

        logger.info('=== PIPELINE COMPLETO: TODAS LAS FASES OK ===')
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