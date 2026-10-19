import cv2
import os
import json
import datetime
import requests
from PIL import Image
from Katna.video import Video
from Katna.writer import KeyFrameDiskWriter
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
import base64
from openai import OpenAI

# Configure Grok
GROK_API_KEY = "YOUR_XAI_API_KEY"
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

def call_grok_api(messages, temperature=0):
    client = OpenAI(
        api_key=GROK_API_KEY,
        base_url="https://api.x.ai/v1",
    )
    
    try:
        completion = client.chat.completions.create(
            model="grok-2-vision-latest",
            messages=messages,
            temperature=temperature,
            stream=False
        )
        
        return {
            "choices": [{"message": {"content": completion.choices[0].message.content}}],
            "usage": completion.usage
        }
            
    except Exception as e:
        print(f"Error al hacer la llamada a la API: {str(e)}")
        return None

def detect_scene_changes(video_path, scene_output_folder="scenes"):
    # Crear carpeta de salida si no existe
    os.makedirs(scene_output_folder, exist_ok=True)
    
    # Crear el VideoManager y SceneManager
    video_manager = VideoManager([video_path])
    scene_manager = SceneManager()
    
    # Agregar el detector de cambios de escena
    scene_manager.add_detector(ContentDetector(threshold=27))
    
    # Iniciar el procesamiento del video
    video_manager.start()
    scene_manager.detect_scenes(frame_source=video_manager)

    # Obtener la lista de escenas detectadas
    scene_list = scene_manager.get_scene_list()

    # Calcular la duración de cada escena
    scene_data = []
    for idx, scene in enumerate(scene_list):
        start_time = scene[0].get_seconds()
        # Para la última escena, usar la duración del video
        if idx < len(scene_list) - 1:
            end_time = scene_list[idx + 1][0].get_seconds()
        else:
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            end_time = total_frames / fps
            cap.release()
        
        duration = end_time - start_time
        scene_data.append({
            "scene_number": idx + 1,
            "timestamp": start_time,
            "timestamp_formatted": str(datetime.timedelta(seconds=int(start_time))),
            "duration": duration
        })

    # Crear diccionario para el JSON
    scenes_data = {
        "video_path": video_path,
        "total_scenes": len(scene_data),
        "scene_changes": scene_data
    }
    
    # Guardar el JSON
    json_path = os.path.join(scene_output_folder, "scene_changes.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(scenes_data, f, indent=4)
    
    # Guardar las imágenes clave de cada escena
    cap = cv2.VideoCapture(video_path)
    for idx, scene_time in enumerate(scene_data):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(scene_time["timestamp"] * cap.get(cv2.CAP_PROP_FPS)))
        ret, frame = cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_path = os.path.join(scene_output_folder, f"scene_{scene_time['scene_number']}_frame.jpg")
            Image.fromarray(frame_rgb).save(frame_path, format="JPEG", quality=95)
    
    cap.release()
    return scene_data

