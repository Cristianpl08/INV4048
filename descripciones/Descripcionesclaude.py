import cv2
import os
import json
import datetime
from PIL import Image
from Katna.video import Video
from Katna.writer import KeyFrameDiskWriter
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
import anthropic
import base64
import torch
import clip
import numpy as np
import time
import re


def is_valid_summary(summary_text):
    """
    Verifica si el resumen es válido (no está vacío, no son solo guiones, etc.)
    """
    if not summary_text or not summary_text.strip():
        return False
    
    # Eliminar espacios en blanco y saltos de línea
    cleaned_text = summary_text.strip()
    
    # Verificar si solo contiene guiones, asteriscos, o caracteres especiales
    if re.match(r'^[\s\-_*]+$', cleaned_text):
        return False
    
    # Verificar si es muy corto (menos de 10 caracteres)
    if len(cleaned_text) < 10:
        return False
    
    # Verificar si contiene solo símbolos o caracteres no alfabéticos
    if not re.search(r'[a-zA-ZáéíóúñÁÉÍÓÚÑ]', cleaned_text):
        return False
    
    # Verificar si parece ser un error común de la API
    error_patterns = [
        "error",
        "no se pudo",
        "no se puede",
        "imposible",
        "falló",
        "failed",
        "empty",
        "vacío",
        "sin contenido"
    ]
    
    cleaned_lower = cleaned_text.lower()
    for pattern in error_patterns:
        if pattern in cleaned_lower:
            return False
    
    return True


