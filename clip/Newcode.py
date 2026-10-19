import cv2
import os
import json
import datetime
from PIL import Image
from Katna.video import Video
from Katna.writer import KeyFrameDiskWriter
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
import openai
import base64

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
                    frame_pos = i * frame_interval
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
    client = openai.OpenAI(api_key=api_key)
    max_chars = int(7 * 30)  # 30 caracteres por segundo
    prompt = (
        f"Eres un Especialista en Audiodescripción para personas ciegas o con baja visión. "
        f"Genera una descripción general del video basada en los fotogramas proporcionados, "
        f"ajustándote a {max_chars} caracteres (30 caracteres por segundo).\n\n"
        f"Proporciona tu respuesta en dos partes:\n\n"
        f"1. DESCRIPCIÓN GENERAL:\n"
        f"Elementos esenciales a cubrir:\n"
        f"- [Quién] Identifica personajes, características distintivas y acciones\n"
        f"- [Qué] Describe objetos, eventos e interacciones relevantes\n"
        f"- [Dónde] Proporciona contexto del entorno\n"
        f"- [Cuándo] Indica momento del día si es relevante\n"
        f"- [Acción] Especifica movimientos significativos\n"
        f"- [Cambios de Escena] Indica transiciones temporales importantes\n\n"
        f"2. ANÁLISIS DE MECANISMOS DE ATENCIÓN:\n"
        f"Para cada mecanismo utilizado, explica detalladamente:\n"
        f"- Por qué fue seleccionado\n"
        f"- Qué elementos específicos de la imagen justifican su uso\n"
        f"- Cómo contribuye a la comprensión global de la escena\n\n"
        f"Mecanismos disponibles:\n"
        f"1. Personajes:\n"
        f"   - Género y edad aproximada\n"
        f"   - Real o animado\n"
        f"   - Accesorios distintivos\n"
        f"   - Rasgos faciales destacables\n"
        f"2. Expresiones Faciales:\n"
        f"   - Emociones básicas (alegría, tristeza, ira, miedo, sorpresa, asco)\n"
        f"3. Acciones:\n"
        f"   - Movimientos de personajes\n"
        f"   - Movimientos de objetos relevantes\n"
        f"4. Escenarios:\n"
        f"   - Ubicación y ambientación\n"
        f"   - Colores predominantes\n"
        f"   - Temporalidad\n"
        f"5. Clima y Atmósfera:\n"
        f"   - Condiciones ambientales\n"
        f"   - Ambiente general\n"
        f"6. Postura y Lenguaje Corporal:\n"
        f"   - Gestos significativos\n"
        f"   - Posturas relevantes\n"
        f"7. Interacciones:\n"
        f"   - Comunicación no verbal entre personajes\n"
        f"8. Efectos Especiales:\n"
        f"   - Elementos visuales artificiales relevantes\n\n"
        f"Pautas obligatorias:\n"
        f"- Usa tiempo presente y voz activa\n"
        f"- NO menciones textos, créditos o elementos escritos\n"
        f"- Describe de lo general a lo específico\n"
        f"- Mantén un tono objetivo y neutral\n"
        f"- Usa oraciones completas y vocabulario claro\n"
        f"- Sé conciso, evitando detalles innecesarios\n\n"
        f"Formato de respuesta esperado:\n\n"
        f"DESCRIPCIÓN:\n"
        f"[Tu descripción aquí]\n\n"
        f"ANÁLISIS DE MECANISMOS DE ATENCIÓN:\n"
        f"1. [Mecanismo]: \n"
        f"   - Justificación de selección: [explicar por qué se eligió]\n"
        f"   - Elementos específicos: [detallar qué elementos de la escena lo justifican]\n"
        f"   - Contribución a la comprensión: [explicar cómo ayuda a entender mejor la escena]\n"
        f"2. [Mecanismo]: \n"
        f"   [Mismo formato de análisis]\n"
        f"[etc.]"
    )
    
    descriptions = {}
    total_tokens = 0
    
    for filename in sorted(os.listdir(image_folder)):
        if (filename.endswith(('.jpg', '.png', '.jpeg')) and 
            (filename.startswith('keyframe_') or filename.startswith('temp_segment'))):
            
            image_path = os.path.join(image_folder, filename)
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": prompt},
                        {
                            "role": "user", 
                            "content": [
                                {"type": "text", "text": "Describe esta imagen:"},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_data}"
                                    }
                                }
                            ]
                        }
                    ]
                )
            
            description = response.choices[0].message.content
            descriptions[filename] = description
            
            tokens_used = response.usage.total_tokens
            total_tokens += tokens_used
            print(f"Procesado: {filename} - Tokens usados: {tokens_used}")
    
    print(f"Total de tokens usados: {total_tokens}")
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(descriptions, f, indent=4, ensure_ascii=False)
    
    print("Audiodescripciones guardadas en", output_json)
    return descriptions

