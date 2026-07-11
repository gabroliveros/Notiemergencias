#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import random
import re
import socket
import itertools
import unicodedata
import openpyxl
import pandas as pd
from multiprocessing import Process
from datetime import timedelta
import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from selenium_stealth import stealth
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote_plus
from urllib.parse import urlparse

# ---------------- CONFIGURACIÓN ----------------
USE_MULTIPLE_BROWSERS = True   # True -> usar multiprocessing con N navegadores
NUM_BROWSERS = 4               # cuántos navegadores/procesos quieres lanzar
GROUP_START_INDEX = 0         # índice en 'grupos' desde donde iniciar (ej: 'comite' está en 13 en tu lista)

PROXY_ROTATION_PAGES = 5   # (queda definido pero no lo usamos)

MIN_DELAY_BETWEEN_PAGES = 3.1
MAX_DELAY_BETWEEN_PAGES = 5.6

SEARCH_ENGINE = 'duckduckgo'    # Opción: 'google' o 'duckduckgo'

# Rutas base (las rutas finales por worker tendrán sufijo _part{i})
RUTA_CARPETA = r'c:/Users/ACER/Desktop/Minado_noticias'
RUTA_EXCEL_BASE = os.path.join(RUTA_CARPETA, 'ddg_noticias_vzla_OPEN.xlsx')
RUTA_PROGRESO_BASE = os.path.join(RUTA_CARPETA, 'progreso_busqueda.json')
os.makedirs(RUTA_CARPETA, exist_ok=True)

REGION_GL = 've'
FORCE_SITE_VE = False
SOCIAL = False

hoy = datetime.date.today()

# ---------------- FILTRO DE FECHAS ----------------
# Nota: Google acepta nativamente 'after:YYYY-MM-DD before:YYYY-MM-DD' en el texto.
# DuckDuckGo prefiere parámetros en la URL, pero incluirlo en la query ayuda a perfilar.
USAR_FECHAS = True
FECHA_DESDE = '2026-07-03'
FECHA_HASTA = '2026-07-04'

FECHA_DESDE = '2026-06-25'
FECHA_HASTA = '2026-07-09' 

# ---------------- DICCIONARIOS Y GRUPOS PARA EL BARRIDO ----------------

# Palabras clave relacionadas con el evento (Agrupadas con OR para reducir queries)
KEYWORDS_LLUVIAS = (
    '(lluvia OR crecida OR inundacion OR deslizamiento OR desbord OR '
    'draga OR precipitacion OR vaguada OR tormenta OR damnificados OR afectados)'
)

# Medios de comunicación de Venezuela (puedes usar sus nombres o sus dominios ej: site:el-nacional.com)
MEDIOS_VENEZUELA = [
    'El Nacional', 'El Universal', 'Últimas Noticias', 'El Diario', 'La Patilla', 
    'TalCual', 'Efecto Cocuyo', 'Diario Vea', 'Diario La Nación', 'Noticia al Día'
]

ESTADOS_VENEZUELA = [
    'amazonas', 'apure', 'aragua', 'barinas', 'bolivar', 'carabobo', 'cojedes', 'delta amacuro', 
    'distrito capital', 'falcon', 'guarico', 'lara', 'la guaira', 'merida', 'miranda', 'monagas', 
    'nueva esparta', 'portuguesa', 'sucre', 'tachira', 'trujillo', 'yaracuy', 'zulia'
]

# Exclusiones para limpiar ruido de formatos no deseados
EXCLUSION = ' -filetype:pdf -filetype:doc -filetype:xls -scribd'

# ---------------- GENERADOR DE QUERIES OPTIMIZADO ----------------

def generar_queries_lluvias(lista_medios, lista_estados, rango_fechas=None):
    res = []
    
    # Estructura de la query: 
    # venezuela "Nombre del Medio" "Nombre del Estado" (lluvia OR inundacion...) after:YYYY-MM-DD before:YYYY-MM-DD
    for medio in lista_medios:
        for estado in lista_estados:
            query_base = f'venezuela "{medio}" "{estado}" {KEYWORDS_LLUVIAS}{EXCLUSION}'
            
            if rango_fechas:
                query_base += f' after:{rango_fechas[0]} before:{rango_fechas[1]}'
                
            res.append(query_base)
    return res

# Control de índice de inicio para no repetir trabajo si se corta
if GROUP_START_INDEX and 0 <= GROUP_START_INDEX < len(MEDIOS_VENEZUELA):
    medios_trabajo = MEDIOS_VENEZUELA[GROUP_START_INDEX:]
else:
    medios_trabajo = MEDIOS_VENEZUELA[:]

# Configuración del rango de fechas para la función
fechas_filtro = (FECHA_DESDE, FECHA_HASTA) if USAR_FECHAS else None

# Generación final
queries_total = generar_queries_lluvias(medios_trabajo, ESTADOS_VENEZUELA, fechas_filtro)
queries_total = queries_total[:5] 
print(f"Total queries generadas para el barrido: {len(queries_total)}")
print(f"Ejemplo de Query 1: {queries_total[0]}")

# ---------------- RASPA POR RANGO DE FECHAS ---------------------------------------

def generar_consultas_por_dia(start_date, end_date):
    consultas = []
    for r in SOCIAL_SITES:
        for e in estados:
            fecha_actual = datetime.strptime(start_date, "%Y-%m-%d")
            fecha_fin = datetime.strptime(end_date, "%Y-%m-%d")
            base_query = 'site:'+ r + ' venezuela vzla venzolan ' + e
            while fecha_actual <= fecha_fin:
                siguiente = fecha_actual + timedelta(days=1)
                consulta = (
                    f"{base_query} "
                    f"after:{fecha_actual.strftime('%Y-%m-%d')} "
                    f"before:{siguiente.strftime('%Y-%m-%d')}"
                )
                consultas.append(consulta)
                fecha_actual = siguiente

    return consultas

