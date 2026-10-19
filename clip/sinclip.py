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
import numpy as np
import time

def detect_scene_changes(video_path, scene_output_folder="scenes"):
    os.makedirs(scene_output_folder, exist_ok=True)
    video_manager = VideoManager([video_path])
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=27))
    video_manager.start()
    scene_manager.detect_scenes(frame_source=video_manager)
    scene_list = scene_manager.get_scene_list()
    scene_data = []
    for idx, scene in enumerate(scene_list):
        start_time = scene[0].get_seconds()
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
    json_path = os.path.join(scene_output_folder, "scene_changes.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(scene_data, f, ensure_ascii=False, indent=2)
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

def extract_keyframes(video_path, output_folder="keyframes", frames_per_second=2):
    """
    Extrae keyframes del video a una tasa de 1-3 frames por segundo.
    
    Args:
        video_path: Ruta al archivo de video
        output_folder: Carpeta donde guardar los keyframes
        frames_per_second: Número de frames por segundo (1-3)
    """
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    
    if frame_rate == 0:
        print("Error: No se pudo obtener la tasa de cuadros del video.")
        return [], 0
    
    video_duration = total_frames / frame_rate
    
    # Calcular el intervalo entre frames basado en frames_per_second
    frame_interval = int(frame_rate / frames_per_second)
    
    # Asegurar que el intervalo sea al menos 1
    frame_interval = max(1, frame_interval)
    
    print(f"Video: {video_path}")
    print(f"Duración: {video_duration:.2f} segundos")
    print(f"Frame rate: {frame_rate} fps")
    print(f"Frames por segundo extraídos: {frames_per_second}")
    print(f"Intervalo entre frames: {frame_interval}")
    
    frames = []
    frame_indices = []
    
    # Extraer frames en intervalos regulares
    for i in range(0, total_frames, frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frames.append((frame_rgb, i))
        frame_indices.append(i)
    
    cap.release()
    
    if not frames:
        print("No se pudieron extraer frames del video.")
        return [], video_duration
    
    print(f"Total de frames extraídos: {len(frames)}")
    
    # Crear carpeta de salida
    os.makedirs(output_folder, exist_ok=True)
    
    # Guardar frames y crear JSON
    keyframes_json = []
    for idx, (frame, frame_num) in enumerate(frames):
        frame_path = os.path.join(output_folder, f"keyframe_{frame_num}.jpg")
        Image.fromarray(frame).save(frame_path, format="JPEG", quality=95)
        
        frame_time = frame_num / frame_rate
        keyframes_json.append({
            "frame_index": idx,
            "frame_number": frame_num,
            "timestamp": frame_time,
            "filename": f"keyframe_{frame_num}.jpg"
        })
    
    # Guardar JSON con información de los keyframes
    json_path = os.path.join(output_folder, "keyframes.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(keyframes_json, f, ensure_ascii=False, indent=2)
    
    print(f"Keyframes guardados en: {output_folder}")
    print(f"Información de keyframes guardada en: {json_path}")
    
    return [frame[1] for frame in frames], video_duration

def generate_audiodescriptions(api_key, image_folder, output_json="audiodescriptions.json", video_duration=None):
    openai.api_key = api_key
    if video_duration is None:
        max_chars = 30
    else:
        max_chars = int(video_duration * 30)
    descriptions = []
    total_tokens = 0
    prompt = (
        f"Rol:Eres un Especialista en Audiodescripción para personas ciegas o con baja visión.\n"
        f"Tarea: Genera una descripción de la imagen y generar prosodia con base al modelado prosodico (Intensidad, Tono, Duración, Ritmo)\n"
        f"Elementos esenciales a cubrir:\n"
        f"- [Quién] Identifica personajes, características distintivas y acciones\n"
        f"- [Qué] Describe objetos, eventos e interacciones relevantes\n"
        f"- [Dónde] Proporciona contexto del entorno\n"
        f"- [Cuándo] Indica momento del día si es relevante\n"
        f"- [Acción] Especifica movimientos significativos\n"
        f"- [Cambios de Escena] Indica transiciones temporales importantes\n\n"

        f"Mecanismos de Atención (prioriza los más relevantes según el contenido):\n"
        f" 1. Personajes:\n"
        f" Definición conceptual: Entidades narrativas con identidad propia que participan en la acción, portan rasgos físicos, psicológicos, sociales y emocionales, y cuya presencia tiene un peso semántico en la construcción del relato. Su descripción debe priorizar los atributos relevantes para la trama y los aspectos que marcan su evolución emocional. En la audiodescripción, el énfasis está en la caracterización funcional y afectiva.\n"
        f" Ejemplo: Un joven con ropa desgastada y una mirada esquiva recorre la estación de tren sin rumbo aparente. Su caracterización transmite anticipación (media: ansiedad), marcando una identidad emocionalmente suspendida entre la espera y la incertidumbre.\n"
        f" Caracteristicas:\n"
        f"   - Género y edad aproximada\n"
        f"   - Real o animado\n"
        f"   - Accesorios distintivos\n"
        f"   - Rasgos faciales destacables\n"
        f"   - Justificación: Especifica CUÁL personaje y QUÉ aspectos específicos son relevantes, explicando por qué\n"
        f" 2. Expresiones Faciales:\n"
        f" Definición conceptual: Configuraciones musculares del rostro que comunican emociones, intenciones o reacciones internas de los personajes. Son fundamentales para la lectura emocional de la escena y, desde una perspectiva semántica, funcionan como signos icónicos que conectan la interioridad del personaje con el espectador. La audiodescripción debe traducir estas expresiones en términos que evoquen la intensidad y cualidad emocional de forma precisa.\n"
        f" Ejemplo: Un pasillo estrecho, con paredes agrietadas y una luz parpadeante al fondo, acompañado por un zumbido casi imperceptible con un fuerte olor a muerte. La composición del escenario y el clima evocan una emoción de miedo (alto: terror), preparando al oyente para una posible amenaza o evento inesperado.\n"
        f" Caracteristicas:\n"
        f"   - Emociones (Alegría (Bajo: Serenidad, Alto: Éxtasis), Confianza (Bajo: Aceptación, Alto: Admiración), Miedo (Bajo: Aprensión, Alto: Terror), Sorpresa (Bajo: Distracción, Alto: Asombro), Tristeza (Bajo: Duelo, Alto: Pensamiento profundo), Disgusto (Bajo: Aburrimiento, Alto: Odio), Ira (Bajo: Molestia, Alto: Furia), Anticipación (Bajo: Interés, Alto: Vigilancia).)\n"
        f"   - Justificación: Especifica CUÁL Configuración musculares del rostro que comunican emociones y QUÉ emoción específica, explicando su impacto\n"
        f" 3. Acciones:\n"
        f" Definición conceptual: Conjunto de movimientos, gestos o comportamientos ejecutados por personajes o elementos en la escena que impulsan el desarrollo narrativo o comunican intenciones, emociones o cambios de estado. Desde la dimensión semántica, las acciones son unidades mínimas de sentido que articulan la lógica de los acontecimientos, y su mención en la audiodescripción debe enfatizar lo relevante para la comprensión narrativa y emocional del contenido.\n"
        f" Ejemplo: Una mujer abre lentamente una carta, la lee y deja caer los brazos. La acción comunica una emoción de tristeza (medio: tristeza). La pausa en el movimiento y el descenso corporal son claves para expresar el peso emocional del contenido leído.\n"
        f" Caracteristicas:\n"
        f"   - Movimientos de personajes\n"
        f"   - Movimientos de objetos relevantes\n"
        f"   - Justificación: Especifica QUÉ acción concreta y CUÁL es su importancia específica en la escena\n"
        f" 4. Escenarios, clima y atmósfera:\n"
        f" Definición conceptual: Conjunto articulado por el espacio físico representado (escenario) y la carga sensorial y afectiva que lo impregna (clima y atmósfera), que en conjunto configuran el trasfondo emocional y simbólico de la acción narrativa. Desde la dimensión semántica, esta categoría abarca tanto los elementos materiales del entorno (arquitectura, objetos, iluminación, distribución espacial) como sus cualidades expresivas (tonalidad emocional, tensión ambiental, ritmo perceptivo). En la audiodescripción, su traducción debe priorizar los aspectos sensoriales que modelan la experiencia emocional del espectador, activando emociones como miedo, alegría o tristeza, y facilitando la inmersión narrativa del oyente.\n"
        f" Ejemplo: Un pasillo estrecho, con paredes agrietadas y una luz parpadeante al fondo, acompañado por un zumbido casi imperceptible con un fuerte olor a muerte. La composición del escenario y el clima evocan una emoción de miedo (alto: terror), preparando al oyente para una posible amenaza o evento inesperado.\n"
        f" Caracteristicas:\n"
        f"   - Ubicación y ambientación\n"
        f"   - Colores predominantes\n"
        f"   - Temporalidad\n"
        f"   - Condiciones ambientales\n"
        f"   - Ambiente general\n"
        f"   - Justificación: Especifica QUÉ elementos específicos son relevantes y CUÁL es su importancia específica en la escena\n"
        f" 5. Postura y Lenguaje Corporal:\n"
        f" Definición conceptual: Configuraciones físicas del cuerpo y sus movimientos no verbales que expresan estados emocionales, disposiciones actitudinales o relaciones interpersonales. Actúan como signos visuales de significación emocional y contextual. En audiodescripción, deben ser traducidos en imágenes verbales que permitan inferir el estado emocional, la intención o la tensión narrativa de la escena.\n"
        f" Ejemplo: Una mujer se mantiene erguida, con los brazos cruzados y la cabeza levemente inclinada hacia atrás al escuchar a su interlocutor. Su postura indica rechazo (bajo: aburrimiento), marcando distancia emocional y juicio negativo.\n"
        f" Caracteristicas:\n"
        f"   - Gestos significativos\n"
        f"   - Posturas relevantes\n"
        f"   - Justificación: Especifica QUÉ gesto o postura específica y CUÁL es su significado concreto\n"
        f" 6. Interacciones:\n"
        f" Definición conceptual: Relaciones dinámicas entre personajes o entre personajes y objetos/entornos, que revelan vínculos afectivos, sociales o simbólicos. Las interacciones son claves para la comprensión de los roles, jerarquías, conflictos o alianzas en el universo narrativo. En la audiodescripción, se deben describir no solo los actos, sino también el carácter relacional y emocional de los mismos.\n"
        f" Ejemplo: Una niña se recuesta en el hombro de su abuela mientras ambas miran un álbum de fotos. La interacción sugiere confianza (baja: aprobación), comunicando una relación íntima y cálida entre generaciones.\n"
        f" Caracteristicas:\n"
        f"   - Comunicación no verbal entre personajes\n"
        f"   - Justificación: Especifica CUÁLES personajes interactúan y QUÉ comunican específicamente\n"
        f" 7. Efectos Especiales:\n"
        f" Definición conceptual: Elementos visuales, sonoros o digitales que no se corresponden con una representación mimética de la realidad, sino que introducen una dimensión espectacular, simbólica o fantástica en la escena. Su función semántica puede reforzar emociones, enfatizar acciones o crear transiciones. En la audiodescripción, los efectos especiales deben ser interpretados en términos de su impacto emocional y narrativo, no sólo técnico.\n"
        f" Ejemplo: Una explosión de luz azul recorre el cielo cuando dos personajes se toman de la mano. Este efecto especial subraya una emoción de alegría (alta: éxtasis), acentuando la unión emocional intensa entre los personajes. \n"
        f" Caracteristicas:\n"
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
    
    # Obtener lista de archivos y ordenarlos por número de frame
    image_files = []
    for filename in os.listdir(image_folder):
        if filename.endswith((".jpg", ".jpeg", ".png")) and (
            filename.startswith("keyframe_")
        ):
            try:
                frame_num = int(filename.split('_')[1].split('.')[0])
                image_files.append((frame_num, filename))
            except:
                continue
    
    # Ordenar los archivos por número de frame
    image_files.sort(key=lambda x: x[0])
    
    # Procesar los archivos en orden
    for frame_num, filename in image_files:
        print(f"Procesando archivo: {filename}")
        image_path = os.path.join(image_folder, filename)
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            response = openai.chat.completions.create(
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
                ],
                max_tokens=1000
            )
        
        full_response = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        
        # Separar la descripción de los mecanismos de atención
        description = ""
        attention_mechanisms = ""
        
        if "Mecanismos de atención" in full_response:
            parts = full_response.split("Mecanismos de atención")
            description = parts[0].strip()
            attention_mechanisms = "Mecanismos de atención" + parts[1].strip()
        else:
            description = full_response.strip()
        
        descriptions.append({
            "frame_number": frame_num,
            "filename": filename,
            "description": description,
            "attention_mechanisms": attention_mechanisms,
            "tokens_used": tokens_used
        })
        
        total_tokens += tokens_used
        print(f"Procesado: {filename} - Tokens usados: {tokens_used}")
    
    if not descriptions:
        print(f"ADVERTENCIA: No se encontraron imágenes para procesar en {image_folder}")
        print(f"Archivos encontrados: {os.listdir(image_folder)}")
    
    print(f"Total de tokens usados: {total_tokens}")
    
    # Guardar el archivo JSON
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(descriptions, f, ensure_ascii=False, indent=2)
    
    print("Audiodescripciones guardadas en", output_json)
    return descriptions

def summarize_audiodescriptions(api_key, descriptions_json, video_duration, prosody_analysis_json, output_json="video_summary.json"):
    openai.api_key = api_key
    with open(descriptions_json, "r", encoding="utf-8") as f:
        descriptions = json.load(f)
    # Usar solo las descripciones, no los mecanismos de atención
    combined_text = " ".join([d["description"] for d in descriptions])
    max_chars = int(video_duration * 30)
    with open(prosody_analysis_json, "r", encoding="utf-8") as f:
        prosody_content = json.load(f)
    selected_emotion = prosody_content.get("complementary_emotion", None)
    emotion_ranges = {
        "Duelo": (7.08, 11.21),
        "Distracción": (7.38, 11.66),
        "Asombro": (8.93, 14.11),
        "Aversión": (8.86, 14.01),
        "Aceptación": (9.44, 14.91),
        "Admiración": (9.08, 14.36),
        "Aprensión": (7.69, 12.15),
        "Vigilancia": (9.44, 14.91),
        "Aburrimiento": (9.08, 14.36),
        "Pensamiento Profundo": (7.61, 12.02),
        "Molestia": (10.24, 16.18),
        "Serenidad": (9.51, 15.04),
        "Terror": (8.98, 14.18),
        "Interés": (8.41, 13.29),
        "Éxtasis": (10.18, 16.09),
        "Ira": (9.91, 15.65)
    }
    if selected_emotion and selected_emotion in emotion_ranges:
        min_chars_per_sec, max_chars_per_sec = emotion_ranges[selected_emotion]
        min_chars = int(video_duration * min_chars_per_sec)
        max_chars = int(video_duration * max_chars_per_sec)
    else:
        min_chars = 0
        max_chars = 0
    summary_prompt = (
        f"Rol:Eres un Especialista en Audiodescripción para personas ciegas o con baja visión.\n"
        f"Tarea: Genera una descripción general con base a las descripciones de forma secuencial de los frames.\n"
        f"IMPORTANTE - RESTRICCIÓN DE CARACTERES:\n"
        f"La duración del video es {video_duration} segundos.\n"
        f"La emoción complementaria detectada es: {selected_emotion}\n"
        f"Para esta emoción, la descripción principal DEBE tener entre {min_chars} y {max_chars} caracteres en total.\n"
        f"NO EXCEDER ESTOS LÍMITES BAJO NINGUNA CIRCUNSTANCIA.\n\n"
        f"Análisis de prosodia del video:\n{prosody_content}\n"
        f"Pautas de estilo:\n"
        f"- Comienza directamente con la descripción, sin introducciones\n"
        f"- Usa lenguaje directo y activo\n"
        f"- Evita frases como 'en la imagen', 'en el video', 'podemos ver', 'se observa', etc.\n"
        f"- Mantén un tono narrativo fluido y natural\n"
        f"- Describe como si estuvieras contando una historia\n"
        f"- Usa verbos en presente y voz activa\n"
        f"- Sé conciso pero descriptivo\n"
        f"Para cada descripción, indica qué mecanismos de atención fueron utilizados, especificando CUÁL o QUÉ elemento específico se está describiendo y proporcionando una justificación detallada de su relevancia en la escena.\n\n"
        f"Pautas obligatorias:\n"
        f"- Utilizar los mecanismos de atención fueron utilizados \n"
        f"- Ajustar el tono y ritmo de la descripción según el análisis de prosodia proporcionado\n"
        f"- La descripción principal DEBE tener entre {min_chars} y {max_chars} caracteres\n"
        f"- Los mecanismos de atención y la información adicional NO cuentan para el límite de caracteres\n"
        f"- Al final de la descripción, incluir un resumen con:\n"
        f"  * Emoción complementaria utilizada\n"
        f"  * Número total de caracteres de la descripción principal\n"
        f"  * Caracteres por segundo\n"
        f"  * Rango de caracteres permitido para esa emoción\n"
    )    
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": combined_text}
        ],
        max_tokens=1000
    )
    
    full_summary = response.choices[0].message.content
    tokens_used = response.usage.total_tokens
    
    # Separar las diferentes secciones del resumen
    main_summary = ""
    attention_mechanisms = ""
    statistics_summary = ""
    
    # Buscar las diferentes secciones con múltiples variaciones
    attention_keywords = ["Mecanismos de atención", "Mecanismos de Atención", "Mecanismos de Atención Utilizados"]
    stats_keywords = ["Resumen:", "Resumen"]
    
    # Buscar sección de mecanismos de atención
    attention_found = False
    for keyword in attention_keywords:
        if keyword in full_summary:
            parts = full_summary.split(keyword)
            main_summary = parts[0].strip()
            remaining = keyword + parts[1].strip()
            attention_found = True
            break
    
    if not attention_found:
        main_summary = full_summary.strip()
        remaining = ""
    
    # Buscar sección de estadísticas
    if remaining:
        stats_found = False
        for keyword in stats_keywords:
            if keyword in remaining:
                stats_parts = remaining.split(keyword)
                attention_mechanisms = stats_parts[0].strip()
                statistics_summary = keyword + stats_parts[1].strip()
                stats_found = True
                break
        
        if not stats_found:
            attention_mechanisms = remaining
    
    # Calcular estadísticas de caracteres
    # Extraer solo la descripción principal real (primera oración/párrafo)
    if main_summary:
        # Buscar el final de la descripción principal (antes de cualquier sección adicional)
        lines = main_summary.split('\n')
        description_lines = []
        for line in lines:
            line = line.strip()
            if line and not any(keyword in line for keyword in attention_keywords + stats_keywords):
                description_lines.append(line)
            else:
                break
        
        # Unir las líneas de descripción principal
        main_description_text = ' '.join(description_lines)
        char_count = len(main_description_text)
    else:
        char_count = 0
    
    chars_per_second = char_count / video_duration if video_duration > 0 else 0
    
    if char_count > max_chars:
        print(f"ADVERTENCIA: El número de caracteres de la descripción ({char_count}) excede el máximo permitido ({max_chars})")
        print("Se recomienda regenerar la descripción con un número menor de caracteres")
    elif char_count < min_chars:
        print(f"ADVERTENCIA: El número de caracteres de la descripción ({char_count}) es menor al mínimo permitido ({min_chars})")
        print("Se recomienda regenerar la descripción con un número mayor de caracteres")
    
    print(f"Tokens usados en el resumen: {tokens_used}")
    print(f"Total de caracteres de la descripción: {char_count}")
    print(f"Caracteres por segundo: {chars_per_second:.2f}")
    print(f"Rango permitido para {selected_emotion}: {min_chars} - {max_chars} caracteres")
    
    summary_json = {
        "main_summary": main_summary,
        "attention_mechanisms": attention_mechanisms,
        "statistics_summary": statistics_summary,
        "emotion": selected_emotion,
        "char_count": char_count,
        "chars_per_second": chars_per_second,
        "char_range": [min_chars, max_chars],
        "tokens_used": tokens_used
    }
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, ensure_ascii=False, indent=2)
    
    print("Resumen del video guardado en", output_json)
    return summary_json