def extract_keyframes(video_path, output_folder, start_time=None, end_time=None):
    os.makedirs(output_folder, exist_ok=True)
    
    # Limpiar archivos temporales anteriores
    for f in os.listdir(output_folder):
        if f.startswith('temp_segment_') or f.startswith('temp_segment.'):
            try:
                os.remove(os.path.join(output_folder, f))
            except:
                pass

    # 1. Obtener duración del video usando OpenCV
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(3))
    height = int(cap.get(4))
    
    if frame_rate == 0:
        print("Error: No se pudo obtener la tasa de cuadros del video.")
        return [], 0
    
    # Calcular la duración total del video
    video_duration = total_frames / frame_rate
    
    try:
        # Si tenemos start_time y end_time, crear un segmento temporal del video
        if start_time is not None and end_time is not None:
            scene_duration = end_time - start_time
            # Crear un archivo temporal para el segmento
            temp_video = os.path.join(output_folder, "temp_segment.avi")
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out = cv2.VideoWriter(temp_video, fourcc, frame_rate, (width, height))
            
            # Establecer el punto de inicio
            start_frame = int(start_time * frame_rate)
            end_frame = int(end_time * frame_rate)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            # Escribir solo los frames del segmento
            frames_written = 0
            for _ in range(start_frame, end_frame):
                ret, frame = cap.read()
                if ret:
                    out.write(frame)
                    frames_written += 1
            
            out.release()
            cap.release()
            
            print(f"Frames escritos en el segmento temporal: {frames_written}")
            
            # Verificar que el archivo temporal existe y tiene tamaño
            if not os.path.exists(temp_video) or os.path.getsize(temp_video) == 0:
                print("Error: El segmento temporal no se creó correctamente")
                return [], video_duration
            
            # Calcular número de keyframes
            if scene_duration < 3:  # Si la escena es menor a 3 segundos
                num_keyframes = 3  # Extraer al menos 3 frames
            else:
                num_keyframes = int(3 * scene_duration)  # 3 frames por segundo
            
            num_keyframes = min(num_keyframes, frames_written)
            
            print(f"Extrayendo {num_keyframes} keyframes para la escena...")
            
            # Usar Katna para escenas largas (≥3 segundos) y OpenCV para escenas cortas
            if scene_duration >= 3:
                print("Usando Katna para extraer keyframes (escena larga)...")
                video_processor = Video()
                disk_writer = KeyFrameDiskWriter(location=output_folder)
                try:
                    video_processor.extract_video_keyframes(
                        no_of_frames=num_keyframes,
                        file_path=temp_video,
                        writer=disk_writer
                    )
                except Exception as e:
                    print(f"Error con Katna: {str(e)}, usando OpenCV como respaldo...")
                    # Si Katna falla, usar OpenCV como respaldo
                    cap = cv2.VideoCapture(temp_video)
                    if not cap.isOpened():
                        print("Error: No se pudo abrir el video temporal")
                        return [], video_duration
                    
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    frame_interval = total_frames // num_keyframes
                    
                    for i in range(num_keyframes):
                        frame_pos = i * frame_interval
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                        ret, frame = cap.read()
                        if ret:
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            frame_path = os.path.join(output_folder, f"keyframe_{i}.jpg")
                            Image.fromarray(frame_rgb).save(frame_path, format="JPEG", quality=95)
                    cap.release()
            else:
                print("Usando OpenCV para extraer keyframes (escena corta)...")
                cap = cv2.VideoCapture(temp_video)
                if not cap.isOpened():
                    print("Error: No se pudo abrir el video temporal")
                    return [], video_duration
                
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                frame_interval = total_frames // num_keyframes
                
                for i in range(num_keyframes):
                    frame_pos = (i * frame_interval) + 1  # Skip first frame by adding 1
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                    ret, frame = cap.read()
                    if ret:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        frame_path = os.path.join(output_folder, f"keyframe_{i}.jpg")
                        Image.fromarray(frame_rgb).save(frame_path, format="JPEG", quality=95)
                cap.release()
            
            # Limpiar el archivo temporal
            try:
                os.remove(temp_video)
            except:
                pass
        
        # Contar los frames extraídos
        extracted_frames = len([f for f in os.listdir(output_folder) if f.endswith('.jpg')])
        print(f"Frames extraídos: {extracted_frames}")
        
        return list(range(extracted_frames)), video_duration
        
    except Exception as e:
        print(f"Error al extraer keyframes: {str(e)}")
        # Intentar limpiar el archivo temporal si existe
        try:
            if 'temp_video' in locals():
                os.remove(temp_video)
        except:
            pass
        return [], video_duration


