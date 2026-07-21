# -*- coding: utf-8 -*-
"""
Escaneo sísmico nacional vía USGS Earthquake Catalog (FDSN Event API):
gratuita, pública, sin autenticación. Consulta todos los sismos dentro del
bounding box de Venezuela en la ventana configurada, y asigna cada uno al
estado más cercano (por distancia a la capital) usando las mismas
coordenadas de env_prod.json['precipitacion']['estados'].
"""

import math
from datetime import datetime, timedelta

import pandas as pd
import requests

from kobo.xlsform_builder import nombre_choice

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# Bounding box de Venezuela (con margen para no perder sismos costeros/fronterizos)
BBOX_VENEZUELA = {"minlatitude": 0.5, "maxlatitude": 13.0, "minlongitude": -73.5, "maxlongitude": -59.5}


def _distancia_km(lat1, lon1, lat2, lon2):
    """Distancia de haversine en km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _asignar_estado(lat, lon, capitales, radio_km_maximo):
    """Devuelve la clave del estado cuya capital está más cerca del epicentro,
    o None si el sismo más cercano queda fuera de radio_km_maximo (mar afuera,
    Caribe, o frontera con Colombia/Brasil/Guyana)."""
    mejor_estado, mejor_distancia = None, float("inf")
    for clave, info in capitales.items():
        d = _distancia_km(lat, lon, info["lat"], info["lon"])
        if d < mejor_distancia:
            mejor_estado, mejor_distancia = clave, d
    if mejor_distancia > radio_km_maximo:
        return None
    return mejor_estado


def consultar_sismos(ventana_dias, minmagnitude):
    fecha_fin = datetime.utcnow()
    fecha_inicio = fecha_fin - timedelta(days=ventana_dias)

    params = {
        "format": "geojson",
        "starttime": fecha_inicio.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": fecha_fin.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": minmagnitude,
        "orderby": "time",
        **BBOX_VENEZUELA,
    }
    response = requests.get(USGS_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    filas = []
    for feature in data.get("features", []):
        props = feature["properties"]
        lon, lat, prof = feature["geometry"]["coordinates"]
        filas.append({
            "id_evento": feature["id"],
            "fecha_evento": pd.to_datetime(props["time"], unit="ms", utc=True),
            "magnitud": props.get("mag"),
            "profundidad_km": prof,
            "lugar": props.get("place", ""),
            "lat": lat,
            "lon": lon,
            "url_detalle": props.get("url", ""),
        })
    return pd.DataFrame(filas)


def calcular_nivel_alerta(magnitud_maxima, umbrales_estado):
    if magnitud_maxima >= umbrales_estado["umbral_rojo"]:
        return "ROJO"
    if magnitud_maxima >= umbrales_estado["umbral_naranja"]:
        return "NARANJA"
    if magnitud_maxima >= umbrales_estado["umbral_amarillo"]:
        return "AMARILLO"
    return "VERDE"


def escanear_sismos_nacional(ventana_dias, minmagnitude, radio_km_maximo, capitales, umbrales_por_estado):
    """Devuelve (df_eventos, df_metricas):
    - df_eventos: un registro por sismo individual (para el detalle/mapa de puntos).
    - df_metricas: una fila por estado con magnitud máxima, número de sismos,
      profundidad promedio y nivel de alerta (snapshot de esta corrida)."""
    print("\nConsultando catálogo sísmico de USGS...")
    df_sismos = consultar_sismos(ventana_dias, minmagnitude)

    if df_sismos.empty:
        print("Sin sismos registrados en la ventana/umbral configurados.")
        return df_sismos, pd.DataFrame()

    df_sismos["estado"] = df_sismos.apply(
        lambda fila: _asignar_estado(fila["lat"], fila["lon"], capitales, radio_km_maximo), axis=1
    )
    sin_estado = df_sismos["estado"].isna().sum()
    if sin_estado:
        print(f"{sin_estado} sismos fuera del radio de asignación a un estado (mar/frontera) — se excluyen de métricas por estado.")

    df_asignados = df_sismos[df_sismos["estado"].notna()].copy()

    filas_metricas = []
    for estado, grupo in df_asignados.groupby("estado"):
        umbrales_estado = umbrales_por_estado.get(estado, umbrales_por_estado["_default"])
        magnitud_maxima = grupo["magnitud"].max()
        filas_metricas.append({
            "fecha_calculo": datetime.now(),
            "estado": nombre_choice(estado),
            "ventana_dias": ventana_dias,
            "n_sismos": len(grupo),
            "magnitud_maxima": round(magnitud_maxima, 2),
            "magnitud_promedio": round(grupo["magnitud"].mean(), 2),
            "profundidad_promedio_km": round(grupo["profundidad_km"].mean(), 2),
            "nivel_alerta": calcular_nivel_alerta(magnitud_maxima, umbrales_estado).lower(),
        })

    df_metricas = pd.DataFrame(filas_metricas)
    return df_sismos, df_metricas


if __name__ == "__main__":
    import json

    with open("env_prod.json", encoding="utf-8") as f:
        _cfg = json.load(f)

    df_eventos, df_metricas = escanear_sismos_nacional(
        ventana_dias=_cfg["sismos"]["ventana_dias"],
        minmagnitude=_cfg["sismos"]["minmagnitude"],
        radio_km_maximo=_cfg["sismos"]["radio_km_maximo"],
        capitales=_cfg["precipitacion"]["estados"],
        umbrales_por_estado=_cfg["sismos"]["umbrales"],
    )
    df_eventos.to_excel("descargas/sismos_eventos.xlsx", index=False)
    df_metricas.to_excel("descargas/sismos_metricas.xlsx", index=False)
    print("Archivos generados en descargas/")