# Raspa todo lo que consiga en un rango de fechas
# queries_total = generar_consultas_por_dia('2026-07-01', '2026-07-02')
# print(len(queries_total), '\n', queries_total[:5])

# ----------------- funciones auxiliares -----------------

def iniciar_driver_sigiloso(proxy=None, user_data_dir=None, profile_dir=None):
    UA_LIST = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15"
    ]
    ua = random.choice(UA_LIST)

    options = Options()
    options.add_argument("--start-maximized")
    w = random.choice([1200, 1300, 1366, 1440, 1600])
    h = random.choice([700, 768, 800, 900])
    options.add_argument(f"--window-size={w},{h}")

    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")
        if profile_dir:
            options.add_argument(f'--profile-directory={profile_dir}')

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--lang=es-ES")
    options.add_argument(f"--user-agent={ua}")

    # no proxies en este archivo (se prescinde de ellos)
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        script = r"""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'languages', {get: () => ['es-ES','es']});
        Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
        Object.defineProperty(navigator, 'mimeTypes', {get: () => [1,2,3]});
        window.chrome = { runtime: {} };
        const originalQuery = window.navigator.permissions.query;
        try {
            window.navigator.permissions.__proto__.query = function(parameters) {
                if (parameters && parameters.name === 'notifications') {
                    return Promise.resolve({ state: Notification.permission });
                }
                return originalQuery(parameters);
            };
        } catch (e) {}
        try {
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) { return 'Intel Inc.'; }
                if (parameter === 37446) { return 'Intel Iris OpenGL Engine'; }
                return getParameter(parameter);
            };
        } catch (e) {}
        """
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
    except Exception:
        pass

    try:
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": ua})
    except Exception:
        pass

    try:
        driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {'timezoneId': 'America/New_York'})
    except Exception:
        pass

    try:
        time.sleep(0.4)
        driver.set_window_size(w, h)
    except Exception:
        pass

    time.sleep(random.uniform(0.4, 1.0))
    return driver

def escribir_como_humano(elemento, texto, min_delay=0.06, max_delay=0.22):
    for letra in texto:
        elemento.send_keys(letra)
        time.sleep(random.uniform(min_delay, max_delay))

def limpiar_url_google(url):
    if not url:
        return None
    m = re.search(r'/url\?q=(https?://[^&]+)', url)
    if m:
        return m.group(1)
    m2 = re.search(r'url\?q=(https?://[^&]+)', url)
    if m2:
        return m2.group(1)
    return url

MESES_ES = {
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'sep': 9, 'set': 9, 'oct': 10, 'nov': 11, 'dic': 12
}
MESES_EN = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

def extraer_fecha_de_snippet(texto, fecha_referencia=None):
    """
    Extrae la fecha de publicación que DuckDuckGo suele anteponer al snippet,
    con o sin separador visible (a veces queda pegada directo al texto).
    Formatos soportados:
      - Relativo ES: "hace 3 dias", "hace 2 semanas", "ayer", "hoy"
      - Relativo EN: "3 days ago", "2 weeks ago"
      - Absoluto EN: "Jul 4, 2026"
      - Absoluto ES: "4 jul 2026", "4 de julio de 2026"
      - ISO:         "2026-07-04"
    Devuelve la fecha en formato 'YYYY-MM-DD' o None si no reconoce ningun
    patron (se prefiere devolver None a inventar una fecha incorrecta).
    """
    if not texto:
        return None

    ref = fecha_referencia or datetime.now()

    texto_norm = unicodedata.normalize('NFKD', texto.lower())
    texto_norm = ''.join(c for c in texto_norm if not unicodedata.combining(c))
    texto_norm = texto_norm.strip()

    # --- Fechas relativas ("hace N unidad" / "N unidad ago") ---
    m = re.match(r'hace\s+(\d+)\s+(dia|dias|hora|horas|semana|semanas|mes|meses|ano|anos)', texto_norm)
    if not m:
        m = re.match(r'(\d+)\s+(day|days|hour|hours|week|weeks|month|months|year|years)\s+ago', texto_norm)
    if m:
        cantidad = int(m.group(1))
        unidad = m.group(2)
        if unidad.startswith(('dia', 'day')):
            delta = timedelta(days=cantidad)
        elif unidad.startswith(('hora', 'hour')):
            delta = timedelta(hours=cantidad)
        elif unidad.startswith(('semana', 'week')):
            delta = timedelta(weeks=cantidad)
        elif unidad.startswith(('mes', 'month')):
            delta = timedelta(days=cantidad * 30)
        else:
            delta = timedelta(days=cantidad * 365)
        return (ref - delta).strftime('%Y-%m-%d')

    if re.match(r'^ayer\b', texto_norm):
        return (ref - timedelta(days=1)).strftime('%Y-%m-%d')
    if re.match(r'^hoy\b', texto_norm):
        return ref.strftime('%Y-%m-%d')

    # --- Fecha ISO ("2026-07-04") ---
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', texto_norm)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime('%Y-%m-%d')
        except ValueError:
            return None

    # --- "4 de julio de 2026" / "4 julio 2026" / "14 jul 2025" ---
    m = re.match(r'(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})', texto_norm)
    if not m:
        m = re.match(r'(\d{1,2})\s+([a-z]{3,})\.?\s+(?:de\s+)?(\d{4})', texto_norm)
    if m:
        dia, mes_txt, anio = m.group(1), m.group(2)[:3], m.group(3)
        mes = MESES_ES.get(mes_txt)
        if mes:
            try:
                return datetime(int(anio), mes, int(dia)).strftime('%Y-%m-%d')
            except ValueError:
                return None

    # --- "Jul 4, 2026" / "Jul. 4, 2026" ---
    m = re.match(r'([a-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})', texto_norm)
    if m:
        mes_txt, dia, anio = m.group(1)[:3], m.group(2), m.group(3)
        mes = MESES_EN.get(mes_txt)
        if mes:
            try:
                return datetime(int(anio), mes, int(dia)).strftime('%Y-%m-%d')
            except ValueError:
                return None

    return None