def generate_audiodescriptions(api_key, image_folder, output_json="audiodescriptions.json"):
    max_chars = int(7 * 30)  # 30 caracteres por segundo
    
    descriptions = {}
    total_tokens = 0
    prompt = (
        f"Eres un Especialista en Audiodescripción para personas ciegas o con baja visión. "
        f"Genera una descripción general del video basada en los fotogramas proporcionados, "
        f"ajustándote a {max_chars} caracteres (30 caracteres por segundo).\n\n"
        f"Elementos esenciales a cubrir:\n"
        f"- [Quién] Identifica personajes, características distintivas y acciones\n"
        f"- [Qué] Describe objetos, eventos e interacciones relevantes\n"
        f"- [Dónde] Proporciona contexto del entorno\n"
        f"- [Cuándo] Indica momento del día si es relevante\n"
        f"- [Acción] Especifica movimientos significativos\n"
        f"- [Cambios de Escena] Indica transiciones temporales importantes\n\n"
        f"Mecanismos de Atención (prioriza los más relevantes según el contenido):\n"
        f"1. Personajes:\n"
        f"   - Género y edad aproximada\n"
        f"   - Real o animado\n"
        f"   - Accesorios distintivos\n"
        f"   - Rasgos faciales destacables\n"
        f"   - Justificación: Especifica CUÁL personaje y QUÉ aspectos específicos son relevantes, explicando por qué\n"
        f"2. Expresiones Faciales:\n"
        f"   - Emociones básicas (alegría, tristeza, ira, miedo, sorpresa, asco)\n"
        f"   - Justificación: Especifica CUÁL expresión facial y QUÉ emoción específica se observa, explicando su impacto\n"
        f"3. Acciones:\n"
        f"   - Movimientos de personajes\n"
        f"   - Movimientos de objetos relevantes\n"
        f"   - Justificación: Especifica QUÉ acción concreta y CUÁL es su importancia específica en la escena\n"
        f"4. Escenarios:\n"
        f"   - Ubicación y ambientación\n"
        f"   - Colores predominantes\n"
        f"   - Temporalidad\n"
        f"   - Justificación: Especifica CUÁL escenario y QUÉ elementos específicos son relevantes, explicando su función\n"
        f"5. Clima y Atmósfera:\n"
        f"   - Condiciones ambientales\n"
        f"   - Ambiente general\n"
        f"   - Justificación: Especifica QUÉ condiciones específicas y CUÁL es su efecto concreto en la escena\n"
        f"6. Postura y Lenguaje Corporal:\n"
        f"   - Gestos significativos\n"
        f"   - Posturas relevantes\n"
        f"   - Justificación: Especifica QUÉ gesto o postura específica y CUÁL es su significado concreto\n"
        f"7. Interacciones:\n"
        f"   - Comunicación no verbal entre personajes\n"
        f"   - Justificación: Especifica CUÁLES personajes interactúan y QUÉ comunican específicamente\n"
        f"8. Efectos Especiales:\n"
        f"   - Elementos visuales artificiales relevantes\n"
        f"   - Justificación: Especifica QUÉ efecto específico y CUÁL es su propósito concreto en la narrativa\n\n"
        f"Para cada descripción, indica qué mecanismos de atención fueron utilizados, especificando CUÁL o QUÉ elemento específico se está describiendo y proporcionando una justificación detallada de su relevancia en la escena.\n\n"
        f"Pautas obligatorias:\n"
        f"- Usa tiempo presente y voz activa\n"
        f"- NO menciones textos, créditos o elementos escritos\n"
        f"- Describe de lo general a lo específico\n"
        f"- Mantén un tono objetivo y neutral\n"
        f"- Usa oraciones completas y vocabulario claro\n"
        f"- Sé conciso, evitando detalles innecesarios\n"
        f"- Al final de la descripción, lista los mecanismos de atención utilizados"
    )
    
    # Procesar archivos de ambos formatos (Katna y OpenCV)
    for filename in sorted(os.listdir(image_folder)):
        if filename.endswith((".jpg", ".jpeg", ".png")) and (
            filename.startswith("temp_segment_") or 
            filename.startswith("keyframe_") or
            filename == "temp_segment.jpg" or
            filename == "temp_segment.jpeg"
        ):
            print(f"Procesando archivo: {filename}")
            image_path = os.path.join(image_folder, filename)
            
            # Verificar tamaño del archivo (máximo 10MB)
            file_size = os.path.getsize(image_path) / (1024 * 1024)  # Convertir a MB
            if file_size > 10:
                print(f"Error: El archivo {filename} excede el tamaño máximo permitido de 10MB")
                continue
            
            # Cargar la imagen y convertirla a base64
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Preparar mensajes para la API de Grok
            messages = [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                                "detail": "high"
                            }
                        },
                        {
                            "type": "text",
                            "text": "Describe esta imagen en detalle, siguiendo las pautas de audiodescripción proporcionadas."
                        }
                    ]
                }
            ]
            
            # Llamar a la API de Grok con reintentos
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                response = call_grok_api(messages)
                if response and "choices" in response and len(response["choices"]) > 0:
                    description = response["choices"][0]["message"]["content"]
                    descriptions[filename] = description
                    
                    # Obtener información de tokens si está disponible
                    if "usage" in response:
                        usage = response["usage"]
                        print(f"Procesado: {filename}")
                        print(f"  - Tokens de prompt: {usage.prompt_tokens}")
                        print(f"  - Tokens de completado: {usage.completion_tokens}")
                        print(f"  - Tokens totales: {usage.total_tokens}")
                        if hasattr(usage, 'prompt_tokens_details'):
                            details = usage.prompt_tokens_details
                            print(f"  - Tokens de texto: {details.text_tokens}")
                            print(f"  - Tokens de imagen: {details.image_tokens}")
                    else:
                        # Simular conteo de tokens si no está disponible
                        tokens_used = len(description.split())
                        print(f"Procesado: {filename} - Palabras usadas: {tokens_used}")
                    
                    break
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"Reintento {retry_count} de {max_retries} para {filename}")
                        import time
                        time.sleep(2)  # Esperar 2 segundos antes de reintentar
                    else:
                        print(f"Error al procesar {filename} después de {max_retries} intentos")
    
    print(f"Total de descripciones generadas: {len(descriptions)}")
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(descriptions, f, indent=4, ensure_ascii=False)
    
    print("Audiodescripciones guardadas en", output_json)
    return descriptions

