import google.generativeai as genai
import os

# Configuración de la API Key
API_KEY = "YOUR_GOOGLE_API_KEY"  # Reemplaza con tu API key de Google
genai.configure(api_key=API_KEY)

# Variables de archivos
AUDIO_FILE = "PG10644C.mp3"
OUTPUT_FILE = "diarization/PG10644C.txt"

def transcribe_audio_with_diarization(audio_path, output_path):
    """
    Transcribe audio con diarización de hablantes usando Gemini
    """
    try:
        # Usar gemini-2.5-flash o gemini-2.5-pro (modelos actuales)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Cargar el archivo de audio
        audio_file = genai.upload_file(path=audio_path)
        
        # Prompt para transcripción con diarización
        prompt = """
        Por favor, transcribe este archivo de audio con las siguientes especificaciones:
        
        1. Identifica y etiqueta a cada hablante (Speaker 1, Speaker 2, etc.)
        2. Incluye timestamps cuando sea posible
        3. Formatea la transcripción de la siguiente manera:
           [Speaker X] (timestamp): texto transcrito
        4. Proporciona un resumen breve al final
        5. Mantén la puntuación y formato apropiados
        6. IMPORTANTE: NO alucines, NO inventes, NO agregues información que no esté en el audio
        7. Transcribe EXACTAMENTE lo que escuchas, sin inferir, suponer o completar frases
        8. Si no puedes entender algo claramente, indica [inaudible] en lugar de inventar palabras
        
        Transcribe el audio completo con precisión. Sé fiel al audio original.
        """
        
        # Generar la transcripción
        print("Procesando transcripción...")
        response = model.generate_content([prompt, audio_file])
        
        # Guardar la transcripción en el archivo de salida
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        print(f"✓ Transcripción completada y guardada en: {output_path}")
        print("\n--- Vista previa de la transcripción ---")
        print(response.text[:500] + "...\n")
        
        return response.text
        
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