def detectar_captcha_simple(driver):
    try:
        url = driver.current_url.lower()
        page = driver.page_source.lower()
        if "sorry/index" in url or "consent" in url or "detected unusual traffic" in page or "captcha" in page:
            return True
    except Exception:
        return False
    return False

def esperar_resolucion_captcha(driver):
    if detectar_captcha_simple(driver):
        print("\n" + "!"*60)
        print("⚠️ CAPTCHA o banner detectado. Resuélvelo en la ventana del navegador (acepta cookies si aparece).")
        print("Cuando termines y la página de resultados vuelva, presiona ENTER en esta consola para continuar.")
        print("!"*60 + "\n")
        input()
        time.sleep(random.uniform(1, 2))
        return True
    return False

def scroll_lento(driver, min_scrolls=14, max_scrolls=28):
    try:
        altura_total = driver.execute_script("return document.body.scrollHeight")
        pasos = random.randint(min_scrolls, max_scrolls)
        paso_px = max(50, int(altura_total / pasos))
        for i in range(pasos):
            desplazamiento = max(30, paso_px + random.randint(-30, 30))
            driver.execute_script(f"window.scrollBy(0, {desplazamiento});")
            try:
                acciones = ActionChains(driver)
                acciones.move_by_offset(random.randint(-30, 30), random.randint(-30, 30)).perform()
                acciones.move_by_offset(-3, -3).perform()
            except Exception:
                pass
            time.sleep(random.uniform(0.6, 1.1))
        if random.random() < 0.4:
            driver.execute_script("window.scrollBy(0, -80);")
            time.sleep(random.uniform(0.5, 0.9))
    except Exception:
        pass

def guardar_resultados_parciales(df, ruta_csv, ruta_excel):
    """
    Guardado incremental en CSV (append) para velocidad (UTF-8-SIG para Excel):
    - si no existe CSV, lo crea con cabecera
    - si existe, añade solo filas nuevas (compara por conteo de filas)
    - fallback: si falla CSV, intenta escribir .xlsx completo como última opción
    """
    try:
        if df is None or len(df) == 0:
            return

        csv_path = ruta_csv

        if not os.path.exists(csv_path):
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            return

        try:
            existing_lines = 0
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                for _ in f:
                    existing_lines += 1
            rows_already = max(0, existing_lines - 1)
        except Exception:
            rows_already = 0

        if len(df) <= rows_already:
            return

        new_rows = df.iloc[rows_already:]
        new_rows.to_csv(csv_path, index=False, mode='a', header=False, encoding='utf-8-sig')

    except Exception as e:
        print("Error guardando CSV parcial (intento fallback XLSX):", e)
        try:
            df.to_excel(ruta_excel, index=False)
        except Exception as e2:
            print("Fallback XLSX también falló:", e2)

def build_search_url(engine, encoded_query, start=0, region_gl=None, ddg_use_html=False):
    engine = (engine or 'google').lower()
    if engine == 'google':
        base = f"https://www.google.com/search?q={encoded_query}&hl=es"
        if region_gl:
            base += f"&gl={region_gl}"
        if start and int(start) > 0:
            base += f"&start={int(start)}"
        return base

    if engine == 'duckduckgo':
        if ddg_use_html:
            base = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            if start and int(start) > 0:
                base += f"&s={int(start)}"
            return base
        else:
            base = f"https://duckduckgo.com/?q={encoded_query}&t=ffab&ia=web"
            return base

    raise ValueError("engine desconocido: usa 'google' o 'duckduckgo'")

