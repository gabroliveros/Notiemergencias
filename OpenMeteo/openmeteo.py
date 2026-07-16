#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests, time
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from kobo.xlsform_builder import nombre_choice



# 1. FUNCIONES DE PROCESAMIENTO

def consultar_acumulado_ciudad(
    estado_clave,
    info,
    fecha_inicio,
    fecha_fin,
    anios_historicos=10,
    normal_minimo_mm=15,
    umbral_amarillo_pct=1.25,
    umbral_naranja_pct=1.70,
    umbral_rojo_pct=2.20,
):
    """Calcula el riesgo relativo de una capital comparando la lluvia
    acumulada actual contra su 'normal histórico':

        riesgo_relativo = acumulado_ventana / normal_historico_ventana

    normal_historico_ventana = mediana de la lluvia acumulada en la MISMA
    ventana de fechas (mismo día/mes) de cada uno de los `anios_historicos`
    años anteriores. Se usa mediana en vez de promedio para que un evento
    extremo puntual en el histórico no distorsione el "normal".

    `normal_minimo_mm` evita ratios absurdos en temporada seca, cuando el
    normal histórico es casi 0mm (cualquier lluvia daría un % gigante).

    Se hace UN solo request cubriendo todo el rango (hoy - anios_historicos
    años, hasta hoy) y las ventanas se recortan localmente con pandas, en
    vez de un request por año.
    """
    fecha_inicio_ts = pd.Timestamp(fecha_inicio)
    fecha_fin_ts = pd.Timestamp(fecha_fin)
    rango_inicio = (fecha_inicio_ts - pd.DateOffset(years=anios_historicos)).date()

    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={info['lat']}&longitude={info['lon']}"
        f"&start_date={rango_inicio}&end_date={fecha_fin}"
        f"&daily=precipitation_sum&timezone=auto"
    )

    max_reintentos = 4
    backoff_factor = 2  # Segundos a esperar multiplicados en cada fallo (2s, 4s, 8s...)
    response = None

    for intento in range(max_reintentos):
        try:
            if intento == 0:
                time.sleep(hash(estado_clave) % 10 / 10.0) 

            response = requests.get(url, timeout=25)
            
            if response.status_code == 200:
                break
                
            elif response.status_code == 429:
                espera = backoff_factor ** (intento + 1)
                # print(f"⚠️ [Rate Limit] {estado_clave.upper()} devolvió 429. Reintentando en {espera}s... (Intento {intento+1}/{max_reintentos})")
                time.sleep(espera)
            else:
                espera = backoff_factor ** (intento + 1)
                print(f"⚠️ [Error HTTP {response.status_code}] en {estado_clave.upper()}. Reintentando en {espera}s...")
                time.sleep(espera)

        except (requests.exceptions.RequestException, Exception) as e:
            espera = backoff_factor ** (intento + 1)
            print(f"❌ [Fallo de Red] en {estado_clave.upper()}: {str(e)}. Reintentando en {espera}s... (Intento {intento+1}/{max_reintentos})")
            time.sleep(espera)
    
    if response is None or response.status_code != 200:
        print(f"🚨 [ERROR DEFINITIVO] No se pudieron recuperar los datos de precipitación para {estado_clave.upper()} tras {max_reintentos} intentos.")
        return None

    try:
        data = response.json()
        if 'time' not in data.get('daily', {}):
            return None

        lluvias = [v if v is not None else 0.0 for v in data['daily']['precipitation_sum']]
        df = pd.DataFrame({
            'Fecha': pd.to_datetime(data['daily']['time']),
            'Lluvia_Diaria_mm': lluvias,
        }).set_index('Fecha')

        # Acumulado de la ventana actual (ej. últimos 30 días)
        ventana_actual = df.loc[fecha_inicio_ts:fecha_fin_ts, 'Lluvia_Diaria_mm']
        acumulado = float(ventana_actual.sum())

        # Acumulados de la MISMA ventana (mismo día/mes) en años anteriores
        normales = []
        for k in range(1, anios_historicos + 1):
            ini_hist = fecha_inicio_ts - pd.DateOffset(years=k)
            fin_hist = fecha_fin_ts - pd.DateOffset(years=k)
            ventana_hist = df.loc[ini_hist:fin_hist, 'Lluvia_Diaria_mm']
            if not ventana_hist.empty:
                normales.append(float(ventana_hist.sum()))

        if not normales:
            return None

        normal = round(float(pd.Series(normales).median()), 2)
        normal_efectivo = max(normal, normal_minimo_mm)
        riesgo_relativo = round(acumulado / normal_efectivo, 2)

        if riesgo_relativo >= umbral_rojo_pct:
            alerta, color, prioridad = "ROJO", "red", 4
        elif riesgo_relativo >= umbral_naranja_pct:
            alerta, color, prioridad = "NARANJA", "orange", 3
        elif riesgo_relativo >= umbral_amarillo_pct:
            alerta, color, prioridad = "AMARILLO", "gold", 2
        else:
            alerta, color, prioridad = "VERDE", "green", 1

        return {
            "estado": estado_clave,
            "capital": info['capital'],
            "acumulado": round(acumulado, 2),
            "normal_historico": round(normal, 2),
            "anios_historicos_usados": len(normales),
            "alerta": alerta,
            "color": color,
            "prioridad": prioridad,
            # "saturacion" ahora es el % del normal histórico (antes era % de un umbral fijo)
            "saturacion": round(riesgo_relativo * 100, 2),
            # se mantienen estas columnas (mismo esquema para Kobo) pero ahora
            # son umbrales en mm DERIVADOS del normal histórico de cada capital,
            # no valores fijos escritos a mano
            "umbral_amarillo": round(normal_efectivo * umbral_amarillo_pct,2),
            "umbral_naranja": round(normal_efectivo * umbral_naranja_pct, 2),
            "umbral_rojo": round(normal_efectivo * umbral_rojo_pct, 2),
            "df_historico": ventana_actual.reset_index() if not ventana_actual.empty else None,
        }
    except Exception:
        pass
    return None


