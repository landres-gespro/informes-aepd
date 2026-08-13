import os
import re
import csv
import time
import requests
from collections import Counter

CDX_URL = "https://web.archive.org/cdx/search/cdx"
INDEX_FILE = "data/history/index.csv"

def cdx_query(params):
    try:
        r = requests.get(CDX_URL, params=params, timeout=600)
        r.raise_for_status()
        rows = r.json()
        if rows and rows[0] == ["original", "timestamp"]:
            rows = rows[1:]
        return rows
    except Exception as e:
        print(f"⚠️ Consulta fallida: {e}")
        return []

def main():
    # Si el censo ya existe Y tiene datos, no lo volvemos a descargar
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, encoding="utf-8") as f:
            n = sum(1 for _ in f) - 1
        if n > 0:
            print(f"📚 El censo histórico ya existe ({n} resoluciones). Saltando descarga.")
            return
        else:
            print("📚 El censo existe pero está vacío. Volviendo a consultar...")

    print("🌍 Consultando el archivo histórico de Wayback Machine (gratis)...")

    base = {
        "output": "json",
        "fl": "original,timestamp",
        "collapse": "urlkey",
        "filter": "statuscode:200",
    }

        rows = []
    # Intentos 1 y 2: carpeta de informes, con y sin www
    for host in ["www.aepd.es/informe/*.pdf", "aepd.es/informe/*.pdf"]:
        p = dict(base)
        p["url"] = host
        got = cdx_query(p)
        print(f"🔎 Consulta '{host}': {len(got)} URLs.")
        rows += got
        time.sleep(2)

    # Intento 3 (respaldo): todo el dominio, filtrando por patrón AÑO-NUMERO.pdf
    if not rows:
        p = dict(base)
        p["url"] = "aepd.es"
        p["matchType"] = "domain"
        p["filter"] = r"original:.*/\d{4}-\d{3,4}\.pdf"
        got = cdx_query(p)
        print(f"🔎 Consulta de dominio completo: {len(got)} URLs.")
        rows += got

    if not rows:
        print("❌ Wayback no devolvió nada con ningún método. Lo revisaremos juntos.")
        return

    print(f"🔎 Total bruto: {len(rows)} capturas únicas.")
    print("📋 Primeras 3 URLs de muestra:")
    for r0 in rows[:3]:
        print("   ", r0)

    # Deduplicar y extraer el año del nombre del archivo (ej. ps-00415-2024.pdf)
    seen = {}
    for original, timestamp in rows:
        original = original.strip()
        if not original.lower().endswith(".pdf"):
            continue
        filename = original.rstrip("/").split("/")[-1].lower()
        # SOLO nombres con formato de informe: AÑO-NÚMERO.pdf (ej. 2016-0302.pdf)
        if not re.match(r"^\d{4}-\d{3,4}\.pdf$", filename):
            continue
        # El año de un informe está AL PRINCIPIO del nombre
        m = re.match(r"^(\d{4})-", filename)
        year = int(m.group(1)) if m else 0
        if year and (year < 2016 or year > 2100):
            continue  # Solo nos interesa 2016 en adelante
        # Deduplicamos por NOMBRE de archivo (ID del informe), no por URL completa
        key = filename
        if key not in seen or timestamp > seen[key][0]:
            seen[key] = (timestamp, original, year)

    entries = []
    for timestamp, original, year in seen.values():
        filename = original.rstrip("/").split("/")[-1]
        entries.append({
            "id": filename[:-4],
            "year": year if year else 9999,
            "url_live": original,
            "url_wayback": f"https://web.archive.org/web/{timestamp}id_/{original}",
        })

    entries.sort(key=lambda e: (e["year"], e["id"]))

    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "year", "url_live", "url_wayback"])
        w.writeheader()
        w.writerows(entries)

    c = Counter(e["year"] for e in entries)
    print(f"✅ Censo guardado: {len(entries)} resoluciones únicas (2016 en adelante).")
    for y in sorted(c):
        print(f"   Año {y}: {c[y]} resoluciones")

if __name__ == "__main__":
    main()
