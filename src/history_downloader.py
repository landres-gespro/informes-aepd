import os
import csv
import time
import requests
import pymupdf

INDEX_FILE = "data/informes/index.csv"
HISTORY_DIR = "data/informes"
FAILS_FILE = "data/informes/fallos.csv"
BATCH_SIZE = 60  # Informes históricos por noche

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def load_index():
    if not os.path.exists(INDEX_FILE):
        return []
    with open(INDEX_FILE, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def dedupe_index(index):
    """Una sola entrada por ID de resolución."""
    seen = {}
    for e in index:
        if e["id"] not in seen:
            seen[e["id"]] = e
    return list(seen.values())

def load_processed():
    processed = set()
    if not os.path.exists(HISTORY_DIR):
        return processed
    for fname in os.listdir(HISTORY_DIR):
        if fname.startswith("textos_") and fname.endswith(".csv"):
            with open(os.path.join(HISTORY_DIR, fname), encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    processed.add(row["id"])
    return processed

def dedupe_textos():
    """Autocuración: elimina duplicados ya escritos en los CSVs por año."""
    if not os.path.exists(HISTORY_DIR):
        return
    for fname in os.listdir(HISTORY_DIR):
        if fname.startswith("textos_") and fname.endswith(".csv"):
            path = os.path.join(HISTORY_DIR, fname)
            with open(path, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            unique = {}
            for r in rows:
                if r["id"] not in unique:
                    unique[r["id"]] = r
            if len(unique) != len(rows):
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=["id", "year", "url_live", "url_wayback", "texto"])
                    w.writeheader()
                    w.writerows(unique.values())
                print(f"🧹 Limpieza de duplicados en {fname}: {len(rows)} -> {len(unique)}")

def load_fails():
    fails = {}
    if os.path.exists(FAILS_FILE):
        with open(FAILS_FILE, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fails[row["id"]] = int(row["intentos"])
    return fails

def save_fails(fails):
    with open(FAILS_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "intentos"])
        w.writeheader()
        for k, v in fails.items():
            w.writerow({"id": k, "intentos": v})

def download_pdf(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        if r.content[:4] != b"%PDF":
            return None
        return r.content
    except Exception:
        return None

def extract_text(pdf_bytes):
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        text = "".join(p.get_text() for p in doc)
        return text.replace("\n", " ").replace("\r", " ").strip()
    except Exception:
        return ""

def append_row(year, row):
    path = os.path.join(HISTORY_DIR, f"textos_{year}.csv")
    exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "year", "url_live", "url_wayback", "texto"])
        if not exists:
            w.writeheader()
        w.writerow(row)

def main():
    index = dedupe_index(load_index())
    if not index:
        print("❌ No hay censo histórico.")
        return

    os.makedirs(HISTORY_DIR, exist_ok=True)
    dedupe_textos()
    processed = load_processed()
    fails = load_fails()

    pending = [e for e in index
               if e["id"] not in processed and fails.get(e["id"], 0) < 3]

    print(f"📚 Censo único: {len(index)} | Procesadas: {len(processed)} | Pendientes: {len(pending)}")
    if not pending:
        print("✅ Histórico completo. ¡Misión cumplida!")
        return

    batch = pending[:BATCH_SIZE]
    ok = fail = 0
    done_this_run = set()

    for i, e in enumerate(batch, 1):
        eid = e["id"]
        if eid in done_this_run:
            continue
        print(f"⬇️ [{i}/{len(batch)}] {eid} (año {e['year']})...", end=" ", flush=True)

        pdf = download_pdf(e["url_live"])
        fuente = "AEPD"
        if not pdf:
            time.sleep(1)
            pdf = download_pdf(e["url_wayback"])
            fuente = "Wayback"

        if not pdf:
            fails[eid] = fails.get(eid, 0) + 1
            print(f"❌ sin PDF (intento {fails[eid]}/3)")
            fail += 1
            time.sleep(1)
            continue

        text = extract_text(pdf)
        if len(text) < 200:
            fails[eid] = fails.get(eid, 0) + 1
            print(f"⚠️ texto corto (intento {fails[eid]}/3)")
            fail += 1
            time.sleep(1)
            continue

        append_row(e["year"], {
            "id": eid,
            "year": e["year"],
            "url_live": e["url_live"],
            "url_wayback": e["url_wayback"],
            "texto": text[:3000],
        })
        done_this_run.add(eid)
        ok += 1
        print(f"✅ OK ({fuente}, {len(text)} chars)")
        time.sleep(2)

    save_fails(fails)
    print(f"📊 Resumen de la noche: {ok} OK, {fail} fallos")
    print(f"🎯 Progreso total del histórico: {len(processed) + ok} / {len(index)}")

if __name__ == "__main__":
    main()