def escanear_riesgo_nacional(
    ventana_dias=30,
    estados=None,
    anios_historicos=10,
    normal_minimo_mm=15,
    umbral_amarillo_pct=1.25,
    umbral_naranja_pct=1.70,
    umbral_rojo_pct=2.20,
):
    """Escanea concurrentemente las capitales configuradas en
    env_prod.json['precipitacion']['estados'].

    El riesgo ya no se mide contra un umbral fijo en mm por estado, sino
    contra el 'normal histórico' de cada capital (mediana de los últimos
    `anios_historicos` años en la misma ventana de fechas):

        riesgo_relativo = acumulado / normal_historico
        Amarillo > umbral_amarillo_pct | Naranja > umbral_naranja_pct | Rojo > umbral_rojo_pct
    """
    if estados is None:
        raise ValueError(
            "Falta 'estados' (ver la sección 'precipitacion.estados' de env_prod.json)."
        )

    fecha_fin = datetime.now().date()
    fecha_inicio = fecha_fin - timedelta(days=ventana_dias)

    print("\nIniciando escaneo nacional de seguridad hídrica (riesgo relativo al normal histórico)...")
    resultados = []

    with ThreadPoolExecutor(max_workers=12) as executor:
        futuros = [
            executor.submit(
                consultar_acumulado_ciudad,
                estado_clave,
                info,
                fecha_inicio,
                fecha_fin,
                anios_historicos,
                normal_minimo_mm,
                umbral_amarillo_pct,
                umbral_naranja_pct,
                umbral_rojo_pct,
            )
            for estado_clave, info in estados.items()
        ]
        for f in futuros:
            res = f.result()
            if res:
                resultados.append(res)

    df_riesgos = pd.DataFrame(resultados)
    df_riesgos = df_riesgos.sort_values(by=["prioridad", "saturacion"], ascending=[False, False])

    en_riesgo = df_riesgos[df_riesgos['prioridad'] > 1]

    print("      REPORTE NACIONAL DE RIESGO HIDROLÓGICO (MAYOR A MENOR PELIGRO)      ")
    print("="*60)

    if en_riesgo.empty:
        print("  🟢 EXCELENTES NOTICIAS: No se detectan capitales en niveles de riesgo.")
        print("  Todas las zonas monitoreadas se encuentran en Alerta Verde.")
    else:
        for _, row in en_riesgo.iterrows():
            simbolo = "🔴" if row['alerta'] == "ROJO" else "🟠" if row['alerta'] == "NARANJA" else "🟡"
            print(f" {simbolo} Alerta {row['alerta']}: {row['capital']} (Edo. {row['estado']})")
            print(f"    - Lluvia acum. {ventana_dias} días: {row['acumulado']:.1f} mm  (normal histórico: {row['normal_historico']:.1f} mm, {row['anios_historicos_usados']} años)")
            print(f"    - Riesgo relativo: {row['saturacion']:.0f}% de su normal histórico")
            print("-" * 60)

    total_rojo = len(df_riesgos[df_riesgos['alerta'] == "ROJO"])
    total_naranja = len(df_riesgos[df_riesgos['alerta'] == "NARANJA"])
    total_amarillo = len(df_riesgos[df_riesgos['alerta'] == "AMARILLO"])
    print(f"\nResumen de alertas activas a nivel nacional:")
    print(f" - Alertas Rojas: {total_rojo} | Alertas Naranjas: {total_naranja} | Alertas Amarillas: {total_amarillo}")
    print("="*60 + "\n")

    df_kobo = df_riesgos.copy()
    df_kobo["fecha_calculo"] = datetime.now()
    df_kobo = df_kobo.rename(columns={"acumulado": "precipitacion_30dias", "alerta": "nivel_alerta"})
    df_kobo["estado"] = df_kobo["estado"].apply(nombre_choice)
    df_kobo["nivel_alerta"] = df_kobo["nivel_alerta"].str.lower()
    df_kobo = df_kobo[
        [
            "fecha_calculo",
            "estado",
            "capital",
            "precipitacion_30dias",
            "saturacion",
            "nivel_alerta",
            "umbral_amarillo",
            "umbral_naranja",
            "umbral_rojo",
        ]
    ]

    return df_kobo