def analyze_prosody(api_key, image_folder, descriptions_json, video_duration, output_json="prosody_analysis.json"):
    openai.api_key = api_key
    
    with open(descriptions_json, "r", encoding="utf-8") as f:
        descriptions = json.load(f)
    
    # Usar tanto descripción como mecanismos de atención (como en v7)
    combined_text = " ".join([d["description"] + " " + d["attention_mechanisms"] for d in descriptions])
    
    # Solicitar a la IA que analice el tono de prosodia adecuado para el video completo
    tone_prompt = (
    f"Analiza al descripción para una audiodescripcion de video para determinar el modelado prosodico \n"
    f"la descripcion del video, mecanismos de atención y modelado prosodico: {combined_text}\n"
    f"Identifica las emociones principales detectadas (deben sumar 100%). Luego, proporciona una única prosodia general para todo el video en el siguiente formato, basado en la tabla de referencia:\n\n"
    f" Identifica prosodia para la imagen basado en la siguiente tabla de referencia:\n\n"
    	f"Referencia modelado prosodico:\n\n"
    	f"- Emoción principal: Alegría\n"
    	f"  - Emoción complementaria: Serenidad\n"
    	f"  - Intensidad: Bajo\n"
    	f"  - Tono: bajo, estable, sin grandes variaciones\n"
   	f"  - Duración: Larga, pausas relajadas\n"
    	f"  - Ritmo: Lento, regular, pausado\n\n"
    	f"- Emoción principal: Alegría\n"
    	f"  - Emoción complementaria: Éxtasis\n"
    	f"  - Intensidad: Alta\n"
    	f"  - Tono: Alto, con variaciones amplias\n"
    	f"  - Duración: Corta, con exclamaciones\n"
    	f"  - Ritmo: Rápido, enérgico, dinámico\n\n"
    	f"- Emoción principal: Confianza\n"
    	f"  - Emoción complementaria: Aceptación\n"
    	f"  - Intensidad: Bajo\n"
    	f"  - Tono: Medio, cálido, poca variabilidad\n"
    	f"  - Duración: Moderada\n"
    	f"  - Ritmo: Regular, fluido, sin cambios bruscos\n\n"
    	f"- Emoción principal: Confianza\n"
    	f"  - Emoción complementaria: Admiración\n"
    	f"  - Intensidad: Alto\n"
    	f"  - Tono: Alto, a veces ligeramente ascendente\n"
    	f"  - Duración: Moderada\n"
    	f"  - Ritmo: Enfático, con cierto realce, pero no brusco\n\n"
    	f"- Emoción principal: Miedo\n"
    	f"  - Emoción complementaria: Aprensión\n"
    	f"  - Intensidad: Bajo\n"
    	f"  - Tono: Ligero ascenso, posible temblor o quiebre\n"
    	f"  - Duración: Moderada, con pausas vacilantes\n"
    	f"  - Ritmo: Irregular, inseguro, a veces acelerado\n\n"
    	f"- Emoción principal: Miedo\n"
    	f"  - Emoción complementaria: Terror\n"
    	f"  - Intensidad: Alto\n"
    	f"  - Tono: Alto, con quiebres marcados\n"
    	f"  - Duración: Corta, entrecortada\n"
    	f"  - Ritmo: Muy acelerado o brusco, pausas de jadeo\n\n"
    	f"- Emoción principal: Sorpresa\n"
    	f"  - Emoción complementaria: Distracción\n"
    	f"  - Intensidad: Bajo\n"
    	f"  - Tono: Variable, a veces errático\n"
    	f"  - Duración: Variable (puede ser corta o larga)\n"
    	f"  - Ritmo: Inconsistente, con cambios inesperados\n\n"
    	f"- Emoción principal: Sorpresa\n"
    	f"  - Emoción complementaria: Asombro\n"
    	f"  - Intensidad: Alto\n"
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
    	f"  - Intensidad: Alto\n"
    	f"  - Tono: Bajo, descendente, monótono\n"
    	f"  - Duración: Larga, con pausas prolongadas\n"
    	f"  - Ritmo: Muy lento, pesado, con silencios marcados\n\n"
    	f"- Emoción principal: Disgusto\n"
    	f"  - Emoción complementaria: Aburrimiento\n"
    	f"  - Intensidad: Bajo\n"
    	f"  - Tono: Bajo, con poca variación\n"
    	f"  - Duración: larga, habla sostenida\n"
    	f"  - Ritmo: Lento, plano, sin cambios de intensidad\n\n"
    	f"- Emoción principal: Disgusto\n"
    	f"  - Emoción complementaria: Aversión\n"
    	f"  - Intensidad: Alto\n"
    	f"  - Tono: Medio a alto, seco o cortante\n"
    	f"  - Duración: Moderada, a veces con pausas bruscas\n"
    	f"  - Ritmo: Cortante, agresivo, enfatizando el rechazo\n\n"
    	f"- Emoción principal: Ira\n"
    	f"  - Emoción complementaria: Molestia\n"
    	f"  - Intensidad: Bajo\n"
    	f"  - Tono: Medio, con pequeños picos de tensión\n"
    	f"  - Duración: Moderada, frases más cortas\n"
    	f"  - Ritmo: Un tanto acelerado, interrumpido, con quiebres\n\n"
    	f"- Emoción principal: Ira\n"
    	f"  - Emoción complementaria: Furia\n"
    	f"  - Intensidad: Alto\n"
    	f"  - Tono: Alto, agresivo, con cambios bruscos\n"
    	f"  - Duración: Moderada o corta, intercalada con exclamaciones\n"
    	f"  - Ritmo: Rápido, explosivo, con picos intensos\n\n"
    	f"- Emoción principal: Anticipación\n"
    	f"  - Emoción complementaria: Interés\n"
    	f"  - Intensidad: Bajo\n"
    	f"  - Tono: Alto, ligeramente ascendente\n"
    	f"  - Duración: Variable\n"
    	f"  - Ritmo: Fluido, ágil, mostrando atención sostenida\n\n"
    	f"- Emoción principal: Anticipación\n"
    	f"  - Emoción complementaria: Vigilancia\n"
    	f"  - Intensidad: Alto\n"
    	f"  - Tono: Alto, a veces tenso\n"
    	f"  - Duración: Moderada, con pausas para observar\n"
    	f"  - Ritmo: Ágil, algo acelerado, atento a cambios\n"
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
    f"Intensidad: Bajoq\n"
    f"Tono: Medio-bajo, estable, sin grandes variaciones\n"
    f"Duración: Larga, pausas relajadas\n"
    f"Ritmo: Lento, regular, pausado\n\n"
    f"No de recomendaciones, interpretaciones adicionales ni ajustes sugeridos. Solo responde siguiendo el formato indicado para cada emoción principal detectada.\n\n"
   )


    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": tone_prompt},
           {"role": "user", "content": "Dame una sola prosodia general para todo el video siguiendo el formato especificado"}
        ],
        max_tokens=3000
    )
    
    prosody_suggestion = response.choices[0].message.content
    tokens_used = response.usage.total_tokens
    print(f"Tokens usados en el análisis de prosodia: {tokens_used}")
    
    # Intentar extraer los campos principales de la prosodia
    prosody_json = {
        "main_emotion": None,
        "complementary_emotion": None,
        "intensity": None,
        "tone": None,
        "duration": None,
        "rhythm": None,
        "tokens_used": tokens_used
    }
    for line in prosody_suggestion.split('\n'):
        if line.lower().startswith("emoción principal"):
            prosody_json["main_emotion"] = line.split(":")[1].strip()
        elif line.lower().startswith("emoción complementaria"):
            prosody_json["complementary_emotion"] = line.split(":")[1].strip()
        elif line.lower().startswith("intensidad"):
            prosody_json["intensity"] = line.split(":")[1].strip()
        elif line.lower().startswith("tono"):
            prosody_json["tone"] = line.split(":")[1].strip()
        elif line.lower().startswith("duración"):
            prosody_json["duration"] = line.split(":")[1].strip()
        elif line.lower().startswith("ritmo"):
            prosody_json["rhythm"] = line.split(":")[1].strip()
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(prosody_json, f, ensure_ascii=False, indent=2)
    print("Análisis de prosodia guardado en:", output_json)
    return prosody_json

