import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from kobo.xlsform_builder import nombre_choice

# =====================================================================
# 1. BASE DE DATOS DE COORDENADAS Y UMBRALES PERSONALIZADOS
# =====================================================================
# Calibramos umbrales por región (las zonas áridas o andinas toleran menos agua que las selváticas)
CAPITALES_VE = {
    "1":  {"estado": "Amazonas", "capital": "Puerto Ayacucho", "lat": 5.6639, "lon": -67.6236, "u_amarillo": 200, "u_naranja": 350, "u_rojo": 500},
    "2":  {"estado": "Anzoátegui", "capital": "Barcelona", "lat": 10.1362, "lon": -64.6862, "u_amarillo": 100, "u_naranja": 180, "u_rojo": 280},
    "3":  {"estado": "Apure", "capital": "San Fernando de Apure", "lat": 7.8878, "lon": -67.4724, "u_amarillo": 150, "u_naranja": 250, "u_rojo": 380},
    "4":  {"estado": "Aragua", "capital": "Maracay", "lat": 10.2469, "lon": -67.5958, "u_amarillo": 120, "u_naranja": 220, "u_rojo": 350},
    "5":  {"estado": "Barinas", "capital": "Barinas", "lat": 8.6333, "lon": -70.2167, "u_amarillo": 150, "u_naranja": 250, "u_rojo": 380},
    "6":  {"estado": "Bolívar", "capital": "Ciudad Bolívar", "lat": 8.1029, "lon": -63.5470, "u_amarillo": 150, "u_naranja": 250, "u_rojo": 380},
    "7":  {"estado": "Carabobo", "capital": "Valencia", "lat": 10.1667, "lon": -68.0000, "u_amarillo": 120, "u_naranja": 220, "u_rojo": 350},
    "8":  {"estado": "Cojedes", "capital": "San Carlos", "lat": 9.6612, "lon": -68.5827, "u_amarillo": 120, "u_naranja": 220, "u_rojo": 350},
    "9":  {"estado": "Delta Amacuro", "capital": "Tucupita", "lat": 9.0603, "lon": -62.0510, "u_amarillo": 180, "u_naranja": 300, "u_rojo": 450},
    "10": {"estado": "Distrito Capital", "capital": "Caracas", "lat": 10.5061, "lon": -66.9144, "u_amarillo": 120, "u_naranja": 220, "u_rojo": 350},
    "11": {"estado": "Falcón", "capital": "Coro", "lat": 11.3950, "lon": -69.6816, "u_amarillo": 60, "u_naranja": 110, "u_rojo": 180},
    "12": {"estado": "Guárico", "capital": "San Juan de los Morros", "lat": 9.9115, "lon": -67.3537, "u_amarillo": 110, "u_naranja": 200, "u_rojo": 300},
    "13": {"estado": "Lara", "capital": "Barquisimeto", "lat": 10.0678, "lon": -69.3467, "u_amarillo": 80, "u_naranja": 140, "u_rojo": 220},
    "14": {"estado": "Mérida", "capital": "Mérida", "lat": 8.5833, "lon": -71.1333, "u_amarillo": 130, "u_naranja": 230, "u_rojo": 360},
    "15": {"estado": "Miranda", "capital": "Los Teques", "lat": 10.3411, "lon": -67.0406, "u_amarillo": 120, "u_naranja": 220, "u_rojo": 350},
    "16": {"estado": "Monagas", "capital": "Maturín", "lat": 9.7423, "lon": -63.1889, "u_amarillo": 130, "u_naranja": 220, "u_rojo": 340},
    "17": {"estado": "Nueva Esparta", "capital": "La Asunción", "lat": 11.0333, "lon": -63.8628, "u_amarillo": 70, "u_naranja": 120, "u_rojo": 200},
    "18": {"estado": "Portuguesa", "capital": "Guanare", "lat": 9.0436, "lon": -69.7489, "u_amarillo": 130, "u_naranja": 230, "u_rojo": 360},
    "19": {"estado": "Sucre", "capital": "Cumaná", "lat": 10.4500, "lon": -64.1667, "u_amarillo": 90, "u_naranja": 160, "u_rojo": 250},
    "20": {"estado": "Táchira", "capital": "San Cristóbal", "lat": 7.7682, "lon": -72.2322, "u_amarillo": 130, "u_naranja": 230, "u_rojo": 360},
    "21": {"estado": "Trujillo", "capital": "Trujillo", "lat": 9.3701, "lon": -70.4347, "u_amarillo": 120, "u_naranja": 210, "u_rojo": 320},
    "22": {"estado": "La Guaira", "capital": "La Guaira", "lat": 10.6000, "lon": -66.9331, "u_amarillo": 100, "u_naranja": 180, "u_rojo": 300},
    "23": {"estado": "Yaracuy", "capital": "San Felipe", "lat": 10.3353, "lon": -68.7458, "u_amarillo": 120, "u_naranja": 220, "u_rojo": 350},
    "24": {"estado": "Zulia", "capital": "Maracaibo", "lat": 10.6333, "lon": -71.6333, "u_amarillo": 80, "u_naranja": 140, "u_rojo": 220}
}

# Fechas de análisis (últimos 30 días)
fecha_fin = datetime.now().date()
fecha_inicio = fecha_fin - timedelta(days=30)

