# Sistema de Monitoreo de Noticias y Alertas de Emergencia

Sistema automatizado que rastrea noticias de prensa sobre desastres o emergencias 
(lluvias/inundaciones, sismos, sequía, huracanes), las clasifica geográfica y temáticamente,
calcula niveles de alerta por estado, complementa esas alertas con datos hidrológicos
independientes de precipitación acumulada (Open-Meteo), y publica todo en KoboToolbox para
alimentar un tablero de Power BI.

Adaptado al contexto venezolano y escalable o ajustable a cualquier otro país.

```
Flujo principal (noticias):
    Scraper (DuckDuckGo) → Unir partes → Limpieza/clasificación → Métricas de alerta → KoboToolbox → Power BI

Flujo paralelo (hidrológico, independiente de las noticias):
    Open-Meteo (24 capitales) → Cálculo de nivel de riesgo → KoboToolbox → Power BI
```

## Tabla de contenido

- [Arquitectura](#arquitectura)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Instalación](#instalación)
- [Configuración (`env_prod.json`)](#configuración-env_prodjson)
- [Cómo correr el sistema](#cómo-correr-el-sistema)
- [Las etapas del pipeline, en detalle](#las-etapas-del-pipeline-en-detalle)
- [Reglas de nivel de alerta](#reglas-de-nivel-de-alerta)
- [KoboToolbox: formularios y datos](#kobotoolbox-formularios-y-datos)
- [Automatización (tareas programadas)](#automatización-tareas-programadas)
- [Limitaciones conocidas y pendientes](#limitaciones-conocidas-y-pendientes)
- [Hoja de ruta](#hoja-de-ruta)

## Arquitectura

1. **Scraper multi-navegador** (`buscador.py`): recorre
   DuckDuckGo con Selenium (varios navegadores en paralelo) cruzando *medio de
   comunicación × estado de Venezuela*, filtrando por palabras clave del tipo de evento
   configurado y por rango de fechas. Cada worker guarda su propio CSV.
2. **Unir partes** (`procesamiento/unir_partes.py`): compila todos los CSV de los
   workers en un único xlsx acumulado, deduplicando por URL (también contra corridas
   anteriores).
3. **Limpieza y clasificación** (`procesamiento/limpieza_clasificacion.py`): normaliza
   texto, filtra lo que no es de Venezuela, clasifica cada noticia por zona geográfica,
   nivel de afectación (víctimas/rescate/daños), medios de logística mencionados y tipo
   de evento; extrae lugares y actores/autoridades con NER (spaCy).
4. **Métricas y alerta** (`procesamiento/metricas_alerta.py`): agrupa por
   *estado × tipo de evento* dentro de una ventana de tiempo (48h por defecto) y calcula
   un nivel de alerta (Rojo/Naranja/Amarillo/Verde).
5. **Precipitación nacional** (`OpenMeteo/openmeteo.py`): consulta, en paralelo, la
   lluvia acumulada de los últimos 30 días en la capital de cada uno de los 24
   estados contra la API histórica de Open-Meteo, y calcula un nivel de alerta
   hidrológico por estado según umbrales propios de cada región. Es independiente del
   flujo de noticias — no depende del scraper ni de la clasificación.
6. **KoboToolbox** (`kobo/`): crea los tres formularios en Kobo la primera vez (si no
   existen) y sube las noticias relevantes, las métricas de alerta y el snapshot de
   precipitación nacional como respuestas, sin borrar nunca el histórico — cada corrida
   agrega datos nuevos, lo que arma una línea de tiempo por estado y tipo de evento.
7. **`ejecutar_pipeline.py`**: orquesta todas las etapas anteriores en orden, con
   logging detallado por fase (consola + archivo), deteniéndose y marcando claramente
   dónde falló si algo sale mal.

## Estructura del repositorio

```
.
├── buscador.py                                # Scraper (Selenium + DuckDuckGo)
├── ejecutar_pipeline.py                       # Orquestador de todo el pipeline
├── env_prod.json                              # Configuración (NO subir con token real)
├── env_prod.json.example                      # Plantilla segura para el repo
├── requirements.txt
├── .gitignore
│
├── xlsforms/
│   ├── noticias_emergencia_vzla.xlsx          # XLSForm — noticias relevantes
│   ├── metricas_alerta_vzla.xlsx              # XLSForm — métricas de alerta
│   └── precipitacion_nacional.xlsx            # XLSForm — precipitación acumulada por estado
│
├── procesamiento/
│   ├── __init__.py
│   ├── diccionarios.py                        # Palabras clave, geografía, blacklist NER
│   ├── unir_partes.py                         # Etapa 2
│   ├── limpieza_clasificacion.py              # Etapa 3
│   └── metricas_alerta.py                     # Etapa 4
│
├── OpenMeteo/
│   └── openmeteo.py                           # Etapa 5: escaneo hidrológico nacional
│
├── kobo/
│   ├── __init__.py
│   ├── xlsform_builder.py                     # Genera los 3 XLSForm desde los diccionarios
│   ├── gestionar_formularios.py               # Crear/desplegar formularios + enviar datos
│   └── subir_a_kobo.py                        # Etapa 6: selección + envío de datos
│
└── logs/                                      # Generado en tiempo de ejecución (ignorado en git)
```

## Instalación

Requiere Python 3.12 y Google Chrome instalado (el scraper usa `webdriver-manager` para
descargar el ChromeDriver correspondiente automáticamente).

```bash
pip install -r requirements.txt
```

`requirements.txt`:
```
pandas
openpyxl
unidecode
selenium
selenium-stealth
webdriver-manager
requests
matplotlib
```

## Configuración (`env_prod.json`)

Copia `env_prod.json.example` a `env_prod.json` y completa tu token de Kobo
(`https://kf.kobotoolbox.org/token/?format=json`, estando logueado) y tu usuario de Kobo
(el mismo que aparece en tu URL de `bulk-submission-form`).

```jsonc
{
  "kobo": {
    "server": "https://kf.kobotoolbox.org/",
    "api_token": "TU_TOKEN_AQUI",
    "username": "TU_USUARIO_KOBO",
    "form_id_noticias": "noticias_emergencia",
    "form_id_metricas": "metricas_alerta",
    "form_id_precipitacion": "precipitacion_nacional"
  },
  "rutas": {
    "_comentario_descargas": "Todos los CSV/xlsx/logs de una corrida viven aquí. Se limpia al empezar una corrida nueva, salvo que sea la misma situacion, el mismo dia, y la corrida anterior haya sido hace menos de 'horas_reutilizar_descargas'.",
    "horas_reutilizar_descargas": 5,
    "carpeta_descargas": "descargas",
    "scraper_script": "buscador.py",
    "csv_base": "ddg_noticias_OPEN",
    "noticias_crudas": "noticias_crudas.xlsx",
    "noticias_procesadas": "noticias_procesadas.xlsx",
    "alertas": "alertas_por_estado.xlsx",

    "_comentario_registro": "Este archivo NO vive en descargas/ a propósito: es memoria de largo plazo entre corridas (evita re-subir la misma noticia a Kobo días después). Si viviera dentro de descargas/, se borraría cada vez que la carpeta se limpia.",
    "registro_envios_kobo": "kobo/logs/noticias_enviadas_kobo.json",
    "registro_alertas_kobo": "kobo/logs/alertas_enviadas_kobo.json"
  },
  "parametros": {
    "ventana_horas_alerta": 72,
    "minimo_noticias_a_subir": 10
  },
  "scraper": {
    "_comentario_situacion": "Opciones válidas: lluvias, sismo, sequia, huracan. Evite usar más de un criterio de búsqueda",
    "_comentario_fechas": "Si fecha_desde/fecha_hasta son null, se calculan automáticamente como (hoy - ventana_dias) a hoy",

    "situacion": ["lluvias"],
    "num_workers": 4,
    "group_start_index": 0,
    "usar_fechas": true,
    "fecha_desde": null,
    "fecha_hasta": null,
    "ventana_dias": 2,
    "region": "ve",
    "site": "ve",
    "carpeta_base": "descargas",
}
```

**Parámetros clave que se pueden ajustar sin tocar código:**

| Parámetro | Qué hace |
|---|---|
| `kobo.form_id_precipitacion` | `id_string` del formulario de precipitación nacional en Kobo |
| `rutas.carpeta_descargas` | Carpeta de trabajo de cada corrida (CSV/xlsx/logs); se limpia al inicio salvo reutilización reciente |
| `rutas.horas_reutilizar_descargas` | Horas dentro de las cuales una corrida cortada a la mitad reutiliza lo ya descargado (misma situación, mismo día) |
| `rutas.registro_alertas_kobo` | Registro local de claves `estado\|tipo_evento\|día\|nivel` ya enviadas, para no repetir snapshots idénticos de métricas |
| `scraper.situacion` | Tipo de evento a rastrear: `lluvias`, `sismo`, `sequia` o `huracan` |
| `scraper.num_workers` | Cuántos navegadores en paralelo lanza el scraper |
| `scraper.fecha_desde` / `fecha_hasta` | Rango fijo de fechas (para pruebas). Si se dejan en `null`, se calcula automáticamente como *(hoy − `ventana_dias`)* a *hoy* |
| `scraper.ventana_dias` | Tamaño de la ventana automática de fechas cuando no hay fechas fijas |
| `scraper.medios` / `estados` | Listas de medios y estados a cruzar en el barrido |
| `parametros.ventana_horas_alerta` | Ventana de tiempo para calcular el nivel de alerta de noticias (48h por defecto) |
| `parametros.minimo_noticias_a_subir` | Mínimo de noticias a subir a Kobo por corrida, priorizando por nivel de alerta |

El escaneo de precipitación no tiene parámetros propios en `env_prod.json` por ahora — la
ventana (últimos 30 días) y los umbrales por estado están definidos directamente en
`OpenMeteo/openmeteo.py` (`CAPITALES_VE`).

⚠️ `env_prod.json` contiene tu token real — está en `.gitignore`, no lo subas al repo.
Usa `env_prod.json.example` (con un valor de relleno) para que cualquiera que clone el
repo sepa qué archivo crear.

## Cómo correr el sistema

### Automático (recomendado)

```bash
python ejecutar_pipeline.py
```

Corre todas las etapas en orden (incluida la de precipitación), escribe el log en
`descargas/logs/pipeline_<fecha>_<hora>.log`, y se detiene con un mensaje claro en la
etapa donde falle (no sigue a la siguiente etapa si la anterior no terminó bien).

### Manual, etapa por etapa (para depurar)

```bash
# 1) Scraper
python buscador.py

# 2) Unir CSV de los workers
python -m procesamiento.unir_partes . noticias_crudas.xlsx

# 3) Limpieza + clasificación + NER
python -m procesamiento.limpieza_clasificacion noticias_crudas.xlsx noticias_procesadas.xlsx

# 4) Métricas y nivel de alerta
python -m procesamiento.metricas_alerta noticias_procesadas.xlsx alertas_por_estado.xlsx 48

# 5) (solo la primera vez, o si cambias algún XLSForm) Desplegar formularios
python -m kobo.gestionar_formularios noticias_emergencia TU_API_TOKEN
python -m kobo.gestionar_formularios metricas_alerta TU_API_TOKEN
python -m kobo.gestionar_formularios precipitacion_nacional TU_API_TOKEN

# 6) Subir noticias + métricas
python -m kobo.subir_a_kobo noticias_procesadas.xlsx alertas_por_estado.xlsx TU_API_TOKEN TU_USUARIO_KOBO 10

# 7) Escaneo y envío de precipitación nacional (independiente del resto)
python -m OpenMeteo.openmeteo
```

## Las etapas del pipeline, en detalle

### 1. Scraper
Genera queries del tipo `venezuela "<medio>" "<estado>" (<palabras clave>) after:<fecha> before:<fecha>`
contra DuckDuckGo, usando Selenium con varios navegadores en paralelo. Cada worker
guarda resultados parciales incrementalmente (`page_number`, `rank`, `title`, `url`,
`fecha`, `snippet_full`, `criterio_busqueda`, etc.) en su propio CSV.

### 2. Unir partes
Detecta automáticamente todos los `_part*.csv` generados (sin importar cuántos workers
se usaron), los concatena, deduplica por URL, y fusiona con el xlsx acumulado de
corridas anteriores.

### 3. Limpieza y clasificación
- Normaliza texto (minúsculas, sin tildes, sin signos).
- Filtra registros que no correspondan a Venezuela (usando geografía completa: estados,
  municipios, parroquias, ciudades) y excluye ruido de otros países.
- Convierte la fecha a un `datetime` real (`fecha_dt`).
- Clasifica cada noticia por: zona geográfica, nivel de afectación (daños/víctimas/
  rescate), medios de logística (aéreo/acuático/terrestre) y tipo de evento.
- Extrae lugares y actores/autoridades mencionados con NER (`es_core_news_lg` de spaCy),
  limpiando el resultado contra una blacklist y tabla de equivalencias.

### 4. Métricas y nivel de alerta (noticias)
Agrupa las noticias por *estado × tipo de evento* dentro de la ventana de tiempo
configurada y calcula, por grupo: número de noticias, número de fuentes distintas,
si hay víctimas/rescate/daños mencionados, fecha más reciente, y el nivel de alerta
(ver regla abajo).

### 5. Precipitación nacional (hidrológico)
Consulta en paralelo (`ThreadPoolExecutor`) la API histórica de Open-Meteo para las 24
capitales de estado, sumando la precipitación diaria de los últimos 30 días. Cada
estado tiene sus propios umbrales de `amarillo`/`naranja`/`rojo` en `CAPITALES_VE`
(zonas áridas o andinas toleran menos agua acumulada que las zonas selváticas), y se
calcula además un porcentaje de saturación respecto al umbral rojo. El resultado se
normaliza al formato que espera Kobo (`estado` como *choice name*, `nivel_alerta` en
minúscula) antes de enviarse.

### 6. KoboToolbox
- **Formularios**: se crean automáticamente la primera vez que no existen
  (`kobo/gestionar_formularios.py`); si ya existen, nunca se recrean ni se borran.
- **Noticias**: se seleccionan al menos `minimo_noticias_a_subir`, priorizando por
  severidad (Rojo → Naranja → Amarillo → Verde) y completando con las más recientes.
  Se deduplican contra un registro local (`noticias_enviadas_kobo.json`) para no subir
  el mismo enlace en corridas sucesivas.
- **Métricas de alerta**: se suben deduplicando por `estado|tipo_evento|día|nivel`
  (`alertas_enviadas_kobo.json`) — si el nivel no cambia en el mismo día, no se repite
  el snapshot; si cambia (o cambia el día), se sube como punto nuevo de la línea de
  tiempo.
- **Precipitación nacional**: se sube sin deduplicar — cada corrida agrega un snapshot
  nuevo por estado, igual que las métricas de noticias, para armar su propia línea de
  tiempo en el tablero.

## Reglas de nivel de alerta

### Noticias (por estado × tipo de evento, ventana de 48h por defecto)

| Nivel | Condición |
|---|---|
| 🔴 **Rojo** | Hay mención de víctimas, confirmada por **2 o más fuentes distintas** |
| 🟠 **Naranja** | Hay rescate activo o daños estructurales mencionados (con al menos 1 fuente) |
| 🟡 **Amarillo** | 2 o más noticias sobre el evento, sin víctimas/rescate/daños confirmados |
| 🟢 **Verde** | 1 sola noticia, sin señales de impacto — informativo, no dispara acción |

La exigencia de 2 fuentes para Rojo es deliberada: evita que una nota mal interpretada
de un solo medio dispare una alerta máxima.

### Precipitación (por estado, ventana de 30 días)

| Nivel | Condición |
|---|---|
| 🔴 **Rojo** | Lluvia acumulada ≥ umbral rojo del estado |
| 🟠 **Naranja** | Lluvia acumulada ≥ umbral naranja del estado |
| 🟡 **Amarillo** | Lluvia acumulada ≥ umbral amarillo del estado |
| 🟢 **Verde** | Por debajo del umbral amarillo |

Los umbrales son propios de cada estado (definidos en `CAPITALES_VE`, dentro de
`OpenMeteo/openmeteo.py`) y no se cruzan con los de noticias — son dos señales
independientes que el tablero de Power BI puede comparar entre sí.

## KoboToolbox: formularios y datos

Tres formularios, pensados para que el tablero de Power BI los lea directo sin
recalcular nada:

**`noticias_emergencia`** — una fila por noticia: `fecha`, `titulo`, `enlace`,
`estado`, `tipo_evento`, `medio`, `nivel_alerta_asociado`, `criterio_busqueda`.

**`metricas_alerta`** — una fila por *estado × tipo de evento × corrida*:
`fecha_calculo`, `estado`, `tipo_evento`, `ventana_horas`, `n_noticias`,
`n_fuentes_distintas`, `tiene_victimas`, `tiene_rescate_activo`,
`tiene_danios_estructurales`, `fecha_mas_reciente`, `nivel_alerta`, `urls_relacionadas`.

**`precipitacion_nacional`** — una fila por *estado × corrida*: `fecha_calculo`,
`estado`, `capital`, `precipitacion_30dias`, `saturacion`, `nivel_alerta`,
`umbral_amarillo`, `umbral_naranja`, `umbral_rojo`.

Los tipos de evento disponibles como choice en `noticias_emergencia_vzla` y
`metricas_alerta_vzla` son: `sismo`, `inundacion`, `deslave`, `lluvias`, `sequia`,
`huracan`. Los tres formularios comparten la lista de `estados` (24 estados de
Venezuela) y de `niveles_alerta` (`rojo`/`naranja`/`amarillo`/`verde`).

El envío de datos usa el protocolo OpenRosa contra el servidor gemelo de Kobo
(`kc.kobotoolbox.org` para cuentas en el servidor global `kf.kobotoolbox.org`), con el
mismo API token. Ver la sección de limitaciones más abajo sobre el estado de
verificación de este endpoint.

## Automatización (tareas programadas)

En Windows, usa el **Programador de Tareas** apuntando a:
- Programa: ruta a `python.exe`
- Argumentos: `ejecutar_pipeline.py`
- Iniciar en: la carpeta raíz del proyecto

Frecuencia sugerida: cada 12-24h, alineada con `ventana_dias` del scraper y
`ventana_horas_alerta` de las métricas. El escaneo de precipitación corre en cada
ejecución del pipeline (no tiene una frecuencia propia distinta).

## Limitaciones conocidas y pendientes

- **Precipitación depende de la disponibilidad de Open-Meteo**: si la API histórica
  falla o no responde para una capital dentro del `timeout` configurado, esa capital
  simplemente se omite del escaneo de esa corrida (no se reintenta ni se marca como
  error explícito).
- **Volumen de queries**: 24 medios × 23 estados = 552 queries por situación y por
  corrida. Con los tiempos observados en pruebas, esto puede tomar entre 20 y 30 minutos.

## Hoja de ruta

- Integrar métricas oficiales de **FUNVISIS** (sismos) e **INAMEH** (meteorología),
  además de Open-Meteo, como fuentes adicionales para preparar las alertas junto con
  las noticias de prensa.
- Activar el rastreo de `sequia` y `huracan` en corridas reales (ya soportado en el
  código; falta ejecutar corridas piloto y ajustar palabras clave según resultados).
- Evaluar reemplazar/complementar el scraper de DuckDuckGo con una alternativa más
  liviana si la cobertura de resultados lo permite (`html.duckduckgo.com/html/` se
  probó y mostró buena estabilidad pero baja cobertura de resultados; no reemplaza a
  Selenium por ahora).
