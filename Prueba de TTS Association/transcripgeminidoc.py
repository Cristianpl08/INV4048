import google.generativeai as genai
import os
from docx import Document
from docx.shared import Pt
import re

# Configuración de la API Key
API_KEY = "YOUR_GOOGLE_API_KEY"  # Reemplaza con tu API key de Google
genai.configure(api_key=API_KEY)

# Variables de archivos
AUDIO_FILE = "PG10569C.mp3"
OUTPUT_FILE = "diarization/PG10569C.docx"

def extract_dialogues_only(text):
    """
    Extrae solo los diálogos del texto, eliminando timestamps, speakers y descripciones
    """
    lines = text.split('\n')
    dialogues = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Eliminar líneas que son solo descripciones entre paréntesis
        if line.startswith('(') and line.endswith(')'):
            continue
        
        # Eliminar timestamps y speakers del formato [Speaker X] (timestamp): texto
        # Patrón para eliminar [Speaker X] y (timestamp):
        line = re.sub(r'\[Speaker \d+\]\s*', '', line)
        line = re.sub(r'\(\d+:\d+\)\s*', '', line)
        line = re.sub(r'\(\d+:\d+:\d+\)\s*', '', line)
        
        # Eliminar descripciones entre paréntesis al inicio
        line = re.sub(r'^\([^)]+\)\s*', '', line)
        
        # Eliminar dos puntos al inicio si quedan
        line = re.sub(r'^:\s*', '', line)
        
        line = line.strip()
        
        # Solo agregar si la línea contiene texto real (no solo números o símbolos)
        if line and len(line) > 2 and not re.match(r'^[\d\s:\[\]()]+$', line):
            dialogues.append(line)
    
    return '\n\n'.join(dialogues)

def save_to_docx(text, output_path):
    """
    Guarda el texto en un archivo DOCX con formato apropiado
    """
    doc = Document()
    
    # Configurar el estilo del párrafo
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    
    # Dividir el texto en párrafos y agregarlos
    paragraphs = text.split('\n\n')
    
    for para_text in paragraphs:
        if para_text.strip():
            para = doc.add_paragraph(para_text.strip())
            para.paragraph_format.space_after = Pt(6)
    
    doc.save(output_path)

def transcribe_audio_with_diarization(audio_path, output_path):
    """
    Transcribe audio y extrae solo los diálogos usando Gemini
    """
    try:
        # Usar gemini-2.5-flash o gemini-2.5-pro (modelos actuales)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Cargar el archivo de audio
        audio_file = genai.upload_file(path=audio_path)
        
        # Prompt para transcripción solo con diálogos
        prompt = """
        Por favor, transcribe este archivo de audio extrayendo SOLO los diálogos hablados.
        
        Especificaciones:
        1. NO incluyas timestamps
        2. NO incluyas etiquetas de speaker (Speaker 1, Speaker 2, etc.)
        3. NO incluyas descripciones de sonidos o música entre paréntesis
        4. Solo transcribe los diálogos y conversaciones
        5. Mantén la puntuación y formato apropiados
        6. Separa cada intervención en un párrafo nuevo
        
        Transcribe el audio completo con precisión, extrayendo únicamente los diálogos.
        """
        
        # Generar la transcripción
        print("Procesando transcripción...")
        response = model.generate_content([prompt, audio_file])
        
        # Extraer solo los diálogos
        dialogues_text = extract_dialogues_only(response.text)
        
        # Guardar en formato DOCX
        save_to_docx(dialogues_text, output_path)
        
        print(f"✓ Transcripción completada y guardada en: {output_path}")
        print("\n--- Vista previa de la transcripción ---")
        print(dialogues_text[:500] + "...\n")
        
        return dialogues_text
        
    except Exception as e:
        print(f"✗ Error durante la transcripción: {str(e)}")
        return None

# Ejecutar la transcripción
if __name__ == "__main__":
    # Crear directorio de salida si no existe
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    print("Iniciando transcripción de audio con Gemini...")
    print(f"Archivo de entrada: {AUDIO_FILE}")
    print(f"Archivo de salida: {OUTPUT_FILE}\n")
    
    result = transcribe_audio_with_diarization(AUDIO_FILE, OUTPUT_FILE)
    
    if result:
        print("✓ Proceso completado exitosamente")
    else:
        print("✗ El proceso falló")