def extract_keyframes(video_path, output_folder="keyframes"):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    if frame_rate == 0:
        print("Error: No se pudo obtener la tasa de cuadros del video.")
        return [], 0
    video_duration = total_frames / frame_rate
    frame_interval = max(1, total_frames // 100)
    frames = []
    frame_indices = []
    for i in range(0, total_frames, frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = preprocess(Image.fromarray(frame_rgb)).unsqueeze(0).to(device)
        frames.append((image, frame_rgb, i))
        frame_indices.append(i)
    cap.release()
    if not frames:
        return [], video_duration
    frames_tensor = torch.cat([f[0] for f in frames])
    with torch.no_grad():
        image_features = model.encode_image(frames_tensor)
    image_features /= image_features.norm(dim=-1, keepdim=True)
    similarities = torch.mm(image_features, image_features.T)
    diversity_scores = similarities.sum(dim=1)
    num_keyframes = max(5, min(len(frames) // 10, 15))
    keyframe_indices = torch.argsort(diversity_scores)[:num_keyframes]
    selected_frames = [frames[idx] for idx in keyframe_indices.cpu().numpy()]
    selected_frames.sort(key=lambda x: x[2])
    os.makedirs(output_folder, exist_ok=True)
    keyframes_json = []
    for idx, (_, frame, frame_num) in enumerate(selected_frames):
        frame_path = os.path.join(output_folder, f"keyframe_{frame_num}.jpg")
        Image.fromarray(frame).save(frame_path, format="JPEG", quality=95)
        frame_time = frame_num / frame_rate
        keyframes_json.append({
            "frame_index": idx,
            "frame_number": frame_num,
            "timestamp": frame_time,
            "filename": f"keyframe_{frame_num}.jpg"
        })
    json_path = os.path.join(output_folder, "keyframes.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(keyframes_json, f, ensure_ascii=False, indent=2)
    return [frame[2] for frame in selected_frames], video_duration

def extract_keyframes_clip_adjustable(video_path, output_folder="keyframes_clip", 
                                    diversity_threshold=0.7, 
                                    similarity_threshold=0.8,
                                    min_keyframes=5, 
                                    max_keyframes=15,
                                    frame_sampling_rate=30):
    """
    Extrae keyframes usando CLIP con umbrales ajustables
    """
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    
    if frame_rate == 0:
        print("Error: No se pudo obtener la tasa de cuadros del video.")
        return [], 0
    
    video_duration = total_frames / frame_rate
    
    # Ajustar intervalo de muestreo
    frame_interval = max(1, frame_sampling_rate)
    
    frames = []
    frame_indices = []
    
    print(f"Analizando video con {total_frames} frames, muestreando cada {frame_interval} frames...")
    
    for i in range(0, total_frames, frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = preprocess(Image.fromarray(frame_rgb)).unsqueeze(0).to(device)
        frames.append((image, frame_rgb, i))
        frame_indices.append(i)
    
    cap.release()
    
    if not frames:
        return [], video_duration
    
    # Extraer características CLIP
    frames_tensor = torch.cat([f[0] for f in frames])
    with torch.no_grad():
        image_features = model.encode_image(frames_tensor)
    
    image_features /= image_features.norm(dim=-1, keepdim=True)
    similarities = torch.mm(image_features, image_features.T)
    
    # Selección por diversidad
    diversity_scores = similarities.sum(dim=1)
    diversity_scores = (diversity_scores - diversity_scores.min()) / (diversity_scores.max() - diversity_scores.min())
    
    # Lógica mejorada - calcular target_frames de manera más inteligente
    # Queremos extraer más frames, no solo el mínimo
    if len(frames) <= min_keyframes:
        target_frames = len(frames)
    else:
        # Tomar al menos min_keyframes, pero preferiblemente más
        # Usar una fracción más grande del total de frames
        target_frames = min(max_keyframes, max(min_keyframes, len(frames) // 2))
    
    print(f"Frames muestreados: {len(frames)}, Target frames: {target_frames}")
    
    # Tomar los frames más diversos directamente
    diverse_indices = torch.argsort(diversity_scores)[:target_frames]
    
    # Usar directamente todos los frames seleccionados por diversidad
    final_keyframes = diverse_indices.tolist()
    
    # Asegurar mínimo de keyframes - lógica simplificada
    if len(final_keyframes) < min_keyframes and len(frames) >= min_keyframes:
        # Si no tenemos suficientes, tomar más frames directamente
        additional_needed = min_keyframes - len(final_keyframes)
        remaining_indices = [i for i in range(len(frames)) if i not in final_keyframes]
        if remaining_indices:
            # Tomar los frames restantes más diversos
            remaining_diversity = diversity_scores[remaining_indices]
            best_remaining = torch.argsort(remaining_diversity)[:additional_needed]
            for idx in best_remaining:
                final_keyframes.append(remaining_indices[idx.item()])
    
    # Ordenar por orden temporal
    final_keyframes.sort()
    
    selected_frames = [frames[idx] for idx in final_keyframes]
    
    # Guardar keyframes
    os.makedirs(output_folder, exist_ok=True)
    saved_frames = []
    
    # Crear JSON con información de keyframes
    keyframes_json = []
    
    for idx, (_, frame, frame_num) in enumerate(selected_frames):
        frame_path = os.path.join(output_folder, f"keyframe_{frame_num}.jpg")
        Image.fromarray(frame).save(frame_path, format="JPEG", quality=95)
        saved_frames.append(frame_num)
        
        # Agregar información al JSON
        frame_time = frame_num / frame_rate
        keyframes_json.append({
            "frame_index": idx,
            "frame_number": frame_num,
            "timestamp": frame_time,
            "filename": f"keyframe_{frame_num}.jpg"
        })
        
        print(f"Keyframe guardado: keyframe_{frame_num}.jpg")
    
    # Guardar JSON con información de keyframes
    json_path = os.path.join(output_folder, "keyframes.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(keyframes_json, f, ensure_ascii=False, indent=2)
    
    print(f"Total keyframes extraídos con CLIP: {len(saved_frames)}")
    print(f"Configuración usada - Diversidad: {diversity_threshold}, Similitud: {similarity_threshold}")
    
    return saved_frames, video_duration


def generate_audiodescriptions(api_key, image_folder, output_json="audiodescriptions.json", video_duration=None):
    client = anthropic.Anthropic(api_key=api_key)
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
        f"- [Cambios de Escena] Indica transiciones temporales importantes\n"
        f"- [Logos] Si hay logotipos, símbolos o elementos gráficos identificativos, descríbelos detalladamente, incluyendo su forma, colores predominantes, ubicación en la imagen y cualquier elemento visual relevante. Explica su posible función o significado en la escena.\n\n"

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
        f"   - Justificación: Especifica QUÉ efecto específico y CUÁL es su propósito concreto en la narrativa\n"
        f" 8. Logos y Elementos Gráficos Identificativos:\n"
        f" Definición conceptual: Imágenes, símbolos, logotipos o marcas visuales que identifican una empresa, organización, producto o contenido específico. Su presencia puede aportar información sobre la autoría, el contexto comercial o la intencionalidad comunicativa de la escena. En la audiodescripción, deben ser descritos en cuanto a su forma, colores, ubicación y cualquier elemento distintivo, evitando leer textos pero transmitiendo su función o impacto visual.\n"
        f" Ejemplo: En el centro de la imagen, un logotipo azul y blanco muestra la silueta de un camarógrafo junto a una cámara antigua, enmarcado por un rectángulo celeste. El diseño transmite profesionalismo y está asociado a una productora audiovisual.\n"
        f" Características:\n"
        f"   - Forma y composición visual\n"
        f"   - Colores predominantes\n"
        f"   - Ubicación en la imagen\n"
        f"   - Elementos gráficos distintivos\n"
        f"   - Justificación: Especifica QUÉ logotipo o símbolo se describe y CUÁL es su relevancia o función en la escena\n\n"

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
            image_data = image_file.read()
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt + "\n\nDescribe esta imagen:"},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(image_data).decode('utf-8')}}
                    ]}
                ]
            )
        
        full_response = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        
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
    client = anthropic.Anthropic(api_key=api_key)
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
        f"- Si en los frames se identifica un logotipo, símbolo o elemento gráfico identificativo, menciónalo y descríbelo también en la descripción general, explicando su relevancia visual y simbólica.\n"
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
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        messages=[
            {"role": "user", "content": summary_prompt + "\n\n" + combined_text}
        ]
    )
    
    full_summary = response.content[0].text
    tokens_used = response.usage.input_tokens + response.usage.output_tokens
    
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
    client = anthropic.Anthropic(api_key=api_key)
    
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


    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=3000,
        messages=[
            {"role": "user", "content": tone_prompt + "\n\nDame una sola prosodia general para todo el video siguiendo el formato especificado"}
        ]
    )
    
    prosody_suggestion = response.content[0].text
    tokens_used = response.usage.input_tokens + response.usage.output_tokens
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