def process_video(video_path, output_base_folder="output", api_key=None, frames_per_second=2):
    if api_key is None:
        print("Se requiere API key para las descripciones y análisis de prosodia")
        return
    keyframes_folder = os.path.join(output_base_folder, "keyframes")
    os.makedirs(keyframes_folder, exist_ok=True)
    keyframes, duration = extract_keyframes(video_path, keyframes_folder, frames_per_second)
    if not keyframes:
        print("No se pudieron extraer keyframes del video")
        return
    print("\n" + "="*50)
    print(f"INFORMACIÓN DEL VIDEO:")
    print(f"Ruta: {video_path}")
    print(f"Duración: {duration:.2f} segundos")
    print(f"Formato: {datetime.timedelta(seconds=int(duration))}")
    print("="*50 + "\n")
    print(f"Se extrajeron {len(keyframes)} keyframes del video")
    audiodesc_json = os.path.join(output_base_folder, "audiodescriptions.json")
    prosody_json = os.path.join(output_base_folder, "prosody_analysis.json")
    summary_json = os.path.join(output_base_folder, "video_summary.json")
    descriptions = generate_audiodescriptions(api_key, keyframes_folder, output_json=audiodesc_json, video_duration=duration)
    prosody_suggestion = analyze_prosody(api_key, keyframes_folder, audiodesc_json, duration, output_json=prosody_json)
    video_summary = summarize_audiodescriptions(api_key, audiodesc_json, duration, prosody_json, output_json=summary_json)
    print("\nProceso completado. Se han generado:")
    print(f"1. Keyframes en {keyframes_folder}")
    print(f"2. Descripciones en {audiodesc_json}")
    print(f"3. Resumen del video en {summary_json}")
    print(f"4. Análisis de prosodia en {prosody_json}")

if __name__ == "__main__":
    video_file = "segmentos\segmento_22.mp4"
    api_key = "YOUR_API_KEY"
    # Puedes cambiar frames_per_second a 1, 2 o 3 según necesites
    process_video(video_file, api_key=api_key, frames_per_second=2)
    