def summarize_audiodescriptions(api_key, descriptions_json, video_duration, output_json="video_summary.json"):
    with open(descriptions_json, "r", encoding="utf-8") as f:
        descriptions = json.load(f)
    
    combined_text = " ".join(descriptions.values())
    max_chars = int(video_duration * 30)  # 30 caracteres por segundo
    
    summary_prompt = (
        f"Eres un Especialista en Audiodescripción para personas ciegas o con baja visión. "
        f"Genera una descripción general del video basada en las descripciones de unos fotogramas, "
        f"ajustándote a {max_chars} caracteres (30 caracteres por segundo).\n\n"
        f"Elementos esenciales a cubrir:\n"
        f"- [Quién] Identifica personajes, características distintivas y acciones\n"
        f"- [Qué] Describe objetos, eventos e interacciones relevantes\n"
        f"- [Dónde] Proporciona contexto del entorno\n"
        f"- [Cuándo] Indica momento del día si es relevante\n"
        f"- [Acción] Especifica movimientos significativos\n"
        f"- [Cambios de Escena] Indica transiciones temporales importantes\n\n"
        f"Mecanismos de Atención (prioriza los más relevantes según el contenido):\n"
        f"1. Personajes:\n"
        f"   - Género y edad aproximada\n"
        f"   - Real o animado\n"
        f"   - Accesorios distintivos\n"
        f"   - Rasgos faciales destacables\n"
        f"   - Justificación: Especifica CUÁL personaje y QUÉ aspectos específicos son relevantes, explicando por qué\n"
        f"2. Expresiones Faciales:\n"
        f"   - Emociones básicas (alegría, tristeza, ira, miedo, sorpresa, asco)\n"
        f"   - Justificación: Especifica CUÁL expresión facial y QUÉ emoción específica se observa, explicando su impacto\n"
        f"3. Acciones:\n"
        f"   - Movimientos de personajes\n"
        f"   - Movimientos de objetos relevantes\n"
        f"   - Justificación: Especifica QUÉ acción concreta y CUÁL es su importancia específica en la escena\n"
        f"4. Escenarios:\n"
        f"   - Ubicación y ambientación\n"
        f"   - Colores predominantes\n"
        f"   - Temporalidad\n"
        f"   - Justificación: Especifica CUÁL escenario y QUÉ elementos específicos son relevantes, explicando su función\n"
        f"5. Clima y Atmósfera:\n"
        f"   - Condiciones ambientales\n"
        f"   - Ambiente general\n"
        f"   - Justificación: Especifica QUÉ condiciones específicas y CUÁL es su efecto concreto en la escena\n"
        f"6. Postura y Lenguaje Corporal:\n"
        f"   - Gestos significativos\n"
        f"   - Posturas relevantes\n"
        f"   - Justificación: Especifica QUÉ gesto o postura específica y CUÁL es su significado concreto\n"
        f"7. Interacciones:\n"
        f"   - Comunicación no verbal entre personajes\n"
        f"   - Justificación: Especifica CUÁLES personajes interactúan y QUÉ comunican específicamente\n"
        f"8. Efectos Especiales:\n"
        f"   - Elementos visuales artificiales relevantes\n"
        f"   - Justificación: Especifica QUÉ efecto específico y CUÁL es su propósito concreto en la narrativa\n\n"
        f"Para cada descripción, indica qué mecanismos de atención fueron utilizados, especificando CUÁL o QUÉ elemento específico se está describiendo y proporcionando una justificación detallada de su relevancia en la escena.\n\n"
        f"Pautas obligatorias:\n"
        f"- Usa tiempo presente y voz activa\n"
        f"- NO menciones textos, créditos o elementos escritos\n"
        f"- Describe de lo general a lo específico\n"
        f"- Mantén un tono objetivo y neutral\n"
        f"- Usa oraciones completas y vocabulario claro\n"
        f"- Sé conciso, evitando detalles innecesarios\n"
        f"- Al final de la descripción, lista los mecanismos de atención utilizados"
    )
    
    # Preparar mensajes para la API de Grok
    messages = [
        {"role": "system", "content": summary_prompt},
        {"role": "user", "content": combined_text}
    ]
    
    # Llamar a la API de Grok con reintentos
    max_retries = 3
    retry_count = 0
    while retry_count < max_retries:
        response = call_grok_api(messages)
        if response and "choices" in response and len(response["choices"]) > 0:
            summary = response["choices"][0]["message"]["content"]
            tokens_used = len(summary.split())  # Aproximación simple
            print(f"Palabras usadas en el resumen: {tokens_used}")
            
            with open(output_json, "w", encoding="utf-8") as f:
                json.dump({"summary": summary}, f, indent=4, ensure_ascii=False)
            
            print("Resumen del video guardado en", output_json)
            return summary
        else:
            retry_count += 1
            if retry_count < max_retries:
                print(f"Reintento {retry_count} de {max_retries} para el resumen")
                import time
                time.sleep(2)  # Esperar 2 segundos antes de reintentar
            else:
                print("Error: No se pudo generar el resumen después de varios intentos")
                return None

