# Sistema de Monitoreo de Noticias y Alertas de Emergencia — Venezuela

Sistema automatizado que rastrea noticias de prensa sobre desastres o emergencias en Venezuela 
(lluvias/inundaciones, sismos, sequía, huracanes), las clasifica geográfica y temáticamente, 
calcula niveles de alerta por estado, y publica todo en KoboToolbox para alimentar un tablero 
de Power BI.

```
Flujo:
    Scraper (DuckDuckGo) → Unir partes → Limpieza/clasificación → Métricas de alerta → KoboToolbox → Power BI
```

## Tabla de contenido

- [Arquitectura](#arquitectura)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Instalación](#instalación)
- [Configuración (`env_prod.json`)](#configuración-env_prodjson)
- [Cómo correr el sistema](#cómo-correr-el-sistema)
- [Las 5 etapas del pipeline, en detalle](#las-5-etapas-del-pipeline-en-detalle)
- [Reglas de nivel de alerta](#reglas-de-nivel-de-alerta)
- [KoboToolbox: formularios y datos](#kobotoolbox-formularios-y-datos)
- [Automatización (tareas programadas)](#automatización-tareas-programadas)
- [Limitaciones conocidas y pendientes](#limitaciones-conocidas-y-pendientes)
- [Hoja de ruta](#hoja-de-ruta)

## Arquitectura

1. **Scraper multi-navegador** (`prebusqueda_multinavegador_emergencia.py`): recorre
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
5. **KoboToolbox** (`kobo/`): crea los formularios en Kobo la primera vez (si no
   existen) y sube las noticias relevantes + las métricas de alerta como respuestas,
   sin borrar nunca el histórico — cada corrida agrega un snapshot nuevo, lo que arma
   una línea de tiempo del nivel de alerta por estado y evento.
6. **`ejecutar_pipeline.py`**: orquesta las 5 etapas anteriores en orden, con logging
   detallado por fase (consola + archivo), deteniéndose y marcando claramente dónde
   falló si algo sale mal.

## Estructura del repositorio

```
.
├── prebusqueda_multinavegador_emergencia.py   # Scraper (Selenium + DuckDuckGo)
├── ejecutar_pipeline.py                       # Orquestador de todo el pipeline
├── env_prod.json                              # Configuración (NO subir con token real)
├── env_prod.json.example                      # Plantilla segura para el repo
├── requirements.txt
├── .gitignore
│
├── xlsforms/
│   ├── noticias_emergencia_vzla.xlsx          # XLSForm — noticias relevantes
│   └── metricas_alerta_vzla.xlsx              # XLSForm — métricas de alerta
│
├── procesamiento/
│   ├── __init__.py
│   ├── diccionarios.py                        # Palabras clave, geografía, blacklist NER
│   ├── unir_partes.py                         # Etapa 2
│   ├── limpieza_clasificacion.py              # Etapa 3
│   └── metricas_alerta.py                     # Etapa 4
│
├── kobo/
│   ├── __init__.py
│   ├── xlsform_builder.py                     # Genera los XLSForm desde los diccionarios
│   ├── gestionar_formularios.py               # Crear/desplegar formularios + enviar datos
│   └── subir_a_kobo.py                        # Etapa 5: selección + envío de datos
│
└── logs/                                      # Generado en tiempo de ejecución (ignorado en git)
```

## Instalación

Requiere Python 3.12 y Google Chrome instalado (el scraper usa `webdriver-manager` para
descargar el ChromeDriver correspondiente automáticamente).

```bash
pip install -r requirements.txt
python -m spacy download es_core_news_lg
```

`requirements.txt`:
```
pandas
openpyxl
unidecode
selenium
selenium-stealth
webdriver-manager
spacy
requests
```

## Configuración (`env_prod.json`)

Copia `env_prod.json.example` a `env_prod.json` y completa tu token de Kobo
(`https://kf.kobotoolbox.org/token/?format=json`, estando logueado).

```jsonc
{
  "kobo": {
    "server": "https://kf.kobotoolbox.org/",
    "api_token": "TU_TOKEN_AQUI",
    "form_id_noticias": "noticias_emergencia_vzla",
    "form_id_metricas": "metricas_alerta_vzla"
  },
  "rutas": {
    "carpeta_base": ".",
    "scraper_script": "prebusqueda_multinavegador_emergencia.py",
    "noticias_crudas": "noticias_crudas.xlsx",
    "noticias_procesadas": "noticias_procesadas.xlsx",
    "alertas": "alertas_por_estado.xlsx",
    "registro_envios_kobo": "noticias_enviadas_kobo.json",
    "carpeta_logs": "logs"
  },
  "parametros": {
    "ventana_horas_alerta": 48,
    "minimo_noticias_a_subir": 10
  },
  "scraper": {
    "situacion": "lluvias",
    "num_workers": 4,
    "group_start_index": 0,
    "usar_fechas": true,
    "fecha_desde": null,
    "fecha_hasta": null,
    "ventana_dias": 2,
    "region_gl": "ve",
    "carpeta_salida": "c:/Users/ACER/Desktop/Minado_noticias",
    "medios": ["..."],
    "estados": ["..."]
  }
}
```

**Parámetros clave que se pueden ajustar sin tocar código:**

| Parámetro | Qué hace |
|---|---|
| `scraper.situacion` | Tipo de evento a rastrear: `lluvias`, `sismo`, `sequia` o `huracan` |
| `scraper.num_workers` | Cuántos navegadores en paralelo lanza el scraper |
| `scraper.fecha_desde` / `fecha_hasta` | Rango fijo de fechas (para pruebas). Si se dejan en `null`, se calcula automáticamente como *(hoy − `ventana_dias`)* a *hoy* |
| `scraper.ventana_dias` | Tamaño de la ventana automática de fechas cuando no hay fechas fijas |
| `scraper.medios` / `estados` | Listas de medios y estados a cruzar en el barrido |
| `parametros.ventana_horas_alerta` | Ventana de tiempo para calcular el nivel de alerta (48h por defecto) |
| `parametros.minimo_noticias_a_subir` | Mínimo de noticias a subir a Kobo por corrida, priorizando por nivel de alerta |

⚠️ `env_prod.json` contiene tu token real — está en `.gitignore`, no lo subas al repo.
Usa `env_prod.json.example` (con un valor de relleno) para que cualquiera que clone el
repo sepa qué archivo crear.

## Cómo correr el sistema

### Automático (recomendado)

```bash
python ejecutar_pipeline.py
```

Corre las 5 etapas en orden, escribe el log en `logs/pipeline_<fecha>_<hora>.log`, y se
detiene con un mensaje claro en la etapa donde falle (no sigue a la siguiente etapa si
la anterior no terminó bien).

### Manual, etapa por etapa (para depurar)

```bash
# 1) Scraper
python prebusqueda_multinavegador_emergencia.py

# 2) Unir CSV de los workers
python -m procesamiento.unir_partes . noticias_crudas.xlsx

# 3) Limpieza + clasificación + NER
python -m procesamiento.limpieza_clasificacion noticias_crudas.xlsx noticias_procesadas.xlsx

# 4) Métricas y nivel de alerta
python -m procesamiento.metricas_alerta noticias_procesadas.xlsx alertas_por_estado.xlsx 48

# 5) (solo la primera vez, o si cambias el XLSForm) Desplegar formularios
python -m kobo.gestionar_formularios noticias_emergencia_vzla TU_API_TOKEN
python -m kobo.gestionar_formularios metricas_alerta_vzla TU_API_TOKEN

# 6) Subir noticias + métricas
python -m kobo.subir_a_kobo noticias_procesadas.xlsx alertas_por_estado.xlsx TU_API_TOKEN 10
```

## Las 5 etapas del pipeline, en detalle

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

### 4. Métricas y nivel de alerta
Agrupa las noticias por *estado × tipo de evento* dentro de la ventana de tiempo
configurada y calcula, por grupo: número de noticias, número de fuentes distintas,
si hay víctimas/rescate/daños mencionados, fecha más reciente, y el nivel de alerta
(ver regla abajo).

### 5. KoboToolbox
- **Formularios**: se crean automáticamente la primera vez que no existen
  (`kobo/gestionar_formularios.py`); si ya existen, nunca se recrean ni se borran.
- **Noticias**: se seleccionan al menos `minimo_noticias_a_subir`, priorizando por
  severidad (Rojo → Naranja → Amarillo → Verde) y completando con las más recientes.
  Se deduplican contra un registro local (`noticias_enviadas_kobo.json`) para no subir
  el mismo enlace en corridas sucesivas.
- **Métricas de alerta**: se suben SIN deduplicar — cada corrida agrega un snapshot
  nuevo por *estado × tipo de evento*, lo que arma la línea de tiempo de evolución del
  nivel de alerta en el tablero.

## Reglas de nivel de alerta

Calculadas por *(estado, tipo de evento)* dentro de la ventana de tiempo configurada
(48h por defecto):

| Nivel | Condición |
|---|---|
| 🔴 **Rojo** | Hay mención de víctimas, confirmada por **2 o más fuentes distintas** |
| 🟠 **Naranja** | Hay rescate activo o daños estructurales mencionados (con al menos 1 fuente) |
| 🟡 **Amarillo** | 2 o más noticias sobre el evento, sin víctimas/rescate/daños confirmados |
| 🟢 **Verde** | 1 sola noticia, sin señales de impacto — informativo, no dispara acción |

La exigencia de 2 fuentes para Rojo es deliberada: evita que una nota mal interpretada
de un solo medio dispare una alerta máxima.

## KoboToolbox: formularios y datos

Dos formularios, pensados para que el tablero de Power BI los lea directo sin
recalcular nada:

**`noticias_emergencia_vzla`** — una fila por noticia: `fecha`, `titulo`, `enlace`,
`estado`, `tipo_evento`, `medio`, `nivel_alerta_asociado`, `criterio_busqueda`.

**`metricas_alerta_vzla`** — una fila por *estado × tipo de evento × corrida*:
`fecha_calculo`, `estado`, `tipo_evento`, `ventana_horas`, `n_noticias`,
`n_fuentes_distintas`, `tiene_victimas`, `tiene_rescate_activo`,
`tiene_danios_estructurales`, `fecha_mas_reciente`, `nivel_alerta`, `urls_relacionadas`.

Los tipos de evento disponibles como choice en ambos formularios son:
`sismo`, `inundacion`, `deslave`, `lluvias`, `sequia`, `huracan`.

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
`ventana_horas_alerta` de las métricas.

## Limitaciones conocidas y pendientes

- **Envío de datos a Kobo no verificado en producción**: la creación/despliegue de
  formularios (`upload_koboform`) sí está probada (viene de código ya usado en otro
  proyecto), pero el envío de submissions vía OpenRosa (`kc.kobotoolbox.org/api/v1/submissions`)
  se construyó a partir de documentación/foros oficiales, no de una prueba directa contra
  la cuenta real. Probar con pocos registros antes de una subida masiva.
- **Formularios ya desplegados no ganan choices nuevos automáticamente**: si
  `noticias_emergencia_vzla` o `metricas_alerta_vzla` ya existían en Kobo antes de
  agregar `sequia`/`huracan`, hay que recrearlos manualmente (esto borra su histórico)
  para que esas opciones aparezcan.
- **Volumen de queries**: 24 medios × 23 estados = 552 queries por situación y por
  corrida. Con los tiempos observados en pruebas, esto puede ser lento; una optimización
  pendiente es agrupar medios con `OR` dentro de menos queries en vez de una por medio.
- **Condición de carrera en `ChromeDriverManager`** al iniciar varios workers a la vez
  (error `WinError 5: Acceso denegado` en el driver): se identificó la causa (varios
  procesos descargando/moviendo el mismo binario en simultáneo) y se propuso resolver el
  path del driver una sola vez antes de lanzar los workers — pendiente de confirmar que
  se aplicó.
- **Logging de crash a archivo en el scraper**: se agregó un `try/except` con log a
  archivo por worker para capturar tracebacks que la consola de Windows pierde con
  multiprocessing — pendiente de una corrida larga que lo confirme en un caso real de
  falla.
- **Diccionario de equivalencias de frecuencia** (`EQUIVALENCIAS_FRECUENCIA` en
  `diccionarios.py`) tiene entradas con raíces truncadas que no generan match real
  contra el código actual (usa igualdad exacta, no substring) — no afecta las alertas
  (que usan su propio mapeo en `metricas_alerta.py`), solo los reportes descriptivos
  exploratorios de `generar_resumenes()`.

## Hoja de ruta

- Integrar métricas oficiales de **FUNVISIS** (sismos), **INAMEH** (meteorología) y
  mediciones satelitales, como fuentes adicionales para preparar las alertas junto con
  las noticias de prensa.
- Activar el rastreo de `sequia` y `huracan` en corridas reales (ya soportado en el
  código; falta ejecutar corridas piloto y ajustar palabras clave según resultados).
- Evaluar reemplazar/complementar el scraper de DuckDuckGo con una alternativa más
  liviana si la cobertura de resultados lo permite (`html.duckduckgo.com/html/` se
  probó y mostró buena estabilidad pero baja cobertura de resultados; no reemplaza a
  Selenium por ahora).