def process_video(video_path, output_base_folder="output", api_key=None):
    if api_key is None:
        print("Se requiere API key para las descripciones y análisis de prosodia")
        return
    
    # Crear carpeta específica para este video
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    video_output_folder = os.path.join(output_base_folder, video_name)
    os.makedirs(video_output_folder, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"PROCESANDO VIDEO: {video_name}")
    print(f"{'='*60}")
    
    keyframes_folder = os.path.join(video_output_folder, "keyframes")
    os.makedirs(keyframes_folder, exist_ok=True)
    
    keyframes, duration = extract_keyframes_clip_adjustable(
        video_path, 
        output_folder=keyframes_folder,
        diversity_threshold=0.2,  # Permisivo para diversidad
        similarity_threshold=0.3,  # Permisivo para similitud
        min_keyframes=3,  # Mínimo razonable
        max_keyframes=30,  # Máximo razonable
        frame_sampling_rate=15 # Muestrear cada 15 frames
    )
    if not keyframes:
        print("No se pudieron extraer keyframes del video")
        return
    
    print(f"\n{'='*50}")
    print(f"INFORMACIÓN DEL VIDEO:")
    print(f"Ruta: {video_path}")
    print(f"Duración: {duration:.2f} segundos")
    print(f"Formato: {datetime.timedelta(seconds=int(duration))}")
    print(f"{'='*50}\n")
    print(f"Se extrajeron {len(keyframes)} keyframes del video")
    
    # Archivos de salida específicos para este video
    audiodesc_json = os.path.join(video_output_folder, "audiodescriptions.json")
    prosody_json = os.path.join(video_output_folder, "prosody_analysis.json")
    summary_json = os.path.join(video_output_folder, "video_summary.json")
    
    # Procesar descripciones
    print(f"\nGenerando audiodescripciones para {video_name}...")
    descriptions = generate_audiodescriptions(api_key, keyframes_folder, output_json=audiodesc_json, video_duration=duration)
    
    # Analizar prosodia
    print(f"\nAnalizando prosodia para {video_name}...")
    prosody_suggestion = analyze_prosody(api_key, keyframes_folder, audiodesc_json, duration, output_json=prosody_json)
    
    # Generar resumen con verificación y reintentos
    print(f"\nGenerando resumen para {video_name}...")
    max_retries = 3
    retry_count = 0
    video_summary = None
    
    while retry_count < max_retries:
        try:
            video_summary = summarize_audiodescriptions(api_key, audiodesc_json, duration, prosody_json, output_json=summary_json)
            
            # Verificar si el resumen es válido
            if video_summary and "main_summary" in video_summary:
                main_summary = video_summary["main_summary"]
                if is_valid_summary(main_summary):
                    print(f"✓ Resumen generado exitosamente y validado")
                    break
                else:
                    print(f"⚠ Resumen inválido detectado: '{main_summary[:50]}...'")
                    print(f"Reintentando generación del resumen (intento {retry_count + 2}/{max_retries})...")
            else:
                print(f"⚠ Resumen vacío o sin main_summary, reintentando...")
                
        except Exception as e:
            print(f"Error generando resumen: {str(e)}")
            print(f"Reintentando... (intento {retry_count + 2}/{max_retries})")
        
        retry_count += 1
        if retry_count < max_retries:
            print("Esperando 5 segundos antes del reintento...")
            time.sleep(5)
    
    if retry_count >= max_retries:
        print(f"❌ No se pudo generar un resumen válido después de {max_retries} intentos")
        if video_summary and "main_summary" in video_summary:
            print(f"Último resumen generado: '{video_summary['main_summary'][:100]}...'")
    else:
        print(f"✅ Resumen final válido generado en {retry_count + 1} intentos")
    
    print(f"\n{'='*50}")
    print(f"PROCESO COMPLETADO PARA: {video_name}")
    print(f"{'='*50}")
    print(f"Se han generado en {video_output_folder}:")
    print(f"1. Keyframes en {keyframes_folder}")
    print(f"2. Descripciones en {audiodesc_json}")
    print(f"3. Resumen del video en {summary_json}")
    print(f"4. Análisis de prosodia en {prosody_json}")
    print(f"{'='*50}\n")
    
    return video_output_folder