def prepare_images_for_analysis(image_folder):
    frames = []
    for image_file in sorted(os.listdir(image_folder)):
        if image_file.endswith(('.jpg', '.png', '.jpeg')):
            image_path = os.path.join(image_folder, image_file)
            # Aquí cargaríamos la imagen para el análisis
            frames.append(image_path)
    return frames

def analyze_prosody(api_key, image_folder, descriptions_json, video_duration):
    frames = prepare_images_for_analysis(image_folder)
    with open(descriptions_json, "r", encoding="utf-8") as f:
        descriptions = json.load(f)
    
    # Analizar las imágenes y las descripciones para sugerir un tono
    combined_text = " ".join(descriptions.values())
    
    # Solicitar a la IA que analice el tono de prosodia adecuado para el video completo
    tone_prompt = (
    f"Analiza las siguientes imágenes de frames del video y el resumen para determinar las emociones presentes:\n\n"
    f"Resumen del video: {combined_text}\n"
    f"[Frame Images: {frames}]\n\n"
    f"Identifica las emociones principales detectadas en todo el video con sus porcentajes (deben sumar 100%). Luego, proporciona una única prosodia general para todo el video en el siguiente formato, basado en la tabla de referencia:\n\n"
    f"Formato de salida (por cada emoción principal):\n"
    f"Emoción principal: [nombre] [porcentaje]%\n"
    f"Emoción complementaria: [nombre]\n"
    f"Intensidad: [texto según tabla]\n"
    f"Tono: [texto según tabla]\n"
    f"Duración: [texto según tabla]\n"
    f"Ritmo: [texto según tabla]\n\n"
    f"Ejemplo:\n"
    f"Emoción principal: Alegría 80%\n"
    f"Emoción complementaria: Serenidad\n"
    f"Intensidad: Baja y suave\n"
    f"Tono: Medio-bajo, estable, sin grandes variaciones\n"
    f"Duración: Larga, pausas relajadas\n"
    f"Ritmo: Lento, regular, pausado\n\n"
    f"No des recomendaciones, interpretaciones adicionales ni ajustes sugeridos. Solo responde siguiendo el formato indicado para cada emoción principal detectada.\n\n"
    f"Referencia de emociones:\n\n"
    f"- Emoción principal: Alegría\n"
    f"  - Emoción complementaria: Serenidad\n"
    f"  - Intensidad: Baja y suave\n"
    f"  - Tono: Medio-bajo, estable, sin grandes variaciones\n"
    f"  - Duración: Larga, pausas relajadas\n"
    f"  - Ritmo: Lento, regular, pausado\n\n"
    f"- Emoción principal: Alegría\n"
    f"  - Emoción complementaria: Éxtasis\n"
    f"  - Intensidad: Muy alta y entusiasta\n"
    f"  - Tono: Alto, con variaciones amplias (picos frecuentes)\n"
    f"  - Duración: Moderada-corta, con exclamaciones\n"
    f"  - Ritmo: Rápido, enérgico, dinámico\n\n"
    f"- Emoción principal: Confianza\n"
    f"  - Emoción complementaria: Aceptación\n"
    f"  - Intensidad: Baja y estable\n"
    f"  - Tono: Medio, cálido, poca variabilidad\n"
    f"  - Duración: Moderada\n"
    f"  - Ritmo: Regular, fluido, sin cambios bruscos\n\n"
    f"- Emoción principal: Confianza\n"
    f"  - Emoción complementaria: Admiración\n"
    f"  - Intensidad: Alta y expresiva\n"
    f"  - Tono: Medio-alto, a veces ligeramente ascendente\n"
    f"  - Duración: Moderada\n"
    f"  - Ritmo: Enfático, con cierto realce, pero no brusco\n\n"
    f"- Emoción principal: Miedo\n"
    f"  - Emoción complementaria: Aprensión\n"
    f"  - Intensidad: Baja, con tensión\n"
    f"  - Tono: Ligero ascenso, posible temblor o quiebre\n"
    f"  - Duración: Moderada, con pausas vacilantes\n"
    f"  - Ritmo: Irregular, inseguro, a veces acelerado\n\n"
    f"- Emoción principal: Miedo\n"
    f"  - Emoción complementaria: Terror\n"
    f"  - Intensidad: Muy alta y potente\n"
    f"  - Tono: Muy alto, con quiebres marcados\n"
    f"  - Duración: Corta, entrecortada\n"
    f"  - Ritmo: Muy acelerado o brusco, pausas de jadeo\n\n"
    f"- Emoción principal: Sorpresa\n"
    f"  - Emoción complementaria: Distracción\n"
    f"  - Intensidad: Muy baja e inconstante\n"
    f"  - Tono: Variable, a veces errático\n"
    f"  - Duración: Variable (puede ser corta o larga)\n"
    f"  - Ritmo: Inconsistente, con cambios inesperados\n\n"
    f"- Emoción principal: Sorpresa\n"
    f"  - Emoción complementaria: Asombro\n"
    f"  - Intensidad: Alta y enfocada en la exclamación\n"
    f"  - Tono: Alto y ascendente al inicio, luego variable\n"
    f"  - Duración: Corta o moderada, con pausas breves\n"
    f"  - Ritmo: Brusco e irregular, marcando sorpresa\n\n"
    f"- Emoción principal: Tristeza\n"
    f"  - Emoción complementaria: Pensamiento profundo\n"
    f"  - Intensidad: Baja y tenue\n"
    f"  - Tono: Medio-bajo, monótono o levemente descendente\n"
    f"  - Duración: Larga, con pausas reflexivas\n"
    f"  - Ritmo: Lento, reflexivo, casi meditativo\n\n"
    f"- Emoción principal: Tristeza\n"
    f"  - Emoción complementaria: Duelo\n"
    f"  - Intensidad: Muy alta y sufrimiento\n"
    f"  - Tono: Bajo, descendente, monótono\n"
    f"  - Duración: Larga, con pausas prolongadas\n"
    f"  - Ritmo: Muy lento, pesado, con silencios marcados\n\n"
    f"- Emoción principal: Disgusto\n"
    f"  - Emoción complementaria: Aburrimiento\n"
    f"  - Intensidad: Muy baja y monótona\n"
    f"  - Tono: Bajo, con poca variación\n"
    f"  - Duración: Moderada-larga, habla sostenida\n"
    f"  - Ritmo: Lento, plano, sin cambios de intensidad\n\n"
    f"- Emoción principal: Disgusto\n"
    f"  - Emoción complementaria: Aversión\n"
    f"  - Intensidad: Alta con desagrado\n"
    f"  - Tono: Medio a alto, seco o cortante\n"
    f"  - Duración: Moderada, a veces con pausas bruscas\n"
    f"  - Ritmo: Cortante, agresivo, enfatizando el rechazo\n\n"
    f"- Emoción principal: Ira\n"
    f"  - Emoción complementaria: Molestia\n"
    f"  - Intensidad: Baja, a veces variable con muy baja\n"
    f"  - Tono: Medio, con pequeños picos de tensión\n"
    f"  - Duración: Moderada, frases más cortas\n"
    f"  - Ritmo: Un tanto acelerado, interrumpido, con quiebres\n\n"
    f"- Emoción principal: Ira\n"
    f"  - Emoción complementaria: Furia\n"
    f"  - Intensidad: Muy alta y dominante\n"
    f"  - Tono: Alto, agresivo, con cambios bruscos\n"
    f"  - Duración: Moderada o corta, intercalada con exclamaciones\n"
    f"  - Ritmo: Rápido, explosivo, con picos intensos\n\n"
    f"- Emoción principal: Anticipación\n"
    f"  - Emoción complementaria: Interés\n"
    f"  - Intensidad: Baja y enfocada\n"
    f"  - Tono: Medio-alto, ligeramente ascendente\n"
    f"  - Duración: Variable (depende de la interacción)\n"
    f"  - Ritmo: Fluido, ágil, mostrando atención sostenida\n\n"
    f"- Emoción principal: Anticipación\n"
    f"  - Emoción complementaria: Vigilancia\n"
    f"  - Intensidad: Alta en alerta\n"
    f"  - Tono: Medio-alto, a veces tenso\n"
    f"  - Duración: Moderada, con pausas para observar\n"
    f"  - Ritmo: Ágil, algo acelerado, atento a cambios\n"
)


    # Usar Grok para generar el análisis de prosodia
    response = call_grok_api([{"role": "system", "content": tone_prompt}, {"role": "user", "content": combined_text}])
    prosody_suggestion = response["choices"][0]["message"]["content"]
    tokens_used = len(prosody_suggestion.split())  # Aproximación simple
    print(f"Palabras usadas en el análisis de prosodia: {tokens_used}")
    
    # Crear estructura JSON con la información de prosodia
    prosody_json = {
        "prosody_analysis": {
            "raw_suggestion": prosody_suggestion,
            "timestamp": str(datetime.datetime.now()),
            "video_duration": video_duration,
            "frames_analyzed": len(frames),
            "tokens_used": tokens_used
        }
    }
    
    # Guardar el JSON en un archivo
    output_json = "prosody_analysis.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(prosody_json, f, indent=4, ensure_ascii=False)
    
    print("Análisis de prosodia guardado en:", output_json)
    return prosody_json

