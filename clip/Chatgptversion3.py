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
import torch
import clip
import numpy as np
import time

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

    # Crear contenido RTF
    rtf_content = "{\\rtf1\\ansi\\ansicpg1252\\deff0\\deflang1033\n"
    rtf_content += "{\\fonttbl{\\f0\\fnil\\fcharset0 Calibri;}}\n"
    rtf_content += "{\\colortbl;\\red0\\green0\\blue0;}\n"
    rtf_content += "\\viewkind4\\uc1\\pard\\sa200\\sl276\\slmult1\\f0\\fs22\\lang9\n"
    rtf_content += "\\b Información de cambios de escena:\\b0\\par\n"
    rtf_content += f"Ruta del video: {video_path}\\par\n"
    rtf_content += f"Total de escenas: {len(scene_data)}\\par\n\n"
    
    for scene in scene_data:
        rtf_content += f"\\b Escena {scene['scene_number']}:\\b0\\par\n"
        rtf_content += f"Timestamp: {scene['timestamp_formatted']}\\par\n"
        rtf_content += f"Duración: {scene['duration']:.2f} segundos\\par\n"
        rtf_content += "\\par\n"
    
    rtf_content += "}"
    
    # Guardar el RTF
    rtf_path = os.path.join(scene_output_folder, "scene_changes.rtf")
    with open(rtf_path, 'w', encoding='utf-8') as f:
        f.write(rtf_content)
    
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

