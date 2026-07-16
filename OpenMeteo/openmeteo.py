import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from kobo.xlsform_builder import nombre_choice



# 1. FUNCIONES DE PROCESAMIENTO

def consultar_acumulado_ciudad(estado_clave, info, fecha_inicio, fecha_fin):
    """Realiza la petición HTTP y calcula el acumulado y nivel de riesgo."""

    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={info['lat']}&longitude={info['lon']}&start_date={fecha_inicio}&end_date={fecha_fin}&daily=precipitation_sum&timezone=auto"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            lluvias = data['daily']['precipitation_sum']
            acumulado = sum(lluvias) if lluvias else 0.0

            if acumulado >= info['umbral_rojo']:
                alerta, color, prioridad = "ROJO", "red", 4
            elif acumulado >= info['umbral_naranja']:
                alerta, color, prioridad = "NARANJA", "orange", 3
            elif acumulado >= info['umbral_amarillo']:
                alerta, color, prioridad = "AMARILLO", "gold", 2
            else:
                alerta, color, prioridad = "VERDE", "green", 1

            porcentaje_saturacion = (acumulado / info['umbral_rojo']) * 100

            return {
                "estado": estado_clave,
                "capital": info['capital'],
                "acumulado": acumulado,
                "alerta": alerta,
                "color": color,
                "prioridad": prioridad,
                "saturacion": porcentaje_saturacion,
                "umbral_amarillo": info['umbral_amarillo'],
                "umbral_naranja": info['umbral_naranja'],
                "umbral_rojo": info['umbral_rojo'],
                "df_historico": pd.DataFrame({
                    'Fecha': pd.to_datetime(data['daily']['time']),
                    'Lluvia_Diaria_mm': lluvias
                }) if 'time' in data['daily'] else None
            }
    except Exception:
        pass
    return None


def escanear_riesgo_nacional(ventana_dias=30, estados=None):
    """Escanea concurrentemente las capitales configuradas en
    env_prod.json['precipitacion']['estados']."""
    if estados is None:
        raise ValueError(
            "Falta 'estados' (ver la sección 'precipitacion.estados' de env_prod.json)."
        )

    fecha_fin = datetime.now().date()
    fecha_inicio = fecha_fin - timedelta(days=ventana_dias)

    print("\nIniciando escaneo nacional de seguridad hídrica...")
    resultados = []

    with ThreadPoolExecutor(max_workers=12) as executor:
        futuros = [
            executor.submit(consultar_acumulado_ciudad, estado_clave, info, fecha_inicio, fecha_fin)
            for estado_clave, info in estados.items()
        ]
        for f in futuros:
            res = f.result()
            if res:
                resultados.append(res)

    df_riesgos = pd.DataFrame(resultados)
    df_riesgos = df_riesgos.sort_values(by=["prioridad", "saturacion"], ascending=[False, False])

    en_riesgo = df_riesgos[df_riesgos['prioridad'] > 1]

    print("\n" + "="*70)
    print("      REPORTE NACIONAL DE RIESGO HIDROLÓGICO (MAYOR A MENOR PELIGRO)      ")
    print("="*70)

    if en_riesgo.empty:
        print("  🟢 EXCELENTES NOTICIAS: No se detectan capitales en niveles de riesgo.")
        print("  Todas las zonas monitoreadas se encuentran en Alerta Verde.")
    else:
        for _, row in en_riesgo.iterrows():
            simbolo = "🔴" if row['alerta'] == "ROJO" else "🟠" if row['alerta'] == "NARANJA" else "🟡"
            print(f" {simbolo} Alerta {row['alerta']}: {row['capital']} (Edo. {row['estado']})")
            print(f"    - Lluvia acum. {ventana_dias} días: {row['acumulado']:.1f} mm")
            print(f"    - Saturación de Suelos: {row['saturacion']:.1f}% de su capacidad crítica")
            print("-" * 70)

    total_rojo = len(df_riesgos[df_riesgos['alerta'] == "ROJO"])
    total_naranja = len(df_riesgos[df_riesgos['alerta'] == "NARANJA"])
    total_amarillo = len(df_riesgos[df_riesgos['alerta'] == "AMARILLO"])
    print(f"\nResumen de alertas activas a nivel nacional:")
    print(f" - Alertas Rojas: {total_rojo} | Alertas Naranjas: {total_naranja} | Alertas Amarillas: {total_amarillo}")
    print("="*70 + "\n")

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
    )
    df.to_excel("descargas/precipitacion_nacional.xlsx", index=False)
    print("\nArchivo generado: descargas/precipitacion_nacional.xlsx")