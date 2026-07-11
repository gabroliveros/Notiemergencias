import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
params = {"q": 'venezuela "El Nacional" lluvia inundacion'}

r = requests.post("https://html.duckduckgo.com/html/", data=params, headers=headers, timeout=15)
# print(r.status_code)
# print(r.text[:6000])


# import re

# idx = r.text.find('id="links"')
# print(r.text[idx:idx+4000] if idx != -1 else "No se encontró el contenedor de resultados")

idx = r.text.find('result__snippet')
print(r.text[idx-800:idx+1500])