def reprocess_summary_only(video_name, output_base_folder="output", api_key=None, max_retries=3):
    """
    Reprocesa solo el resumen de un video específico, reutilizando las audiodescripciones ya generadas
    """
    if api_key is None:
        print("Se requiere API key para reprocesar el resumen")
        return False
    
    video_output_folder = os.path.join(output_base_folder, video_name)
    
    # Verificar que existan los archivos necesarios
    audiodesc_json = os.path.join(video_output_folder, "audiodescriptions.json")
    prosody_json = os.path.join(video_output_folder, "prosody_analysis.json")
    summary_json = os.path.join(video_output_folder, "video_summary.json")
    
    if not os.path.exists(audiodesc_json):
        print(f"❌ No se encontró el archivo de audiodescripciones: {audiodesc_json}")
        return False
    
    if not os.path.exists(prosody_json):
        print(f"❌ No se encontró el archivo de análisis de prosodia: {prosody_json}")
        return False
    
    print(f"\n{'='*60}")
    print(f"REPROCESANDO SOLO EL RESUMEN PARA: {video_name}")
    print(f"{'='*60}")
    
    # Leer la duración del video desde las audiodescripciones existentes
    try:
        with open(audiodesc_json, "r", encoding="utf-8") as f:
            descriptions = json.load(f)
        
        # Calcular duración aproximada basada en el número de keyframes
        # Asumiendo que cada keyframe representa aproximadamente 1 segundo
        duration = len(descriptions) * 1.0  # Aproximación simple
        
        print(f"Duración estimada del video: {duration:.2f} segundos")
        
    except Exception as e:
        print(f"Error leyendo audiodescripciones: {str(e)}")
        return False
    
    # Reprocesar el resumen con verificación
    retry_count = 0
    video_summary = None
    
    while retry_count < max_retries:
        try:
            print(f"\nGenerando resumen (intento {retry_count + 1}/{max_retries})...")
            video_summary = summarize_audiodescriptions(api_key, audiodesc_json, duration, prosody_json, output_json=summary_json)
            
            # Verificar si el resumen es válido
            if video_summary and "main_summary" in video_summary:
                main_summary = video_summary["main_summary"]
                if is_valid_summary(main_summary):
                    print(f"✓ Resumen regenerado exitosamente y validado")
                    print(f"Resumen: '{main_summary[:100]}...'")
                    return True
                else:
                    print(f"⚠ Resumen inválido detectado: '{main_summary[:50]}...'")
                    if retry_count < max_retries - 1:
                        print(f"Reintentando generación del resumen...")
            else:
                print(f"⚠ Resumen vacío o sin main_summary, reintentando...")
                
        except Exception as e:
            print(f"Error generando resumen: {str(e)}")
            if retry_count < max_retries - 1:
                print(f"Reintentando...")
        
        retry_count += 1
        if retry_count < max_retries:
            print("Esperando 5 segundos antes del reintento...")
            time.sleep(5)
    
    print(f"❌ No se pudo generar un resumen válido después de {max_retries} intentos")
    if video_summary and "main_summary" in video_summary:
        print(f"Último resumen generado: '{video_summary['main_summary'][:100]}...'")
    
    return False