def extraer_resultados_de_serp(driver, page_number, engine='duckduckgo'):
    resultados = []
    engine = (engine or 'google').lower()
    try:
        if engine == 'duckduckgo':
            time.sleep(2)
            bloques = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='result'], li[data-layout='organic'], div[data-testid='result']")
            print(f"DEBUG bloques encontrados (selector principal): {len(bloques)}")
            if not bloques:
                bloques = driver.find_elements(By.CSS_SELECTOR, ".results article, .nrn-react-div, .web-result")
                print(f"DEBUG bloques encontrados (selector fallback): {len(bloques)}")
            if not bloques:
                print("DEBUG primeros 1500 caracteres del body:", driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")[:1500])
            urls_vistas_pagina = set()
            rank = 1
            for b in bloques:
                try:
                    title = ""
                    url = ""
                    displayed = ""
                    snippet = ""
                    snippet_full = ""
                    rich_type = ""
                    try:
                        a = None
                        for selector in ["a[data-testid='result-title-a']", "h2 a", "a.result__a", "article a"]:
                            try:
                                a = b.find_element(By.CSS_SELECTOR, selector)
                                if a:
                                    break
                            except:
                                continue
                        if a:
                            title = (a.text or "").strip()
                            url = a.get_attribute("href") or ""
                            if url and any(x in url for x in ["duckduckgo.com", "javascript:", "#", "/settings", "/maps"]):
                                continue
                    except Exception:
                        title = ""
                        url = ""
                    try:
                        for selector in ["span[data-testid='result-extras-url-link']", "cite", ".result__url", ".result__domain"]:
                            try:
                                disp = b.find_element(By.CSS_SELECTOR, selector)
                                if disp and disp.text:
                                    displayed = (disp.text or "").strip()
                                    break
                            except:
                                continue
                    except Exception:
                        displayed = ""
                    try:
                        # 1) Intentar encontrar el contenedor explícito de snippet (si existe)
                        snippet_full = ""
                        try:
                            snips = b.find_elements(By.CSS_SELECTOR, "[data-result='snippet'], div[data-result='snippet']")
                            for s in snips:
                                try:
                                    txt = (s.get_attribute("textContent") or s.get_attribute("innerText") or "").strip()
                                    # filtrar textos cortos y textos de menú/acciones conocidos
                                    if txt and len(txt) > 20 and not any(p in txt for p in ["Incluir solo resultados", "Rehacer la búsqueda", "Bloquea este sitio", "Compartir comentarios"]):
                                        snippet_full = txt
                                        break
                                except Exception:
                                    continue
                        except Exception:
                            snippet_full = ""
                        # 2) Si no se encontró, intentar selectores genéricos (fallback)
                        if not snippet_full:
                            for selector in ["div[data-testid='result-snippet']", ".result__snippet", ".result__snippet *", ".snippet", "div:nth-child(3)"]:
                                try:
                                    elems = b.find_elements(By.CSS_SELECTOR, selector)
                                    for s in elems:
                                        try:
                                            txt = (s.get_attribute("textContent") or s.get_attribute("innerText") or "").strip()
                                            if txt and len(txt) > 20 and not any(p in txt for p in ["Incluir solo resultados", "Rehacer la búsqueda", "Bloquea este sitio", "Compartir comentarios"]):
                                                snippet_full = txt
                                                break
                                        except Exception:
                                            continue
                                    if snippet_full:
                                        break
                                except Exception:
                                    continue
                        # 3) Si sigue terminando en '...' intentar forzar lectura quitando clamp vía JS
                        if snippet_full.endswith("..."):
                            try:
                                # usar el primer nodo snippet válido (si lo encontramos), o el último elemento 's' inspeccionado
                                node = None
                                try:
                                    node = b.find_element(By.CSS_SELECTOR, "[data-result='snippet']")
                                except Exception:
                                    try:
                                        node = b.find_element(By.CSS_SELECTOR, ".result__snippet, .snippet")
                                    except Exception:
                                        node = None

                                if node:
                                    snippet_full_js = driver.execute_script(
                                        "let el = arguments[0];"
                                        "try { el.style.webkitLineClamp = 'unset'; el.style.display='block'; } catch(e) {}"
                                        "return (el.textContent || el.innerText || '').trim();",
                                        node
                                    )
                                    if snippet_full_js and len(snippet_full_js) > len(snippet_full):
                                        snippet_full = snippet_full_js.strip()
                            except Exception:
                                pass
                        # 4) Normalizar resultado final
                        snippet = snippet_full #snippet_full[:10000] + ("..." if len(snippet_full) > 10000 else "")
                    except Exception:
                        snippet = ""
                        snippet_full = ""
                    fecha = extraer_fecha_de_snippet(snippet_full)
                    if (title or url) and url and url not in urls_vistas_pagina and not any(x in url for x in ["duckduckgo.com", "javascript:", "#"]):
                        urls_vistas_pagina.add(url)
                        resultados.append({
                            "page_number": page_number,
                            "rank": rank,
                            "title": title,
                            "url": limpiar_url_google(url),
                            "displayed_url": displayed,
                            "fecha": fecha,
                            "snippet": snippet,
                            "snippet_full": snippet_full,
                            "rich_type": rich_type
                        })
                        rank += 1
                except Exception:
                    continue
            if not resultados:
                enlaces = driver.find_elements(By.TAG_NAME, "a")
                rank = 1
                for a in enlaces:
                    try:
                        href = a.get_attribute("href") or ""
                        texto = (a.text or "").strip()
                        if (texto and len(texto) > 10 and href and "http" in href and 
                            not any(x in href for x in ["duckduckgo.com", "javascript:", "#"]) and
                            href not in urls_vistas_pagina):
                            urls_vistas_pagina.add(href)
                            resultados.append({
                                "page_number": page_number,
                                "rank": rank,
                                "title": texto,
                                "url": limpiar_url_google(href),
                                "displayed_url": "",
                                "fecha": None,
                                "snippet": "",
                                "snippet_full": "",
                                "rich_type": ""
                            })
                            rank += 1
                    except Exception:
                        continue

        else:
            return []
    except Exception:
        pass

    return resultados

def ir_siguiente_pagina(driver, engine='google'):
    engine = (engine or 'google').lower()
    try:
        if engine == 'google':
            try:
                btn = driver.find_element(By.ID, "pnnext")
                href = btn.get_attribute("href") or ""
                m2 = re.search(r'start=(\d+)', href)
                current_start = 0
                m = re.search(r'(?:start|s)=(\d+)', driver.current_url or "")
                if m:
                    current_start = int(m.group(1))
                next_start = int(m2.group(1)) if m2 else current_start + 10
                if next_start > current_start:
                    return btn
            except Exception:
                pass
            try:
                link_next = driver.find_element(By.CSS_SELECTOR, "link[rel='next']")
                href = link_next.get_attribute("href") or ""
                m2 = re.search(r'start=(\d+)', href)
                current_start = 0
                m = re.search(r'(?:start|s)=(\d+)', driver.current_url or "")
                if m:
                    current_start = int(m.group(1))
                next_start = int(m2.group(1)) if m2 else current_start + 10
                if next_start > current_start:
                    anchors = driver.find_elements(By.TAG_NAME, "a")
                    for a in anchors:
                        ahref = a.get_attribute("href") or ""
                        if ahref.split('#')[0] == href.split('#')[0]:
                            return a
            except Exception:
                pass
            anchors = driver.find_elements(By.CSS_SELECTOR, "a[aria-label], a")
            for a in anchors:
                try:
                    aria = (a.get_attribute("aria-label") or "").lower()
                    txt = (a.text or "").lower()
                    href = a.get_attribute("href") or ""
                    if ('siguiente' in txt or 'siguiente' in aria or 'next' in aria or 'next' in txt):
                        m3 = re.search(r'start=(\d+)', href)
                        current_start = 0
                        m = re.search(r'(?:start|s)=(\d+)', driver.current_url or "")
                        if m:
                            current_start = int(m.group(1))
                        if m3:
                            next_start = int(m3.group(1))
                            if next_start > current_start:
                                return a
                        else:
                            return a
                except Exception:
                    continue
            return None

        elif engine == 'duckduckgo':
            # intentar forzar scroll al fondo (rápido)
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception:
                pass

            # PRIORIDAD: buscar botón "Mostrar todos..."
            try:
                try:
                    show_all = WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located((By.XPATH,
                            "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'mostrar todos')]"
                        ))
                    )
                except Exception:
                    show_all = None

                if show_all and show_all.is_displayed():
                    try:
                        print("DEBUG show_all outerHTML:", show_all.get_attribute("outerHTML")[:500])
                        print("DEBUG show_all visible/displayed:", show_all.is_displayed())
                    except Exception as e:
                        print("DEBUG error:", e)

                    try:
                        cur = (driver.current_url or "").lower()
                        # si la URL contiene un filtro site: (codificado o no), NO devolver el botón
                        if ('site%3a' in cur) or ('site:' in cur):
                            # no devolvemos show_all para no eliminar el filtro de site:
                            pass
                        else:
                            return show_all
                    except Exception:
                        # en caso de error conservador, devolverlo para el flujo original
                        return show_all
            except Exception:
                pass

            # 1) intentar localizar botón "Más resultados" por id / data-testid (rápido)
            try:
                btn_more = driver.find_element(By.ID, "more-results")
                if btn_more and btn_more.is_displayed():
                    return btn_more
            except Exception:
                pass

            try:
                btn_more = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='more-results-button']"))
                )
                if btn_more and btn_more.is_displayed():
                    return btn_more
            except Exception:
                pass

            # 2) probar varios selectores/variantes (anchors y botones)
            selectors = [
                "button[data-testid='more-results-button']",
                "a[data-testid='more-results-button']",
                "button[data-testid='more-results']",
                "a[data-testid='more-results']",
                "button#more-results",
                ".more-results",
                ".more-results-button"
            ]
            for sel in selectors:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    for e in elems:
                        try:
                            if e.is_displayed():
                                return e
                        except Exception:
                            continue
                except Exception:
                    continue

            # 3) fallback por texto dentro de botones/anchors (idiomas comunes)
            try:
                candidates = driver.find_elements(By.XPATH, "//button|//a")
                for c in candidates:
                    try:
                        txt = (c.text or "").lower()
                        if any(p in txt for p in ["more results", "ver más", "más resultados", "mostrar todos los resultados", "mostrar todos", "show more"]):
                            if c.is_displayed():
                                return c
                    except Exception:
                        continue
            except Exception:
                pass

            # 4) intentar dentro de iframes (anuncios/modals)
            try:
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                for i, f in enumerate(iframes):
                    try:
                        driver.switch_to.frame(f)
                        try:
                            b = driver.find_element(By.CSS_SELECTOR, "button[data-testid='more-results-button'], button#more-results")
                            if b and b.is_displayed():
                                driver.switch_to.default_content()
                                return b
                        except Exception:
                            pass
                        driver.switch_to.default_content()
                    except Exception:
                        try:
                            driver.switch_to.default_content()
                        except Exception:
                            pass
            except Exception:
                pass

            # 5) no encontrado
            return None
        else:
            return None
    except Exception:
        return None