def summarize_audiodescriptions(api_key, descriptions_json, video_duration, output_json="video_summary.json"):
    client = openai.OpenAI(api_key=api_key)
    
    with open(descriptions_json, "r", encoding="utf-8") as f:
        descriptions = json.load(f)
    
    # Filtrar las descripciones que no son "Lo siento, no puedo..."
    valid_descriptions = {
        k: v for k, v in descriptions.items() 
        if not v.startswith("Lo siento, no puedo")
    }
    
    if not valid_descriptions:
        print("No hay descripciones válidas para generar el resumen")
        return None
    
    # Extraer solo las partes de "DESCRIPCIÓN:" de cada frame
    frame_descriptions = []
    for desc in valid_descriptions.values():
        if "DESCRIPCIÓN:" in desc:
            desc_part = desc.split("DESCRIPCIÓN:")[1].split("ANÁLISIS")[0].strip()
            frame_descriptions.append(desc_part)
    
    combined_text = " ".join(frame_descriptions)
    max_chars = int(video_duration * 30)  # 30 caracteres por segundo
    
    summary_prompt = (
        f"Eres un Especialista en Audiodescripción para personas ciegas o con baja visión. "
        f"Genera una descripción general del video basada en las siguientes descripciones de frames, "
        f"ajustándote a {max_chars} caracteres (30 caracteres por segundo).\n\n"
        f"Descripciones de frames:\n{combined_text}\n\n"
        f"Proporciona tu respuesta en dos partes:\n\n"
        f"1. DESCRIPCIÓN GENERAL:\n"
        f"Elementos esenciales a cubrir:\n"
        f"- [Quién] Identifica personajes, características distintivas y acciones\n"
        f"- [Qué] Describe objetos, eventos e interacciones relevantes\n"
        f"- [Dónde] Proporciona contexto del entorno\n"
        f"- [Cuándo] Indica momento del día si es relevante\n"
        f"- [Acción] Especifica movimientos significativos\n"
        f"- [Cambios de Escena] Indica transiciones temporales importantes\n\n"
        f"2. ANÁLISIS DE MECANISMOS DE ATENCIÓN:\n"
        f"Para cada mecanismo utilizado, explica detalladamente:\n"
        f"- Por qué fue seleccionado\n"
        f"- Qué elementos específicos de la escena justifican su uso\n"
        f"- Cómo contribuye a la comprensión global de la secuencia\n\n"
        f"Mecanismos disponibles:\n"
        f"1. Personajes:\n"
        f"   - Género y edad aproximada\n"
        f"   - Real o animado\n"
        f"   - Accesorios distintivos\n"
        f"   - Rasgos faciales destacables\n"
        f"2. Expresiones Faciales:\n"
        f"   - Emociones básicas (alegría, tristeza, ira, miedo, sorpresa, asco)\n"
        f"3. Acciones:\n"
        f"   - Movimientos de personajes\n"
        f"   - Movimientos de objetos relevantes\n"
        f"4. Escenarios:\n"
        f"   - Ubicación y ambientación\n"
        f"   - Colores predominantes\n"
        f"   - Temporalidad\n"
        f"5. Clima y Atmósfera:\n"
        f"   - Condiciones ambientales\n"
        f"   - Ambiente general\n"
        f"6. Postura y Lenguaje Corporal:\n"
        f"   - Gestos significativos\n"
        f"   - Posturas relevantes\n"
        f"7. Interacciones:\n"
        f"   - Comunicación no verbal entre personajes\n"
        f"8. Efectos Especiales:\n"
        f"   - Elementos visuales artificiales relevantes\n\n"
        f"Pautas obligatorias:\n"
        f"- Usa tiempo presente y voz activa\n"
        f"- NO menciones textos, créditos o elementos escritos\n"
        f"- Describe de lo general a lo específico\n"
        f"- Mantén un tono objetivo y neutral\n"
        f"- Usa oraciones completas y vocabulario claro\n"
        f"- Sé conciso, evitando detalles innecesarios\n"
        f"- IMPORTANTE: Solo usa la información proporcionada en las descripciones de los frames\n\n"
        f"Formato de respuesta esperado:\n\n"
        f"DESCRIPCIÓN:\n"
        f"[Tu descripción aquí]\n\n"
        f"ANÁLISIS DE MECANISMOS DE ATENCIÓN:\n"
        f"1. [Mecanismo]: \n"
        f"   - Justificación de selección: [explicar por qué se eligió]\n"
        f"   - Elementos específicos: [detallar qué elementos de la escena lo justifican]\n"
        f"   - Contribución a la comprensión: [explicar cómo ayuda a entender mejor la escena]\n"
        f"2. [Mecanismo]: \n"
        f"   [Mismo formato de análisis]\n"
        f"[etc.]"
    )
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": "Genera un resumen coherente basado en las descripciones de los frames proporcionadas"}
        ]
    )
    
    summary = response.choices[0].message.content
    tokens_used = response.usage.total_tokens
    print(f"Tokens usados en el resumen: {tokens_used}")
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary}, f, indent=4, ensure_ascii=False)
    
    print("Resumen del video guardado en", output_json)
    return summary