# =====================================================================
# 2. FUNCIONES DE PROCESAMIENTO
# =====================================================================
def consultar_acumulado_ciudad(id_ciudad, info):
    """Realiza la petición HTTP y calcula el acumulado y nivel de riesgo."""
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={info['lat']}&longitude={info['lon']}&start_date={fecha_inicio}&end_date={fecha_fin}&daily=precipitation_sum&timezone=auto"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            lluvias = data['daily']['precipitation_sum']
            acumulado = sum(lluvias) if lluvias else 0.0
            
            # Clasificación de riesgo y prioridad numérica para ordenar de mayor a menor riesgo
            if acumulado >= info['u_rojo']:
                alerta, color, prioridad = "ROJO", "red", 4
            elif acumulado >= info['u_naranja']:
                alerta, color, prioridad = "NARANJA", "orange", 3
            elif acumulado >= info['u_amarillo']:
                alerta, color, prioridad = "AMARILLO", "gold", 2
            else:
                alerta, color, prioridad = "VERDE", "green", 1
                
            # Porcentaje de saturación respecto al nivel de desastre (rojo)
            porcentaje_saturacion = round((acumulado / info['u_rojo']) * 100, 2)
            
            return {
                "id": id_ciudad,
                "estado": info['estado'],
                "capital": info['capital'],
                "acumulado": acumulado,
                "alerta": alerta,
                "color": color,
                "prioridad": prioridad,
                "saturacion": porcentaje_saturacion,
                "df_historico": pd.DataFrame({
                    'Fecha': pd.to_datetime(data['daily']['time']),
                    'Lluvia_Diaria_mm': lluvias
                }) if 'time' in data['daily'] else None
            }
    except Exception:
        pass
    return None

def escanear_riesgo_nacional():
    """Escanea concurrentemente las 24 capitales del país."""
    print("\nIniciando escaneo nacional de seguridad hídrica...")
    resultados = []
    
    # Ejecución paralela usando hilos para máxima velocidad
    with ThreadPoolExecutor(max_workers=12) as executor:
        futuros = [executor.submit(consultar_acumulado_ciudad, idx, info) for idx, info in CAPITALES_VE.items()]
        for f in futuros:
            res = f.result()
            if res:
                resultados.append(res)
                
    # Convertir a DataFrame y ordenar:
    # 1º Por prioridad de Alerta (Rojo > Naranja > Amarillo > Verde)
    # 2º Por porcentaje de saturación del suelo para desempatar
    df_riesgos = pd.DataFrame(resultados)
    df_riesgos = df_riesgos.sort_values(by=["prioridad", "saturacion"], ascending=[False, False])
    # Filtrar solo aquellas que superan el nivel seguro (Verde)
    en_riesgo = df_riesgos[df_riesgos['prioridad'] > 1]

    # Filtrar solo aquellas que superan el nivel seguro (Verde)
    en_riesgo = df_riesgos[df_riesgos['prioridad'] > 1]
    
    # print("\n" + "="*70)
    # print("      REPORTE NACIONAL DE RIESGO HIDROLÓGICO (MAYOR A MENOR PELIGRO)      ")
    # print("="*70)
    
    if en_riesgo.empty:
        print("  🟢 EXCELENTES NOTICIAS: No se detectan capitales en niveles de riesgo.")
        print("  Todas las zonas monitoreadas se encuentran en Alerta Verde.")
    else:
        for _, row in en_riesgo.iterrows():
            simbolo = "🔴" if row['alerta'] == "ROJO" else "🟠" if row['alerta'] == "NARANJA" else "🟡"
            print(f" {simbolo} Alerta {row['alerta']}: {row['capital']} (Edo. {row['estado']})")
            print(f"    - Lluvia acum. 30 días: {row['acumulado']:.1f} mm")
            print(f"    - Saturación de Suelos: {row['saturacion']:.1f}% de su capacidad crítica")
            print("-" * 60)
            
    # Resumen general al final
    total_rojo = len(df_riesgos[df_riesgos['alerta'] == "ROJO"])
    total_naranja = len(df_riesgos[df_riesgos['alerta'] == "NARANJA"])
    total_amarillo = len(df_riesgos[df_riesgos['alerta'] == "AMARILLO"])
    print(f"\nResumen de alertas activas a nivel nacional:")
    print(f" - Alertas Rojas: {total_rojo} | Alertas Naranjas: {total_naranja} | Alertas Amarillas: {total_amarillo}")

    df_kobo = df_riesgos.copy()
    df_kobo["fecha_calculo"] = datetime.now()
    df_kobo["umbral_amarillo"] = df_kobo["id"].map(lambda x: CAPITALES_VE[str(x)]["u_amarillo"])
    df_kobo["umbral_naranja"] = df_kobo["id"].map(lambda x: CAPITALES_VE[str(x)]["u_naranja"])
    df_kobo["umbral_rojo"] = df_kobo["id"].map(lambda x: CAPITALES_VE[str(x)]["u_rojo"])
    df_kobo = df_kobo.rename(columns={"acumulado": "precipitacion_30dias", "alerta": "nivel_alerta",})
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

# =====================================================================
# 3. MENÚ PRINCIPAL DEL SISTEMA
# =====================================================================
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
    # menu()
    df = escanear_riesgo_nacional()
    df.to_excel("descargas/precipitacion_nacional.xlsx", index=False)
    print("\nArchivo generado: descargas/precipitacion_nacional.xlsx")