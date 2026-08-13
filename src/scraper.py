import os
import sys
import csv
import feedparser
import requests
import pymupdf

RSS_URL = "https://www.aepd.es/informes-y-resoluciones/informes-juridicos/feed.xml"
DATA_FILE = "data/resultados.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_processed_links():
    """Lee el CSV y devuelve una lista de enlaces de PDFs que ya hemos procesado."""
    processed = set()
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                processed.add(row.get('Link_PDF', ''))
    return processed

def download_pdf_text(url):
    """Descarga el PDF en memoria y extrae todo el texto."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        doc = pymupdf.open(stream=response.content, filetype="pdf")
        text = "".join([page.get_text() for page in doc])
        # Limpiamos saltos de línea para que no rompan el CSV
        return text.replace('\n', ' ').replace('\r', ' ').strip()
    except Exception as e:
        return f"Error extrayendo PDF: {e}"

def main():
    print("🤖 Conectando al canal RSS oficial de la AEPD...")
    # feedparser maneja automáticamente la decodificación y estructura del XML
    feed = feedparser.parse(RSS_URL)
    
    if not feed.entries:
        print("⚠️ No se pudieron leer entradas del RSS.")
        sys.exit(0)
        
    print(f"📡 Encontradas {len(feed.entries)} resoluciones recientes en el RSS.")
    
    # Comprobamos qué tenemos ya para no descargar lo mismo dos veces
    processed_links = get_processed_links()
    new_entries = [entry for entry in feed.entries if entry.link not in processed_links]
    
    if not new_entries:
        print("✅ No hay resoluciones nuevas que no tengamos ya en nuestra base de datos.")
        sys.exit(0)
        
    print(f"🚀 Procesando {len(new_entries)} resoluciones NUEVAS...")
    
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    file_exists = os.path.isfile(DATA_FILE)
    
    with open(DATA_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Titulo", "Link_PDF", "Resumen_AEPD", "Texto_Completo"])
            
        for entry in new_entries:
            titulo = entry.get('title', 'Sin Titulo')
            link = entry.get('link', '')
            resumen = entry.get('summary', '').replace('\n', ' ').replace('\r', ' ')
            
            print(f"📄 Procesando {titulo}...")
            texto = download_pdf_text(link)
            
            # Guardamos el texto. Limitamos a 3000 caracteres para que el archivo en GitHub no crezca demasiado rápido
            # (En el futuro, la IA usará este texto para generar el resumen estructurado)
            writer.writerow([titulo, link, resumen, texto[:3000] + "..."])
            print(f"💾 Guardado en la base de datos.")
            
    print("✅ Ciclo completado con éxito.")

if __name__ == "__main__":
    main()