def process_video(video_path, output_base_folder="output", api_key=None):
    if api_key is None:
        print("Se requiere API key para las descripciones y análisis de prosodia")
        return
        
    # Detectar escenas
    scene_data = detect_scene_changes(video_path, 
                                    scene_output_folder=os.path.join(output_base_folder, "scenes"))
    
    # Crear carpeta central para todos los keyframes
    all_keyframes_folder = os.path.join(output_base_folder, "all_keyframes")
    os.makedirs(all_keyframes_folder, exist_ok=True)
    
    # Procesar cada escena que sea de 2 segundos o más
    scene_descriptions = []
    for scene in scene_data:
        if scene["duration"] >= 2:
            scene_folder = os.path.join(output_base_folder, f"scene_{scene['scene_number']}_keyframes")
            print(f"\nProcesando escena {scene['scene_number']} desde {scene['timestamp']}s hasta {scene['timestamp'] + scene['duration']}s")
            print(f"Duración de la escena: {scene['duration']} segundos")
            
            # 1. Extraer keyframes de la escena individual
            keyframes, duration = extract_keyframes(
                video_path,
                scene_folder,
                start_time=scene["timestamp"],
                end_time=scene["timestamp"] + scene["duration"]
            )
            
            # 2. Copiar keyframes a la carpeta central
            for filename in os.listdir(scene_folder):
                if filename.endswith(('.jpg', '.jpeg', '.png')) and (
                    filename.startswith("temp_segment_") or 
                    filename.startswith("keyframe_") or
                    filename == "temp_segment.jpg" or
                    filename == "temp_segment.jpeg"
                ):
                    src_path = os.path.join(scene_folder, filename)
                    # Agregar el número de escena al nombre del archivo para evitar conflictos
                    new_filename = f"scene_{scene['scene_number']}_{filename}"
                    dst_path = os.path.join(all_keyframes_folder, new_filename)
                    import shutil
                    shutil.copy2(src_path, dst_path)
            
            # 3. Generar descripciones para los frames de esta escena
            scene_descriptions_json = os.path.join(output_base_folder, f"scene_{scene['scene_number']}_descriptions.json")
            scene_descriptions.append(generate_audiodescriptions(api_key, scene_folder, scene_descriptions_json))
            
            print(f"Descripciones de la escena {scene['scene_number']} guardadas en {scene_descriptions_json}")
    
    # 4. Generar descripción general del video
    if scene_descriptions:
        # Combinar todas las descripciones de escenas
        all_descriptions = {}
        for scene_desc in scene_descriptions:
            all_descriptions.update(scene_desc)
        
        # Guardar todas las descripciones en un solo archivo
        all_descriptions_json = os.path.join(output_base_folder, "all_scene_descriptions.json")
        with open(all_descriptions_json, "w", encoding="utf-8") as f:
            json.dump(all_descriptions, f, indent=4, ensure_ascii=False)
        
        # Generar resumen general del video
        video_summary_json = os.path.join(output_base_folder, "video_summary.json")
        video_summary = summarize_audiodescriptions(api_key, all_descriptions_json, duration, video_summary_json)
        
        # 5. Analizar prosodia del video completo usando todos los keyframes
        #prosody_json = os.path.join(output_base_folder, "prosody_analysis.json")
        #analyze_prosody(api_key, all_keyframes_folder, video_summary_json, duration)
        
        print("\nProceso completado. Se han generado:")
        print(f"1. Descripciones por escena en archivos scene_X_descriptions.json")
        print(f"2. Descripción general del video en video_summary.json")
        #print(f"3. Análisis de prosodia en prosody_analysis.json")
        print(f"4. Todos los keyframes se han guardado en {all_keyframes_folder}")
    else:
        print("No se encontraron escenas válidas para procesar")

if __name__ == "__main__":
    video_file = "videosescenas/k9Brw_0gncU_14_33.avi"
    api_key = "YOUR_API_KEY"

    process_video(video_file, api_key=api_key)
    