# def mostrar_grafico_ciudad(res):
#     """Dibuja la gráfica histórica de acumulación mensual de una ciudad."""
#     df = res['df_historico']
#     df['Acumulado_mm'] = df['Lluvia_Diaria_mm'].cumsum()
#     info_geo = CAPITALES_VE[res['id']]
    
#     plt.figure(figsize=(10, 6))
#     plt.plot(df['Fecha'], df['Acumulado_mm'], label='Acumulado Registrado', color='blue', linewidth=2.5)
    
#     # Dibujar líneas de umbrales específicos de la ciudad elegida
#     plt.axhline(y=info_geo['u_rojo'], color='red', linestyle='--', label=f"Rojo (Deslaves/Inundación): {info_geo['u_rojo']}mm")
#     plt.axhline(y=info_geo['u_naranja'], color='orange', linestyle='--', label=f"Naranja (Riesgo Alto): {info_geo['u_naranja']}mm")
#     plt.axhline(y=info_geo['u_amarillo'], color='gold', linestyle='--', label=f"Amarillo (Prevención): {info_geo['u_amarillo']}mm")
    
#     plt.title(f"Análisis Hidrológico - {res['capital']}, Edo. {res['estado']}\nAlerta Actual: {res['alerta']}", fontsize=13, fontweight='bold', color=res['color'])
#     plt.xlabel("Línea de Tiempo (Últimos 30 días)", fontsize=11)
#     plt.ylabel("Milímetros Acumulados (mm)", fontsize=11)
#     plt.grid(True, linestyle=':', alpha=0.5)
#     plt.legend(loc='upper left')
#     plt.xticks(rotation=45)
#     plt.tight_layout()
#     plt.show()


# 2. MENÚ PRINCIPAL DEL SISTEMA

def menu():
    while True:
        print("=== SISTEMA INTEGRADO DE GESTIÓN DE RIESGOS METEOROLÓGICOS (VE) ===")
        # print("1. Escanear todo el país y ver zonas en riesgo (De Mayor a Menor)")
        # print("2. Analizar una capital de estado específica (Ver gráfico)")
        # print("3. Salir")
        
        # opcion = input("\nSelecciona una opción (1-3): ").strip()
        opcion = 1

        if opcion == "1":
            escanear_riesgo_nacional()
        # elif opcion == "2":
        #     print("\n--- SELECCIONA EL ESTADO A ANALIZAR ---")
        #     for idx, info in CAPITALES_VE.items():
        #         print(f"{idx.rjust(2)}. {info['estado']} ({info['capital']})")
            
        #     sel = input("\nIngresa el número (1-24): ").strip()
        #     if sel in CAPITALES_VE:
        #         res = consultar_acumulado_ciudad(sel, CAPITALES_VE[sel])
        #         if res:
        #             print("\n" + "="*50)
        #             print(f" Resultados para {res['capital']}:")
        #             print(f" - Precipitación acumulada: {res['acumulado']:.2f} mm")
        #             print(f" - Nivel de Alerta: [{res['alerta']}]")
        #             print(f" - Saturación de suelos: {res['saturacion']:.1f}%")
        #             print("="*50 + "\n")
        #             mostrar_grafico_ciudad(res)
        #         else:
        #             print("Error al recuperar los datos de la estación. Inténtalo de nuevo.")
        #     else:
        #         print("Opción inválida.")
        # elif opcion == "3":1
        #     print("Saliendo del sistema de prevención. ¡Mantente a salvo!")
        #     break
        # else:
        #     print("Opción no válida. Intenta de nuevo.\n")


if __name__ == "__main__":
    import json

    with open("env_prod.json", encoding="utf-8") as f:
        _cfg_precip = json.load(f)["precipitacion"]

    df = escanear_riesgo_nacional(
        ventana_dias=_cfg_precip["ventana_dias"],
        estados=_cfg_precip["estados"],
        anios_historicos=_cfg_precip.get("anios_historicos", 10),
        normal_minimo_mm=_cfg_precip.get("normal_minimo_mm", 15),
        umbral_amarillo_pct=_cfg_precip.get("umbral_amarillo_pct", 1.25),
        umbral_naranja_pct=_cfg_precip.get("umbral_naranja_pct", 1.70),
        umbral_rojo_pct=_cfg_precip.get("umbral_rojo_pct", 2.20),
    )
    df.to_excel("descargas/precipitacion_nacional.xlsx", index=False)
    print("\nArchivo generado: descargas/precipitacion_nacional.xlsx")