# ----------------- worker main (cada proceso ejecuta esta función) -----------------

def worker_main(worker_id, queries_slice):
    """
    Ejecuta un scraper para queries_slice.
    Cada worker tiene sus propias rutas:
      - RUTA_EXCEL = RUTA_EXCEL_BASE.replace('.xlsx', f'_part{worker_id}.xlsx')
      - RUTA_CSV = RUTA_EXCEL.replace('.xlsx', '.csv')
      - RUTA_PROGRESO = RUTA_PROGRESO_BASE.replace('.json', f'_part{worker_id}.json')
    """
    # paths locales del worker
    ruta_excel = RUTA_EXCEL_BASE.replace('.xlsx', f'_part{worker_id}.xlsx')
    ruta_csv = ruta_excel.replace('.xlsx', '.csv')
    ruta_progreso = RUTA_PROGRESO_BASE.replace('.json', f'_part{worker_id}.json')
    ruta_log_error = ruta_excel.replace('.xlsx', '_error.log')
    import traceback
    try:
        # progreso local (por worker)
        if os.path.exists(ruta_progreso):
            try:
                with open(ruta_progreso, 'r', encoding='utf-8') as f:
                    progreso = json.load(f)
            except Exception:
                progreso = None
        else:
            progreso = None

        if not progreso:
            progreso = {
                "last_query_index": 0,
                "last_query": "",
                "last_page": 1,
                "last_start": 0,
                "results_file": ruta_excel,
                "rows_saved": 0
            }
            with open(ruta_progreso, 'w', encoding='utf-8') as f:
                json.dump(progreso, f, ensure_ascii=False, indent=2)

        # cargar resultados previos (si hay CSV del worker)
        resultados_acumulados = []
        if os.path.exists(ruta_csv):
            try:
                df_prev = pd.read_csv(ruta_csv, encoding='utf-8-sig')
                resultados_acumulados = df_prev.to_dict('records')
                print(f"[worker {worker_id}] Resultados previos cargados: {len(resultados_acumulados)}")
            except Exception:
                resultados_acumulados = []

        # iniciar webdriver
        driver = None
        try:
            driver = iniciar_driver_sigiloso(proxy=None)
            print(f"[worker {worker_id}] Driver iniciado.")
        except Exception as e:
            print(f"[worker {worker_id}] Error iniciando driver:", e)
            return

        def safe_get(url, retries=3):
            intento = 0
            nonlocal_driver = {'driver': driver}
            while intento < retries:
                try:
                    nonlocal_driver['driver'].get(url)
                    return True
                except WebDriverException as e:
                    intento += 1
                    print(f"[worker {worker_id}] WebDriverException en get():", e)
                    try:
                        nonlocal_driver['driver'].quit()
                    except Exception:
                        pass
                    try:
                        nonlocal_driver['driver'] = iniciar_driver_sigiloso(proxy=None)
                    except Exception:
                        pass
                    time.sleep(random.uniform(0.8, 1.6))
            return False

        # main loop por query en la slice proporcionada
        start_index_local = int(progreso.get('last_query_index', 0))
        # start_index_local se interpreta relativo a la slice; si hay progreso y last_query corresponde a un elemento de slice, se reanuda
        # buscamos si last_query está dentro de la slice y actualizamos start_index_local
        if progreso.get('last_query'):
            try:
                idx_in_slice = queries_slice.index(progreso['last_query'])
                start_index_local = idx_in_slice
            except Exception:
                # si no se encuentra, mantener 0
                start_index_local = 0

        for local_idx in range(start_index_local, len(queries_slice)):
            Q_ACTUAL = queries_slice[local_idx]
            print(f"[worker {worker_id}] 🔎 Iniciando búsqueda para: {Q_ACTUAL}")
            encoded_q = quote_plus(Q_ACTUAL)

            pagina_actual = 1
            start_val = 0
            max_paginas = 20

            # evitar clicar "Mostrar todos..." repetidamente en la misma query
            clicked_show_all = False

            # si la query contiene un filtro site: queremos impedir que se quite ese filtro
            forbid_show_all = False
            try:
                qlow = (Q_ACTUAL or "").lower()
                enc_low = (encoded_q or "").lower()
                if 'site:' in qlow or 'site%3a' in enc_low:
                    forbid_show_all = True
            except Exception:
                forbid_show_all = False

            search_url = build_search_url(SEARCH_ENGINE, encoded_q, start=start_val, region_gl=REGION_GL)
            if not safe_get(search_url, retries=3):
                print(f"[worker {worker_id}] Saltando query {Q_ACTUAL} por error de carga.")
                progreso['last_query_index'] = local_idx + 1
                progreso['last_query'] = Q_ACTUAL
                progreso['last_page'] = 1
                progreso['last_start'] = 0
                progreso['results_file'] = ruta_excel
                with open(ruta_progreso, 'w', encoding='utf-8') as f:
                    json.dump(progreso, f, ensure_ascii=False, indent=2)
                continue

            if detectar_captcha_simple(driver):
                esperar_resolucion_captcha(driver)

            # comportamiento optimizado para duckduckgo: cargar todos "more results" y extraer 1 vez
            while pagina_actual <= max_paginas:
                if SEARCH_ENGINE == 'duckduckgo':
                    # cargar "more" repetidamente
                    attempts_no_progress = 0  # contar intentos sin avance para salir rápido si se atasca
                    prev_count = -1           # número previo de resultados en DOM
                    stable_rounds = 0
                    MAX_STABLE_ROUNDS = 3    # si no hay cambio tras N rondas, abortar
                    MAX_TOTAL_RESULTS = 800  # cortafuegos por si la búsqueda devuelve muchísimos items

                    while pagina_actual <= max_paginas:
                        # contar resultados actuales en DOM (rápido, por JS)
                        try:
                            current_count = driver.execute_script(
                                "return document.querySelectorAll(\"article[data-testid='result'], li[data-layout='organic'], div[data-testid='result']\").length || 0;"
                            )
                        except Exception:
                            current_count = 0

                        # si ya alcanzamos un límite razonable, salimos
                        if current_count >= MAX_TOTAL_RESULTS:
                            print(f"[worker {worker_id}]  -> Límites de resultados alcanzado ({current_count}), abortando carga dinámica.")
                            break

                        # localizar botón "More results" (ir_siguiente_pagina hace un scroll corto)
                        btn_more = ir_siguiente_pagina(driver, engine='duckduckgo')
                        if not btn_more:
                            # no hay botón: salir rápido para extraer y pasar a la siguiente query
                            break

                        # obtener texto/clase del botón
                        try:
                            btn_text = (btn_more.text or "").strip().lower()
                        except Exception:
                            btn_text = ""

                        is_show_all = False
                        try:
                            if "mostrar" in btn_text or "mostrar todos" in btn_text:
                                is_show_all = True
                            else:
                                cls = (btn_more.get_attribute("class") or "")
                                if "Pd_jmhkZzftl0UtTaw0u" in cls:
                                    is_show_all = True
                        except Exception:
                            is_show_all = False

                        # Si es "Mostrar todos..." y no lo hemos clicado aún, clickarlo y continuar
                        if is_show_all:
                            if forbid_show_all:
                                # NO clicar: ocultar el botón para que no quite el filtro site: y seguir buscando more-results
                                try:
                                    driver.execute_script("arguments[0].style.display='none';", btn_more)
                                    # pequeña espera para que el DOM se estabilice
                                    time.sleep(random.uniform(0.12, 0.28))
                                except Exception:
                                    pass
                                # reiniciar contadores mínimos y continuar para localizar el botón more-results real
                                attempts_no_progress = 0
                                stable_rounds = 0
                                # seguir al siguiente intento sin clicar
                                continue
                            else:
                                if not clicked_show_all:
                                    print(f"[worker {worker_id}]  -> 'Mostrar todos los resultados' detectado — intentando click...")
                                    try:
                                        driver.execute_script("arguments[0].scrollIntoView({behavior:'auto', block:'center'});", btn_more)
                                        time.sleep(random.uniform(0.10, 0.28))
                                        try:
                                            driver.execute_script("arguments[0].click();", btn_more)
                                        except Exception:
                                            try:
                                                ActionChains(driver).move_to_element(btn_more).click(btn_more).perform()
                                            except Exception:
                                                btn_more.click()
                                        clicked_show_all = True
                                        # esperar rápida actualización del DOM tras quitar el filtro/site
                                        time.sleep(random.uniform(0.8, 1.6))
                                        # reiniciar contadores
                                        attempts_no_progress = 0
                                        prev_count = -1
                                        stable_rounds = 0
                                        # volver a iterar para que el siguiente ir_siguiente_pagina devuelva "more-results"
                                        continue
                                    except Exception as e:
                                        print(f"[worker {worker_id}]  -> fallo al clicar 'Mostrar todos...': {e}")
                                        # seguir intentando localizar "more-results" más abajo

                        # comprobación rápida: si ya clicamos show_all, intentar localizar directly el boton por id
                        if clicked_show_all:
                            try:
                                quick_more = driver.find_element(By.ID, "more-results")
                            except Exception:
                                quick_more = None
                            if quick_more and quick_more.is_displayed():
                                btn_more = quick_more

                        # intentar cerrar/ocultar overlays que puedan tapar el botón
                        overlay_selectors = [
                            "div[class*='ad']",
                            "div[class*='ads']",
                            "div[id*='ad']",
                            "div[class*='banner']",
                            "div[class*='cookie']",
                            "div[class*='consent']",
                            "div[class*='modal']",
                            "div[class*='overlay']",
                            "button[aria-label*='close']",
                            "button[title*='Close']",
                            "button[class*='close']"
                        ]
                        for sel in overlay_selectors:
                            try:
                                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                                for el in elems:
                                    try:
                                        if el.is_displayed():
                                            try:
                                                driver.execute_script("arguments[0].click();", el)
                                                time.sleep(0.06)
                                            except Exception:
                                                try:
                                                    driver.execute_script("arguments[0].style.display='none';", el)
                                                except Exception:
                                                    pass
                                    except Exception:
                                        continue
                            except Exception:
                                continue

                        # intentar localizar el botón "more-results" con waits cortos (1s)
                        try:
                            btn_more = WebDriverWait(driver, 2).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='more-results-button'], button#more-results"))
                            )
                        except Exception:
                            # fallback corto por texto
                            try:
                                btn_more = WebDriverWait(driver, 2).until(
                                    EC.element_to_be_clickable((By.XPATH,
                                        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'more results')"
                                        " or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ver más')"
                                        " or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'más resultados')"
                                        " or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more')]"
                                    ))
                                )
                            except Exception:
                                # si no hay botón clicable en tiempos cortos, aumentamos intento sin progreso
                                attempts_no_progress += 1
                                if attempts_no_progress >= 3:
                                    print(f"[worker {worker_id}]  -> Sin progreso tras {attempts_no_progress} intentos, abortando carga dinámica.")
                                    break
                                else:
                                    time.sleep(random.uniform(0.3, 0.9))
                                    continue

                        # contar antes del click
                        try:
                            before_count = driver.execute_script(
                                "return document.querySelectorAll(\"article[data-testid='result'], li[data-layout='organic'], div[data-testid='result']\").length || 0;"
                            )
                        except Exception:
                            before_count = current_count

                        # intentar click robusto en more_btn
                        clicked = False
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({behavior:'auto', block:'center'});", btn_more)
                            time.sleep(random.uniform(0.06, 0.18))
                            try:
                                driver.execute_script("arguments[0].click();", btn_more)
                                clicked = True
                            except Exception:
                                try:
                                    ActionChains(driver).move_to_element(btn_more).pause(random.uniform(0.02, 0.10)).click(btn_more).perform()
                                    clicked = True
                                except Exception:
                                    try:
                                        btn_more.click()
                                        clicked = True
                                    except Exception:
                                        clicked = False
                        except Exception:
                            try:
                                btn_more.click()
                                clicked = True
                            except Exception:
                                clicked = False

                        if not clicked:
                            print(f"[worker {worker_id}]  -> No se pudo hacer click en 'More results' — interrumpiendo carga dinámica.")
                            attempts_no_progress += 1
                            if attempts_no_progress >= 3:
                                print(f"[worker {worker_id}]  -> Abortando tras {attempts_no_progress} intentos fallidos de click.")
                                break
                            else:
                                time.sleep(random.uniform(0.3, 0.9))
                                continue

                        # esperar y comprobar si aparece contenido nuevo (polling corto)
                        new_content_seen = False
                        poll_start = time.time()
                        POLL_TIMEOUT = 2.2
                        while time.time() - poll_start < POLL_TIMEOUT:
                            try:
                                after_count = driver.execute_script(
                                    "return document.querySelectorAll(\"article[data-testid='result'], li[data-layout='organic'], div[data-testid='result']\").length || 0;"
                                )
                            except Exception:
                                after_count = before_count
                            if after_count > before_count:
                                new_content_seen = True
                                break
                            time.sleep(0.22)

                        if not new_content_seen:
                            # no hubo aumento de resultados tras click -> considerar sin progreso
                            attempts_no_progress += 1
                            stable_rounds += 1
                            print(f"[worker {worker_id}]  -> Click ok pero sin nuevo contenido (stable_rounds={stable_rounds}, attempts_no_progress={attempts_no_progress}).")
                            if stable_rounds >= MAX_STABLE_ROUNDS or attempts_no_progress >= 3:
                                print(f"[worker {worker_id}]  -> No hay nuevo contenido tras varios intentos — abortando carga dinámica.")
                                break
                            else:
                                # pequeña pausa y reintento
                                time.sleep(random.uniform(0.3, 0.9))
                                continue

                        # click produjo nuevo contenido -> resetear contadores y avanzar
                        attempts_no_progress = 0
                        stable_rounds = 0
                        pagina_actual += 1

                        # dejar un tiempo cortito para que el DOM añada resultados
                        time.sleep(random.uniform(0.45, 1.05))

                        # detectar captcha si aparece
                        if detectar_captcha_simple(driver):
                            esperar_resolucion_captcha(driver)
                    # extraer una sola vez
                    try:
                        resultados_pagina = extraer_resultados_de_serp(driver, pagina_actual, engine=SEARCH_ENGINE)
                    except Exception as e:
                        print(f"[worker {worker_id}] Error extrayendo resultados:", e)
                        resultados_pagina = []

                    if resultados_pagina:
                        for r in resultados_pagina:
                            r['criterio_busqueda'] = Q_ACTUAL
                        resultados_acumulados.extend(resultados_pagina)
                        print(f"[worker {worker_id}]  -> resultados extraídos: {len(resultados_pagina)}")
                    else:
                        print(f"[worker {worker_id}]  -> (sin resultados detectados)")

                    # guardar solo al final de la query (comportamiento requerido)
                    try:
                        df_final = pd.DataFrame(resultados_acumulados)
                        guardar_resultados_parciales(df_final, ruta_csv, ruta_excel)
                        print(f"[worker {worker_id}] Guardado final CSV para query. Total acumulado: {len(df_final)}")
                    except Exception as e:
                        print(f"[worker {worker_id}] Error guardando resultados finales:", e)

                    # actualizar progreso: marcar esta query como procesada
                    progreso['last_query_index'] = local_idx + 1
                    progreso['last_query'] = Q_ACTUAL
                    progreso['last_page'] = 1
                    progreso['last_start'] = 0
                    progreso['results_file'] = ruta_excel
                    with open(ruta_progreso, 'w', encoding='utf-8') as f:
                        json.dump(progreso, f, ensure_ascii=False, indent=2)

                    break  # pasar a siguiente query

                else:
                    # comportamiento por página (Google u otros)
                    for scroll in range(3):
                        driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {0.3 + scroll*0.2});")
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

                    try:
                        resultados_pagina = extraer_resultados_de_serp(driver, pagina_actual, engine=SEARCH_ENGINE)
                    except Exception as e:
                        print(f"[worker {worker_id}] Error extrayendo resultados:", e)
                        resultados_pagina = []

                    if resultados_pagina:
                        for r in resultados_pagina:
                            r['criterio_busqueda'] = Q_ACTUAL
                        resultados_acumulados.extend(resultados_pagina)
                        print(f"[worker {worker_id}]  -> resultados extraídos: {len(resultados_pagina)}")
                    else:
                        print(f"[worker {worker_id}]  -> (sin resultados detectados)")

                    # guardado diferido: actualizar progreso local
                    progreso['last_query_index'] = local_idx
                    progreso['last_query'] = Q_ACTUAL
                    progreso['last_page'] = pagina_actual
                    m = re.search(r'(?:start|s)=(\d+)', driver.current_url or "")
                    DEFAULT_PAGE_SIZE = 10
                    progreso['last_start'] = int(m.group(1)) if m else ((pagina_actual-1) * DEFAULT_PAGE_SIZE)
                    progreso['results_file'] = ruta_excel
                    with open(ruta_progreso, 'w', encoding='utf-8') as f:
                        json.dump(progreso, f, ensure_ascii=False, indent=2)

                    btn_next = ir_siguiente_pagina(driver, engine=SEARCH_ENGINE)
                    if not btn_next:
                        print(f"[worker {worker_id}] No hay más páginas para: {Q_ACTUAL}")
                        break

                    clicked = False
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({behavior:'auto', block:'center'});", btn_next)
                        time.sleep(random.uniform(0.15, 0.35))
                        try:
                            driver.execute_script("arguments[0].click();", btn_next)
                            clicked = True
                        except Exception:
                            try:
                                ActionChains(driver).move_to_element(btn_next).pause(random.uniform(0.05, 0.15)).click(btn_next).perform()
                                clicked = True
                            except Exception:
                                try:
                                    btn_next.click()
                                    clicked = True
                                except Exception:
                                    clicked = False
                    except Exception:
                        try:
                            btn_next.click()
                            clicked = True
                        except Exception:
                            clicked = False

                    if not clicked:
                        print(f"[worker {worker_id}] No se pudo hacer click en siguiente – finalizando query.")
                        break

                    pagina_actual += 1
                    time.sleep(random.uniform(MIN_DELAY_BETWEEN_PAGES, MAX_DELAY_BETWEEN_PAGES))

            # fin de una query: seguimos al siguiente (el guardado ya se hizo dentro del flujo)
            # pequeño sleep entre queries para evitar bursts
            time.sleep(random.uniform(4.37, 7.23))

        # finalizar worker
        print(f"[worker {worker_id}] FIN de slice. Total resultados acumulados (memoria): {len(resultados_acumulados)}")


    except Exception:
        with open(ruta_log_error, 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())
        print(f"[worker {worker_id}] ERROR FATAL — ver {ruta_log_error}")
        traceback.print_exc()
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ----------------- función que inicia los procesos -----------------

def start_workers(num_workers=4):
    # dividir queries_total en N slices (reparto por rebanadas round-robin)
    slices = [[] for _ in range(num_workers)]
    for i, q in enumerate(queries_total):
        slices[i % num_workers].append(q)

    procs = []
    for i in range(num_workers):
        p = Process(target=worker_main, args=(i+1, slices[i]), daemon=False)
        p.start()
        procs.append(p)
        print(f"[main] Worker {i+1} iniciado con {len(slices[i])} queries.")

    for p in procs:
        p.join()
    print("[main] Todos los workers han terminado.")

# ----------------- ejecutable -----------------

if __name__ == "__main__":
    if USE_MULTIPLE_BROWSERS and NUM_BROWSERS > 1:
        print(f"Iniciando modo MULTI-BROWSER con {NUM_BROWSERS} procesos.")
        start_workers(NUM_BROWSERS)
    else:
        print("USE_MULTIPLE_BROWSERS=False o NUM_BROWSERS<=1 -> correría un solo worker (no implementado aquí).")