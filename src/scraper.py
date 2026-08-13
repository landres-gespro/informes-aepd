import os
import sys
import csv
import requests
import pymupdf

INDEX_FILE = "data/informes/index.csv"
DATA_FILE = "data/resultados.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_processed_ids():
    """Lee el CSV y devuelve los IDs de informes ya procesados."""
    processed = set()
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                titulo = row.get('Titulo', '')
                if titulo:
                    # El ID es el nombre del archivo sin .pdf
                    processed.add(titulo.replace('.pdf', '').lower())
    return processed

def download_pdf_text(url):
    """Descarga el PDF en memoria y extrae todo el texto."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        if response.content[:4] != b"%PDF":
            return f"Error: no es un PDF válido"
        doc = pymupdf.open(stream=response.content, filetype="pdf")
        text = "".join([page.get_text() for page in doc])
        return text.replace('\n', ' ').replace('\r', ' ').strip()
    except Exception as e:
        return f"Error extrayendo PDF: {e}"

def main():
    print("🤖 Buscando informes recientes en el censo histórico...")
    
    if not os.path.exists(INDEX_FILE):
        print("⚠️ No existe el censo histórico. Ejecuta primero el paso 4b.")
        sys.exit(0)
    
    # Cargar el censo
    with open(INDEX_FILE, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        all_informes = list(reader)
    
    if not all_informes:
        print("⚠️ El censo está vacío.")
        sys.exit(0)
    
    # Ordenar por año descendente (más recientes primero) y luego por ID descendente
    all_informes.sort(key=lambda x: (int(x['year']) if x['year'] != '9999' else 0, x['id']), reverse=True)
    
    print(f"📚 Censo contiene {len(all_informes)} informes.")
    
    # Comprobar qué tenemos ya
    processed_ids = get_processed_ids()
    new_informes = [inf for inf in all_informes if inf['id'].lower() not in processed_ids]
    
    if not new_informes:
        print("✅ No hay informes nuevos que no tengamos ya en nuestra base de datos.")
        sys.exit(0)
    
    # Procesar los 10 más recientes (para no saturar en una sola ejecución)
    batch_size = 10
    batch = new_informes[:batch_size]
    
    print(f"🚀 Procesando {len(batch)} informes recientes (de {len(new_informes)} pendientes)...")
    
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    file_exists = os.path.isfile(DATA_FILE)
    
    with open(DATA_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Titulo", "Link_PDF", "Resumen_AEPD", "Texto_Completo"])
        
        for inf in batch:
            titulo = inf['id']
            # Intentar primero la URL viva, luego Wayback
            url_live = inf['url_live']
            url_wayback = inf['url_wayback']
            
            print(f"📄 Procesando {titulo} (año {inf['year']})...")
            
            # Intento 1: URL oficial
            texto = download_pdf_text(url_live)
            link_usado = url_live
            
            # Intento 2: Wayback si falló
            if texto.startswith("Error"):
                print(f"   ⚠️ URL oficial falló, intentando Wayback...")
                texto = download_pdf_text(url_wayback)
                link_usado = url_wayback
            
            if texto.startswith("Error"):
                print(f"   ❌ No se pudo extraer texto de {titulo}")
                continue
            
            # Guardar (limitamos a 3000 caracteres)
            writer.writerow([titulo, link_usado, f"Informe jurídico {titulo}", texto[:3000] + "..."])
            print(f"   💾 Guardado en la base de datos.")
    
    remaining = len(new_informes) - len(batch)
    print(f"✅ Ciclo completado. Quedan {remaining} informes pendientes para próximas ejecuciones.")

if __name__ == "__main__":
    main()
