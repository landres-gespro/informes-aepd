import os
import sys
import csv
import requests
import pymupdf
from datetime import datetime, timedelta

DATA_FILE = "data/resultados.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def get_processed_ids():
    """Lee el CSV y devuelve los IDs ya procesados."""
    processed = set()
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                titulo = row.get('Titulo', '')
                if titulo:
                    processed.add(titulo.replace('.pdf', '').lower())
    return processed

def download_pdf_text(url):
    """Descarga el PDF y extrae el texto."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        if response.content[:4] != b"%PDF":
            return None
        doc = pymupdf.open(stream=response.content, filetype="pdf")
        text = "".join([page.get_text() for page in doc])
        return text.replace('\n', ' ').replace('\r', ' ').strip()
    except Exception:
        return None

def generate_recent_ids():
    """Genera IDs de informes recientes (últimos 2 años) basándose en patrones."""
    ids = []
    current_year = datetime.now().year
    
    # Generar IDs para el año actual y el anterior
    for year in [current_year, current_year - 1]:
        for num in range(1, 200):  # Hasta 200 informes por año (margen amplio)
            ids.append(f"{year}-{num:04d}")
    
    return ids

def main():
    print("🤖 Buscando informes recientes...")
    
    # Generar IDs candidatos (2024, 2025, 2026)
    candidate_ids = generate_recent_ids()
    print(f"📋 Generados {len(candidate_ids)} IDs candidatos")
    
    # Filtrar los que ya tenemos
    processed_ids = get_processed_ids()
    new_ids = [id for id in candidate_ids if id.lower() not in processed_ids]
    
    if not new_ids:
        print("✅ No hay informes nuevos que procesar.")
        sys.exit(0)
    
    print(f"🚀 Probando {len(new_ids)} IDs nuevos...")
    
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    file_exists = os.path.isfile(DATA_FILE)
    
    found_count = 0
    batch_size = 50  # Probar hasta 50 IDs por ejecución
    
    with open(DATA_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Titulo", "Link_PDF", "Resumen_AEPD", "Texto_Completo"])
        
        for informe_id in new_ids[:batch_size]:
            url = f"https://www.aepd.es/documento/{informe_id}.pdf"
            print(f"📄 Probando {informe_id}...", end=" ")
            
            texto = download_pdf_text(url)
            
            if texto:
                writer.writerow([informe_id, url, f"Informe jurídico {informe_id}", texto[:3000] + "..."])
                print("✅ OK")
                found_count += 1
            else:
                print("❌ No existe")
    
    print(f"✅ Ciclo completado. Encontrados {found_count} informes nuevos.")

if __name__ == "__main__":
    main()