def prepare_images_for_analysis(image_folder):
    frames = []
    for image_file in sorted(os.listdir(image_folder)):
        if (image_file.endswith(('.jpg', '.png', '.jpeg')) and 
            (image_file.startswith('keyframe_') or image_file.startswith('temp_segment'))):
            image_path = os.path.join(image_folder, image_file)
            frames.append(image_path)
    return frames

def analyze_prosody(api_key, image_folder, summary_json, video_duration, output_json="prosody_analysis.json"):
    client = openai.OpenAI(api_key=api_key)
    
    # Obtener todas las imágenes válidas
    frames = prepare_images_for_analysis(image_folder)
    print(f"Analizando prosodia para {len(frames)} frames")
    
    # Cargar el resumen de las descripciones
    with open(summary_json, "r", encoding="utf-8") as f:
        summary_data = json.load(f)
        summary = summary_data.get("summary", "")  # Obtener el resumen generado
    
    # El resto del prompt y análisis usando el resumen
    tone_prompt = (
        f"Analiza las siguientes imágenes de frames del video y el resumen para determinar el tono de prosodia más adecuado:\n\n"
        f"Resumen del video: {summary}\n"  # Usar el resumen en lugar de las descripciones individuales
        f"[Frame Images: {frames}]\n\n"
        f"Observa cada frame y determina:\n\n"
        f"1. Las emociones principales presentes en cada escena con sus porcentajes respectivos\n"
        f"2. Para cada segmento o cambio significativo identificado visualmente en el video, especifica:\n"
        f"   - Las emociones dominantes y sus porcentajes\n"
        f"   - Cómo debe adaptarse el tono según estas emociones\n\n"
        f"Utiliza como referencia las siguientes características para cada emoción:\n\n"
        f"- **Alegría** → **Serenidad**\n"
        f"  - **Intensidad**: Baja y suave\n"
        f"  - **Tono**: Medio-bajo, estable, sin grandes variaciones\n"
        f"  - **Duración**: Larga, pausas relajadas\n"
        f"  - **Ritmo**: Lento, regular, pausado\n\n"
        f"- **Éxtasis** → **Muy alta y entusiasta**\n"
        f"  - **Intensidad**: Muy alta y entusiasta\n"
        f"  - **Tono**: Alto, con variaciones amplias (picos frecuentes)\n"
        f"  - **Duración**: Moderada-corta, con exclamaciones\n"
        f"  - **Ritmo**: Rápido, enérgico, dinámico\n\n"
        f"- **Confianza** → **Aceptación**\n"
        f"  - **Intensidad**: Baja y estable\n"
        f"  - **Tono**: Medio, cálido, poca variabilidad\n"
        f"  - **Duración**: Moderada\n"
        f"  - **Ritmo**: Regular, fluido, sin cambios bruscos\n\n"
        f"- **Confianza** → **Admiración**\n"
        f"  - **Intensidad**: Alta y expresiva\n"
        f"  - **Tono**: Medio-alto, a veces ligeramente ascendente\n"
        f"  - **Duración**: Moderada\n"
        f"  - **Ritmo**: Enfático, con cierto realce, pero no brusco\n\n"
        f"- **Miedo** → **Aprensión**\n"
        f"  - **Intensidad**: Baja, con tensión\n"
        f"  - **Tono**: Ligero ascenso, posible temblor o quiebre\n"
        f"  - **Duración**: Moderada, con pausas vacilantes\n"
        f"  - **Ritmo**: Irregular, inseguro, a veces acelerado\n\n"
        f"- **Miedo** → **Terror**\n"
        f"  - **Intensidad**: Muy alta y potente\n"
        f"  - **Tono**: Muy alto, con quiebres marcados\n"
        f"  - **Duración**: Corta, entrecortada\n"
        f"  - **Ritmo**: Muy acelerado o brusco, pausas de jadeo\n\n"
        f"- **Sorpresa** → **Distracción**\n"
        f"  - **Intensidad**: Muy baja e inconstante\n"
        f"  - **Tono**: Variable, a veces errático\n"
        f"  - **Duración**: Variable (puede ser corta o larga)\n"
        f"  - **Ritmo**: Inconsistente, con cambios inesperados\n\n"
        f"- **Sorpresa** → **Asombro**\n"
        f"  - **Intensidad**: Alta y enfocada en la exclamación\n"
        f"  - **Tono**: Alto y ascendente al inicio, luego variable\n"
        f"  - **Duración**: Corta o moderada, con pausas breves\n"
        f"  - **Ritmo**: Brusco e irregular, marcando sorpresa\n\n"
        f"- **Tristeza** → **Pensamiento profundo**\n"
        f"  - **Intensidad**: Baja y tenue\n"
        f"  - **Tono**: Medio-bajo, monótono o levemente descendente\n"
        f"  - **Duración**: Larga, con pausas reflexivas\n"
        f"  - **Ritmo**: Lento, reflexivo, casi meditativo\n\n"
        f"- **Tristeza** → **Duelo**\n"
        f"  - **Intensidad**: Muy alta y sufrimiento\n"
        f"  - **Tono**: Bajo, descendente, monótono\n"
        f"  - **Duración**: Larga, con pausas prolongadas\n"
        f"  - **Ritmo**: Muy lento, pesado, con silencios marcados\n\n"
        f"- **Disgusto** → **Aburrimiento**\n"
        f"  - **Intensidad**: Muy baja y monótona\n"
        f"  - **Tono**: Bajo, con poca variación\n"
        f"  - **Duración**: Moderada-larga, habla sostenida\n"
        f"  - **Ritmo**: Lento, plano, sin cambios de intensidad\n\n"
        f"- **Disgusto** → **Aversión**\n"
        f"  - **Intensidad**: Alta con desagrado\n"
        f"  - **Tono**: Medio a alto, seco o cortante\n"
        f"  - **Duración**: Moderada, a veces con pausas bruscas\n"
        f"  - **Ritmo**: Cortante, agresivo, enfatizando el rechazo\n\n"
        f"- **Ira** → **Molestia**\n"
        f"  - **Intensidad**: Baja, a veces variable con muy baja\n"
        f"  - **Tono**: Medio, con pequeños picos de tensión\n"
        f"  - **Duración**: Moderada, frases más cortas\n"
        f"  - **Ritmo**: Un tanto acelerado, interrumpido, con quiebres\n\n"
        f"- **Ira** → **Furia**\n"
        f"  - **Intensidad**: Muy alta y dominante\n"
        f"  - **Tono**: Alto, agresivo, con cambios bruscos\n"
        f"  - **Duración**: Moderada o corta, intercalada con exclamaciones\n"
        f"  - **Ritmo**: Rápido, explosivo, con picos intensos\n\n"
        
        f"- **Anticipación** → **Interés**\n"
        f"  - **Intensidad**: Baja y enfocada\n"
        f"  - **Tono**: Medio-alto, ligeramente ascendente\n"
        f"  - **Duración**: Variable (depende de la interacción)\n"
        f"  - **Ritmo**: Fluido, ágil, mostrando atención sostenida\n\n"
        
        f"- **Anticipación** → **Vigilancia**\n"
        f"  - **Intensidad**: Alta en alerta\n"
        f"  - **Tono**: Medio-alto, a veces tenso\n"
        f"  - **Duración**: Moderada, con pausas para observar\n"
        f"  - **Ritmo**: Ágil, algo acelerado, atento a cambios\n\n"
        
        f"Para el análisis de prosodia, proporcione:\n\n"
        f"1. Combinación de emociones principales con sus respectivos porcentajes (si aplica)\n"
        f"2. Para cada emoción identificada:\n"
        f"   - Intensidad específica según el porcentaje de la emoción\n"
        f"   - Tono de voz ajustado a la combinación\n"
        f"   - Duración recomendada de las frases\n"
        f"   - Ritmo sugerido\n"
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": tone_prompt},
            {"role": "user", "content": "Proporcione una sugerencia de tono de prosodia para este video"}
        ]
    )
    
    prosody_suggestion = response.choices[0].message.content
    tokens_used = response.usage.total_tokens
    print(f"Tokens usados en el análisis de prosodia: {tokens_used}")
    
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
    
    # Crear una carpeta para todos los keyframes
    all_keyframes_folder = os.path.join(output_base_folder, "all_keyframes")
    os.makedirs(all_keyframes_folder, exist_ok=True)
    
    # Procesar cada escena que sea de 2 segundos o más
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
            
            # Verificar que se extrajeron frames válidos (incluyendo ambos formatos)
            valid_frames = [f for f in os.listdir(scene_folder) 
                          if (f.endswith(('.jpg', '.png', '.jpeg')) and 
                              (f.startswith('keyframe_') or f.startswith('temp_segment')))]
            
            if valid_frames:
                print(f"Procesando {len(valid_frames)} frames válidos para la escena {scene['scene_number']}")
                
                # 2. Generar descripciones para los frames de esta escena
                scene_descriptions_file = os.path.join(output_base_folder, f"scene_{scene['scene_number']}_descriptions.json")
                scene_descriptions = generate_audiodescriptions(api_key, scene_folder, scene_descriptions_file)
                
                # Copiar los frames a la carpeta general de keyframes
                for frame in valid_frames:
                    src = os.path.join(scene_folder, frame)
                    dst = os.path.join(all_keyframes_folder, f"scene_{scene['scene_number']}_{frame}")
                    import shutil
                    shutil.copy2(src, dst)
                
                print(f"\nCompletado el procesamiento de la escena {scene['scene_number']}:")
                print(f"- Keyframes extraídos: {len(valid_frames)}")
                print(f"- Descripciones guardadas en: {scene_descriptions_file}")
            else:
                print(f"No se encontraron frames válidos para la escena {scene['scene_number']}")
    
    # Generar un único resumen general del video
    if os.path.exists(all_keyframes_folder):
        print("\nGenerando resumen general del video...")
        
        # Obtener la duración total del video
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_duration = total_frames / fps
        cap.release()
        
        # Generar descripciones para todos los keyframes
        all_descriptions_file = os.path.join(output_base_folder, "all_descriptions.json")
        all_descriptions = generate_audiodescriptions(api_key, all_keyframes_folder, all_descriptions_file)
        
        # Generar un único resumen general
        summary_file = os.path.join(output_base_folder, "video_summary.json")
        video_summary = summarize_audiodescriptions(
            api_key,
            all_descriptions_file,
            total_duration,
            summary_file
        )
        
        print("\nCompletado el procesamiento general del video:")
        print(f"- Total de keyframes procesados: {len(os.listdir(all_keyframes_folder))}")
        print(f"- Descripciones generales guardadas en: {all_descriptions_file}")
        print(f"- Resumen general guardado en: {summary_file}")
        
        # Analizar prosodia general del video
        #prosody_file = os.path.join(output_base_folder, "video_prosody.json")
        #analyze_prosody(
        #    api_key,
        #    all_keyframes_folder,
        #    summary_file,
        #    total_duration,
        #    prosody_file
        #)
        #print(f"- Análisis de prosodia guardado en: {prosody_file}")

if __name__ == "__main__":
    video_file = "videosescenas/zMg9dChF97A_12_38.avi"
    api_key = "YOUR_API_KEY"

    process_video(video_file, api_key=api_key)
    