def extract_keyframes(video_path, output_folder="keyframes"):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    
    if frame_rate == 0:
        print("Error: No se pudo obtener la tasa de cuadros del video.")
        return [], 0
    
    video_duration = total_frames / frame_rate  # Duración en segundos
    
    frame_interval = max(1, total_frames // 100)  # Tomar hasta 100 frames para análisis
    
    frames = []
    frame_indices = []
    
    for i in range(0, total_frames, frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = preprocess(Image.fromarray(frame_rgb)).unsqueeze(0).to(device)
        frames.append((image, frame_rgb, i))  # Guardar en RGB directamente
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
    
    num_keyframes = max(5, min(len(frames) // 10, 15))  # Asegurar un mínimo de 5 y un máximo de 15
    keyframe_indices = torch.argsort(diversity_scores)[:num_keyframes]
    
    selected_frames = [frames[idx] for idx in keyframe_indices.cpu().numpy()]
    
    # Ordenar los frames por número de frame
    selected_frames.sort(key=lambda x: x[2])
    
    os.makedirs(output_folder, exist_ok=True)
    
    # Crear archivo RTF con la información temporal
    rtf_content = "{\\rtf1\\ansi\\ansicpg1252\\deff0\\deflang1033\n"
    rtf_content += "{\\fonttbl{\\f0\\fnil\\fcharset0 Calibri;}}\n"
    rtf_content += "{\\colortbl;\\red0\\green0\\blue0;}\n"
    rtf_content += "\\viewkind4\\uc1\\pard\\sa200\\sl276\\slmult1\\f0\\fs22\\lang9\n"
    rtf_content += "\\b Información temporal de los frames:\\b0\\par\n"
    
    for idx, (_, frame, frame_num) in enumerate(selected_frames):
        frame_path = os.path.join(output_folder, f"keyframe_{frame_num}.jpg")
        Image.fromarray(frame).save(frame_path, format="JPEG", quality=95)
        
        # Calcular el tiempo del frame
        frame_time = frame_num / frame_rate
        minutes = int(frame_time // 60)
        seconds = frame_time % 60
        
        # Agregar información al archivo RTF
        rtf_content += f"\\par\nFrame {idx + 1}:\\par\n"
        rtf_content += f"Nombre del archivo: keyframe_{frame_num}.jpg\\par\n"
        rtf_content += f"Tiempo: {minutes:02d}:{seconds:06.3f}\\par\n"
        rtf_content += f"Número de frame: {frame_num}\\par\n"
    
    rtf_content += "}"
    
    # Guardar el archivo RTF
    rtf_path = os.path.join(output_folder, "frames_timing.rtf")
    with open(rtf_path, "w", encoding="utf-8") as f:
        f.write(rtf_content)
    
    return [frame[2] for frame in selected_frames], video_duration

def generate_audiodescriptions(api_key, image_folder, output_rtf="audiodescriptions.rtf"):
    openai.api_key = api_key
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
    
    # Crear contenido RTF
    rtf_content = "{\\rtf1\\ansi\\ansicpg1252\\deff0\\deflang1033\n"
    rtf_content += "{\\fonttbl{\\f0\\fnil\\fcharset0 Calibri;}}\n"
    rtf_content += "{\\colortbl;\\red0\\green0\\blue0;}\n"
    rtf_content += "\\viewkind4\\uc1\\pard\\sa200\\sl276\\slmult1\\f0\\fs22\\lang9\n"
    rtf_content += "\\b Audiodescripciones:\\b0\\par\n\n"
    
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
        
        description = response.choices[0].message.content
        descriptions[filename] = description
        
        # Agregar al contenido RTF
        rtf_content += f"\\b Frame {frame_num}:\\b0\\par\n"
        rtf_content += f"{description}\\par\n"
        rtf_content += "\\par\n"
        
        # Agregar conteo de tokens
        tokens_used = response.usage.total_tokens
        total_tokens += tokens_used
        print(f"Procesado: {filename} - Tokens usados: {tokens_used}")
    
    if not descriptions:
        print(f"ADVERTENCIA: No se encontraron imágenes para procesar en {image_folder}")
        print(f"Archivos encontrados: {os.listdir(image_folder)}")
    
    print(f"Total de tokens usados: {total_tokens}")
    
    # Agregar información de tokens al RTF
    rtf_content += f"\\b Información de procesamiento:\\b0\\par\n"
    rtf_content += f"Total de tokens usados: {total_tokens}\\par\n"
    rtf_content += f"Total de frames procesados: {len(descriptions)}\\par\n"
    rtf_content += "}"
    
    # Guardar el archivo RTF
    with open(output_rtf, "w", encoding="utf-8") as f:
        f.write(rtf_content)
    
    print("Audiodescripciones guardadas en", output_rtf)
    return descriptions

def summarize_audiodescriptions(api_key, descriptions_rtf, video_duration, output_rtf="video_summary.rtf"):
    openai.api_key = api_key
    
    # Leer el archivo RTF y extraer las descripciones
    with open(descriptions_rtf, "r", encoding="utf-8") as f:
        rtf_content = f.read()
    
    # Extraer las descripciones del contenido RTF
    descriptions = {}
    current_frame = None
    current_description = []
    
    for line in rtf_content.split('\n'):
        if line.startswith('\\b Frame'):
            if current_frame and current_description:
                descriptions[current_frame] = '\n'.join(current_description)
            current_frame = line.split('Frame ')[1].split(':')[0]
            current_description = []
        elif line and not line.startswith('\\') and not line.startswith('{') and not line.startswith('}'):
            current_description.append(line)
    
    if current_frame and current_description:
        descriptions[current_frame] = '\n'.join(current_description)
    
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
        f"- Al final de la descripción, lista los elementos específicos que describiste"
    )
    
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": combined_text}
        ],
        max_tokens=1000
    )
    
    summary = response.choices[0].message.content
    tokens_used = response.usage.total_tokens
    print(f"Tokens usados en el resumen: {tokens_used}")
    
    # Crear contenido RTF con formato mejorado
    rtf_content = "{\\rtf1\\ansi\\ansicpg1252\\deff0\\deflang1033\n"
    rtf_content += "{\\fonttbl{\\f0\\fnil\\fcharset0 Calibri;}}\n"
    rtf_content += "{\\colortbl;\\red0\\green0\\blue0;}\n"
    rtf_content += "\\viewkind4\\uc1\\pard\\sa200\\sl276\\slmult1\\f0\\fs22\\lang9\n"
    rtf_content += "\\b Resumen del video:\\b0\\par\n\n"
    
    # Dividir el resumen en párrafos y mecanismos de atención
    paragraphs = summary.split('\n\n')
    for paragraph in paragraphs:
        if paragraph.startswith('Mecanismos de atención:'):
            rtf_content += "\\b Mecanismos de atención:\\b0\\par\n"
            # Procesar cada mecanismo con tabulación
            mechanisms = paragraph.split('Mecanismos de atención:')[1].strip().split('\n')
            for mechanism in mechanisms:
                if mechanism.strip():
                    rtf_content += f"\\tab {mechanism.strip()}\\par\n"
        else:
            rtf_content += f"{paragraph}\\par\n"
    
    rtf_content += "\\par\n"
    rtf_content += "\\b Información de procesamiento:\\b0\\par\n"
    rtf_content += f"Tokens usados: {tokens_used}\\par\n"
    rtf_content += f"Duración del video: {video_duration:.2f} segundos\\par\n"
    rtf_content += "}"
    
    # Guardar el archivo RTF
    with open(output_rtf, "w", encoding="utf-8") as f:
        f.write(rtf_content)
    
    print("Resumen del video guardado en", output_rtf)
    return summary

def prepare_images_for_analysis(image_folder):
    frames = []
    for image_file in sorted(os.listdir(image_folder)):
        if image_file.endswith(('.jpg', '.png', '.jpeg')):
            image_path = os.path.join(image_folder, image_file)
            # Aquí cargaríamos la imagen para el análisis
            frames.append(image_path)
    return frames

def analyze_prosody(api_key, image_folder, descriptions_rtf, video_duration):
    openai.api_key = api_key
    frames = prepare_images_for_analysis(image_folder)
    
    # Leer el archivo RTF y extraer las descripciones
    with open(descriptions_rtf, "r", encoding="utf-8") as f:
        rtf_content = f.read()
    
    # Extraer las descripciones del contenido RTF
    descriptions = {}
    current_frame = None
    current_description = []
    
    for line in rtf_content.split('\n'):
        if line.startswith('\\b Frame'):
            if current_frame and current_description:
                descriptions[current_frame] = '\n'.join(current_description)
            current_frame = line.split('Frame ')[1].split(':')[0]
            current_description = []
        elif line and not line.startswith('\\') and not line.startswith('{') and not line.startswith('}'):
            current_description.append(line)
    
    if current_frame and current_description:
        descriptions[current_frame] = '\n'.join(current_description)
    
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
    
    # Crear contenido RTF
    rtf_content = "{\\rtf1\\ansi\\ansicpg1252\\deff0\\deflang1033\n"
    rtf_content += "{\\fonttbl{\\f0\\fnil\\fcharset0 Calibri;}}\n"
    rtf_content += "{\\colortbl;\\red0\\green0\\blue0;}\n"
    rtf_content += "\\viewkind4\\uc1\\pard\\sa200\\sl276\\slmult1\\f0\\fs22\\lang9\n"
    rtf_content += "\\b Análisis de Prosodia:\\b0\\par\n\n"
    rtf_content += f"{prosody_suggestion}\\par\n\n"
    rtf_content += f"\\b Información de procesamiento:\\b0\\par\n"
    rtf_content += f"Tokens usados: {tokens_used}\\par\n"
    rtf_content += f"Duración del video: {video_duration:.2f} segundos\\par\n"
    rtf_content += f"Frames analizados: {len(frames)}\\par\n"
    rtf_content += f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\par\n"
    rtf_content += "}"
    
    # Guardar el archivo RTF
    output_rtf = "prosody_analysis.rtf"
    with open(output_rtf, "w", encoding="utf-8") as f:
        f.write(rtf_content)
    
    print("Análisis de prosodia guardado en:", output_rtf)
    return prosody_suggestion

def process_video(video_path, output_base_folder="output", api_key=None):
    if api_key is None:
        print("Se requiere API key para las descripciones y análisis de prosodia")
        return
        
    # Crear carpeta para los keyframes
    keyframes_folder = os.path.join(output_base_folder, "keyframes")
    os.makedirs(keyframes_folder, exist_ok=True)
    
    # Extraer keyframes usando CLIP
    keyframes, duration = extract_keyframes(video_path, keyframes_folder)
    
    if not keyframes:
        print("No se pudieron extraer keyframes del video")
        return
    
    print(f"Se extrajeron {len(keyframes)} keyframes del video")
    
    # Generar descripciones para los keyframes
    descriptions = generate_audiodescriptions(api_key, keyframes_folder)
    
    # Generar resumen del video
    video_summary = summarize_audiodescriptions(api_key, "audiodescriptions.rtf", duration)
    
    # Analizar prosodia
    prosody_suggestion = analyze_prosody(api_key, keyframes_folder, "audiodescriptions.rtf", duration)
    
    print("\nProceso completado. Se han generado:")
    print(f"1. Keyframes en {keyframes_folder}")
    print(f"2. Descripciones en audiodescriptions.rtf")
    print(f"3. Resumen del video en video_summary.rtf")
    print(f"4. Análisis de prosodia en prosody_analysis.rtf")

if __name__ == "__main__":
    video_file = "videosart\zTn-nNj5Bng_61_77.avi"
    api_key = "YOUR_API_KEY"

    process_video(video_file, api_key=api_key)
    
