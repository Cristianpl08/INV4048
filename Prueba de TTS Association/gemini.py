import google.generativeai as genai
import os
import re

# Configuración de la API Key
API_KEY = "YOUR_GOOGLE_API_KEY"  # Reemplaza con tu API key de Google
genai.configure(api_key=API_KEY)

# Variables de archivos
AUDIO_FILE = "PG10644C.mp3"
OUTPUT_FILE = "diarization_sin/PG10644C2.txt"

def clean_transcript(text):
    """
    Limpia el texto eliminando timestamps y etiquetas de speakers
    """
    # Eliminar timestamps en formato [HH:MM:SS] o (HH:MM:SS) o similares
    text = re.sub(r'\[?\d{1,2}:\d{2}(?::\d{2})?\]?', '', text)
    text = re.sub(r'\(?\d{1,2}:\d{2}(?::\d{2})?\)?', '', text)
    
    # Eliminar etiquetas de speakers como [Speaker X], Speaker X:, etc.
    text = re.sub(r'\[?Speaker\s+\d+\]?:?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[?Hablante\s+\d+\]?:?', '', text, flags=re.IGNORECASE)
    
    # Limpiar espacios múltiples y saltos de línea excesivos
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    
    return text.strip()

def transcribe_audio_with_diarization(audio_path, output_path):
    """
    Transcribe audio y devuelve solo el diálogo sin timestamps ni speakers
    """
    try:
        # Usar gemini-2.5-flash o gemini-2.5-pro (modelos actuales)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Cargar el archivo de audio
        audio_file = genai.upload_file(path=audio_path)
        
        # Prompt para transcripción solo con diálogo
        prompt = """
        Por favor, transcribe este archivo de audio con las siguientes especificaciones:
        
        1. Transcribe SOLO el diálogo, sin identificar hablantes
        2. NO incluyas timestamps
        3. NO incluyas etiquetas de speakers
        4. Solo proporciona el texto transcrito del diálogo
        5. Mantén la puntuación y formato apropiados
        6. Separa los turnos de conversación con saltos de línea cuando sea natural
        7. IMPORTANTE: NO alucines, NO inventes, NO agregues información que no esté en el audio
        8. Transcribe EXACTAMENTE lo que escuchas, sin inferir, suponer o completar frases
        9. Si no puedes entender algo claramente, indica [inaudible] en lugar de inventar palabras
        
        Transcribe el audio completo con precisión, solo el diálogo sin información adicional. Sé fiel al audio original.
        """
        
        # Generar la transcripción
        print("Procesando transcripción...")
        response = model.generate_content([prompt, audio_file])
        
        # Limpiar el texto para eliminar timestamps y speakers
        cleaned_text = clean_transcript(response.text)
        
        # Guardar la transcripción limpia en el archivo de salida
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_text)
        
        print(f"✓ Transcripción completada y guardada en: {output_path}")
        print("\n--- Vista previa de la transcripción ---")
        print(cleaned_text[:500] + "...\n")
        
        return cleaned_text
        
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