def check_and_reprocess_invalid_summaries(output_base_folder="output", api_key=None, max_retries=3):
    """
    Verifica todos los resúmenes en la carpeta de salida y reprocesa los que son inválidos
    """
    if api_key is None:
        print("Se requiere API key para reprocesar los resúmenes")
        return
    
    if not os.path.exists(output_base_folder):
        print(f"❌ La carpeta {output_base_folder} no existe")
        return
    
    print(f"\n{'='*60}")
    print(f"VERIFICANDO Y REPROCESANDO RESUMENES INVÁLIDOS")
    print(f"Carpeta: {output_base_folder}")
    print(f"{'='*60}")
    
    # Obtener todas las carpetas de videos
    video_folders = []
    for item in os.listdir(output_base_folder):
        item_path = os.path.join(output_base_folder, item)
        if os.path.isdir(item_path):
            video_folders.append(item)
    
    if not video_folders:
        print("No se encontraron carpetas de videos para verificar")
        return
    
    print(f"Se encontraron {len(video_folders)} carpetas de videos para verificar")
    
    valid_summaries = []
    invalid_summaries = []
    reprocessed_summaries = []
    
    for video_folder in video_folders:
        summary_json = os.path.join(output_base_folder, video_folder, "video_summary.json")
        
        if not os.path.exists(summary_json):
            print(f"⚠ {video_folder}: No se encontró archivo de resumen")
            invalid_summaries.append(video_folder)
            continue
        
        try:
            with open(summary_json, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
            
            if "main_summary" in summary_data:
                main_summary = summary_data["main_summary"]
                if is_valid_summary(main_summary):
                    print(f"✓ {video_folder}: Resumen válido")
                    valid_summaries.append(video_folder)
                else:
                    print(f"❌ {video_folder}: Resumen inválido - '{main_summary[:50]}...'")
                    invalid_summaries.append(video_folder)
                    
                    # Intentar reprocesar
                    print(f"🔄 Reprocesando resumen para {video_folder}...")
                    if reprocess_summary_only(video_folder, output_base_folder, api_key, max_retries):
                        reprocessed_summaries.append(video_folder)
                        print(f"✅ {video_folder}: Resumen reprocesado exitosamente")
                    else:
                        print(f"❌ {video_folder}: No se pudo reprocesar el resumen")
            else:
                print(f"❌ {video_folder}: Resumen sin main_summary")
                invalid_summaries.append(video_folder)
                
        except Exception as e:
            print(f"❌ {video_folder}: Error leyendo resumen - {str(e)}")
            invalid_summaries.append(video_folder)
    
    # Resumen final
    print(f"\n{'='*60}")
    print(f"RESUMEN DE VERIFICACIÓN Y REPROCESAMIENTO")
    print(f"{'='*60}")
    print(f"Resúmenes válidos: {len(valid_summaries)}")
    print(f"Resúmenes inválidos: {len(invalid_summaries)}")
    print(f"Resúmenes reprocesados exitosamente: {len(reprocessed_summaries)}")
    
    if valid_summaries:
        print(f"\nResúmenes válidos:")
        for folder in valid_summaries:
            print(f"  ✓ {folder}")
    
    if invalid_summaries:
        print(f"\nResúmenes inválidos:")
        for folder in invalid_summaries:
            print(f"  ❌ {folder}")
    
    if reprocessed_summaries:
        print(f"\nResúmenes reprocesados exitosamente:")
        for folder in reprocessed_summaries:
            print(f"  ✅ {folder}")
    
    print(f"{'='*60}")

def process_all_videos(segmentos_folder="segmentos", output_base_folder="output", api_key=None):
    """
    Procesa todos los videos en la carpeta segmentos de manera individual
    """
    if not os.path.exists(segmentos_folder):
        print(f"Error: La carpeta {segmentos_folder} no existe")
        return
    
    # Obtener todos los archivos de video
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']
    video_files = []
    
    for filename in os.listdir(segmentos_folder):
        if any(filename.lower().endswith(ext) for ext in video_extensions):
            video_path = os.path.join(segmentos_folder, filename)
            video_files.append(video_path)
    
    if not video_files:
        print(f"No se encontraron archivos de video en {segmentos_folder}")
        return
    
    # Ordenar archivos por nombre
    video_files.sort()
    
    print(f"Se encontraron {len(video_files)} videos para procesar:")
    for video_path in video_files:
        print(f"  - {os.path.basename(video_path)}")
    
    print(f"\n{'='*60}")
    print("INICIANDO PROCESAMIENTO DE TODOS LOS VIDEOS")
    print(f"{'='*60}")
    
    processed_videos = []
    failed_videos = []
    
    for i, video_path in enumerate(video_files, 1):
        try:
            print(f"\nProcesando video {i}/{len(video_files)}: {os.path.basename(video_path)}")
            output_folder = process_video(video_path, output_base_folder, api_key)
            if output_folder:
                processed_videos.append((video_path, output_folder))
        except Exception as e:
            print(f"Error procesando {os.path.basename(video_path)}: {str(e)}")
            failed_videos.append(video_path)
    
    # Resumen final
    print(f"\n{'='*60}")
    print("RESUMEN FINAL DEL PROCESAMIENTO")
    print(f"{'='*60}")
    print(f"Videos procesados exitosamente: {len(processed_videos)}")
    print(f"Videos con errores: {len(failed_videos)}")
    
    if processed_videos:
        print(f"\nVideos procesados exitosamente:")
        for video_path, output_folder in processed_videos:
            print(f"  ✓ {os.path.basename(video_path)} → {output_folder}")
    
    if failed_videos:
        print(f"\nVideos con errores:")
        for video_path in failed_videos:
            print(f"  ✗ {os.path.basename(video_path)}")
    
    print(f"\nTodos los archivos de salida se encuentran en la carpeta: {output_base_folder}")
    print(f"{'='*60}")

if __name__ == "__main__":
    # Replace with your Claude API key
    api_key = "YOUR_API_KEY"
    
    # Opciones de procesamiento
    import sys
    
    if len(sys.argv) > 1:
        option = sys.argv[1].lower()
        
        if option == "reprocess_summary":
            # Reprocesar solo el resumen de un video específico
            if len(sys.argv) > 2:
                video_name = sys.argv[2]
                reprocess_summary_only(video_name, "output2", api_key)
            else:
                print("Uso: python Descripciones.py reprocess_summary <nombre_del_video>")
        
        elif option == "check_summaries":
            # Verificar y reprocesar todos los resúmenes inválidos
            output_folder = sys.argv[2] if len(sys.argv) > 2 else "output2"
            check_and_reprocess_invalid_summaries(output_folder, api_key)
        
        elif option == "process_all":
            # Procesar todos los videos (comportamiento original)
            segmentos_folder = sys.argv[2] if len(sys.argv) > 2 else "PruebaIAS"
            output_folder = sys.argv[3] if len(sys.argv) > 3 else "output"
            process_all_videos(segmentos_folder=segmentos_folder, output_base_folder=output_folder, api_key=api_key)
        
        else:
            print("Opciones disponibles:")
            print("  python Descripciones.py process_all [carpeta_segmentos] [carpeta_salida]")
            print("  python Descripciones.py reprocess_summary <nombre_del_video>")
            print("  python Descripciones.py check_summaries [carpeta_salida]")
    else:
        # Comportamiento por defecto: procesar todos los videos
        process_all_videos(segmentos_folder="PruebaIAS", output_base_folder="output", api_key=api_key)
    
