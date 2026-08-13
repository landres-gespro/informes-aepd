import os
import sys
import time
import pandas as pd
from groq import Groq
import json
from pydantic import BaseModel, Field, ValidationError

CSV_FILE = "data/resultados.csv"
BATCH_SIZE = 25 

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class AnalisisResolucion(BaseModel):
    tematica: str = Field(description="Ámbito del informe (ej. Videovigilancia, Historias clínicas, Cesiones de datos, Seguridad, Transparencia...)")
    resumen_ejecutivo: str = Field(description="Resumen DETALLADO de 4-6 frases: quién consulta, qué se pregunta y qué responde el Gabinete Jurídico.")
    hechos_principales: list[str] = Field(description="Lista de 3 a 5 puntos clave del contexto de la consulta.")
    resolucion_final: str = Field(description="Conclusión jurídica principal del informe (la respuesta del Gabinete Jurídico).")
    normativas_infringidas: list[str] = Field(description="Normas o artículos analizados/citados (LOPD, RGPD, LOPDGDD, leyes sectoriales...).")
    palabras_clave: list[str] = Field(description="5-8 palabras o conceptos cortos que definan el informe.")
    
def analyze_text(texto):
    if not texto or "Error" in str(texto):
        return None
        
    texto_input = str(texto)[:6000]
    
prompt = f"""Eres un asistente legal experto en dictámenes del Gabinete Jurídico de la AEPD.
El texto que recibirás es una CONSULTA jurídica (no una sanción): alguien pregunta y el Gabinete responde.
DEBES devolver EXCLUSIVAMENTE un objeto JSON con EXACTAMENTE estas 6 claves:
"tematica", "resumen_ejecutivo", "hechos_principales", "resolucion_final", "normativas_infringidas", "palabras_clave".
Si no encuentras información para una clave, usa el string "No especificado" o una lista vacía [].

EJEMPLO DE RESPUESTA OBLIGATORIA:
{{
  "tematica": "Imágenes en centros sanitarios",
  "resumen_ejecutivo": "Un centro hospitalario consulta si las imágenes tomadas a pacientes forman parte de su historia clínica. El Gabinete Jurídico analiza la finalidad con la que se obtienen las imágenes. Concluye que solo integran la historia clínica si su fin es asistencial, no si se usan para seguridad.",
  "hechos_principales": ["Consulta de un centro sanitario", "Imágenes de pacientes", "Duda sobre su régimen jurídico"],
  "resolucion_final": "Las imágenes solo son historia clínica si se obtienen con finalidad asistencial; si es de seguridad, no.",
  "normativas_infringidas": ["Ley Orgánica 15/1999", "Art. 20 LOPD", "RD 1720/2007"],
  "palabras_clave": ["historia clínica", "imágenes médicas", "centro sanitario", "datos de salud", "videovigilancia"]
}}

TEXTO A ANALIZAR:
{texto_input}
"""
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Eres un asistente legal. Devuelve SOLO un JSON válido, sin texto adicional, sin markdown, sin explicaciones."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        response_json = chat_completion.choices[0].message.content
        
        if response_json.startswith("```json"):
            response_json = response_json[7:-3].strip()
            
        data = json.loads(response_json)
        valid_data = AnalisisResolucion(**data)
        return valid_data.model_dump()
        
    except ValidationError:
        print(f"   ⚠️ Error de formato: La IA intentó inventarse claves nuevas.")
        return None
    except Exception as e:
        if "429" in str(e):
            print("   🛑 LÍMITE DIARIO DE GROQ ALCANZADO. Deteniendo el lote de hoy.")
            return "RATE_LIMIT"
        print(f"   ❌ Error inesperado: {e}")
        return None

def main():
    if not os.path.exists(CSV_FILE):
        print("No hay CSV para analizar.")
        return

    print("🤖 Cargando base de datos...")
    df = pd.read_csv(CSV_FILE)
    
    new_cols = ['Tematica_IA', 'Resumen_IA', 'Hechos_IA', 'Resolucion_IA', 'Normativa_IA', 'PalabrasClave_IA']
    for col in new_cols:
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].fillna("").astype(str)
            
    # Pendientes = vacías, con error previo, o SIN palabras clave (re-análisis con esquema nuevo)
    mask = (df['Tematica_IA'] == "") | (df['Tematica_IA'] == "Error de procesamiento") | (df['PalabrasClave_IA'] == "")
    rows_to_process = df[mask]
    
    total_pending = len(rows_to_process)
    print(f"📊 Total de resoluciones pendientes: {total_pending}")
    
    if total_pending == 0:
        print("✅ Todo está analizado.")
        return

    limit = min(BATCH_SIZE, total_pending)
    print(f"🚀 Procesando lote de {limit} resoluciones...")
    
    processed_count = 0
    
    for index, row in rows_to_process.head(limit).iterrows():
        titulo = row['Titulo']
        print(f"🧠 [{processed_count + 1}/{limit}] Analizando: {titulo}...")
        
        analisis = analyze_text(row['Texto_Completo'])
        
        if analisis == "RATE_LIMIT":
            print("🛑 Guardando progreso y deteniendo la ejecución hasta mañana.")
            break
            
        if analisis:
            df.loc[index, 'Tematica_IA'] = analisis['tematica']
            df.loc[index, 'Resumen_IA'] = analisis['resumen_ejecutivo']
            df.loc[index, 'Hechos_IA'] = " | ".join(analisis['hechos_principales'])
            df.loc[index, 'Resolucion_IA'] = analisis['resolucion_final']
            df.loc[index, 'Normativa_IA'] = ", ".join(analisis['normativas_infringidas'])
            df.loc[index, 'PalabrasClave_IA'] = ", ".join(analisis['palabras_clave'])
            print(f"   ✅ Éxito: '{analisis['tematica']}' | {len(analisis['palabras_clave'])} palabras clave")
            processed_count += 1
        else:
            df.loc[index, 'Tematica_IA'] = "Error de procesamiento"
            processed_count += 1
            
        time.sleep(2) 
            
    print(f"💾 Guardando {processed_count} nuevos análisis en el CSV...")
    df.to_csv(CSV_FILE, index=False, encoding='utf-8')
    
    remaining = total_pending - processed_count
    print(f"✅ Lote completado. Quedan {remaining} pendientes.")

if __name__ == "__main__":
    main()
