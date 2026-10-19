import torch
import clip
import cv2
import os
import json
import numpy as np
import openai
from PIL import Image
import base64
import datetime
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector

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

    # Guardar los cortes de escena en una lista de tiempos
    scene_times = [scene[0].get_seconds() for scene in scene_list]
    
    # Guardar las imágenes clave de cada escena
    cap = cv2.VideoCapture(video_path)
    for idx, scene_time in enumerate(scene_times):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(scene_time * cap.get(cv2.CAP_PROP_FPS)))
        ret, frame = cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_path = os.path.join(scene_output_folder, f"scene_{idx+1}_frame.jpg")
            Image.fromarray(frame_rgb).save(frame_path, format="JPEG", quality=95)
    
    cap.release()
    return scene_times

def extract_keyframes_from_scenes(video_path, scene_times, output_folder="keyframes"):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    
    if frame_rate == 0:
        print("Error: No se pudo obtener la tasa de cuadros del video.")
        return [], 0
    
    video_duration = total_frames / frame_rate  # Duración en segundos
    
    frames = []
    frame_indices = []
    
    for scene_time in scene_times:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(scene_time * frame_rate))
        ret, frame = cap.read()
        if not ret:
            continue
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = preprocess(Image.fromarray(frame_rgb)).unsqueeze(0).to(device)
        frames.append((image, frame_rgb, scene_time))  # Agregar el tiempo del fotograma como tercer valor
        frame_indices.append(scene_time)
    
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
    
    os.makedirs(output_folder, exist_ok=True)
    for idx, (_, frame, _) in enumerate(selected_frames):  # Ahora debería funcionar correctamente
        frame_path = os.path.join(output_folder, f"keyframe_{idx+1}.jpg")
        Image.fromarray(frame).save(frame_path, format="JPEG", quality=95)  # Guardar correctamente en RGB
    
    return [frame[2] for frame in selected_frames], video_duration

def generate_audiodescriptions(api_key, image_folder, output_json="audiodescriptions.json"):
    openai.api_key = api_key
    max_chars = int(7 * 30)  # 30 caracteres por segundo
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
        f"Para cada descripción, indica qué mecanismos de atención fueron utilizados.\n\n"
        f"Pautas obligatorias:\n"
        f"- Usa tiempo presente y voz activa\n"
        f"- NO menciones textos, créditos o elementos escritos\n"
        f"- Describe de lo general a lo específico\n"
        f"- Mantén un tono objetivo y neutral\n"
        f"- Usa oraciones completas y vocabulario claro\n"
        f"- Sé conciso, evitando detalles innecesarios\n"
        f"- Al final de la descripción, lista los mecanismos de atención utilizados"
    )
    
    descriptions = {}
    total_tokens = 0
    
    for filename in sorted(os.listdir(image_folder)):
        if filename.endswith(".jpg") or filename.endswith(".png"):
            image_path = os.path.join(image_folder, filename)
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
                
                response = openai.ChatCompletion.create(
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
            
            description = response["choices"][0]["message"]["content"]
            descriptions[filename] = description
            
            # Agregar conteo de tokens
            tokens_used = response["usage"]["total_tokens"]
            total_tokens += tokens_used
            print(f"Procesado: {filename} - Tokens usados: {tokens_used}")
    
    print(f"Total de tokens usados: {total_tokens}")
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(descriptions, f, indent=4, ensure_ascii=False)
    
    print("Audiodescripciones guardadas en", output_json)
    return descriptions

def summarize_audiodescriptions(api_key, descriptions_json, video_duration, output_json="video_summary.json"):
    openai.api_key = api_key
    
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
        f"Para cada descripción, indica qué mecanismos de atención fueron utilizados.\n\n"
        f"Pautas obligatorias:\n"
        f"- Usa tiempo presente y voz activa\n"
        f"- NO menciones textos, créditos o elementos escritos\n"
        f"- Describe de lo general a lo específico\n"
        f"- Mantén un tono objetivo y neutral\n"
        f"- Usa oraciones completas y vocabulario claro\n"
        f"- Sé conciso, evitando detalles innecesarios\n"
        f"- Al final de la descripción, lista los mecanismos de atención utilizados"
    )
    
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": combined_text}
        ]
    )
    
    summary = response["choices"][0]["message"]["content"]
    tokens_used = response["usage"]["total_tokens"]
    print(f"Tokens usados en el resumen: {tokens_used}")
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary}, f, indent=4, ensure_ascii=False)
    
    print("Resumen del video guardado en", output_json)
    return summary

def prepare_images_for_analysis(image_folder):
    frames = []
    for image_file in sorted(os.listdir(image_folder)):
        if image_file.endswith(('.jpg', '.png', '.jpeg')):
            image_path = os.path.join(image_folder, image_file)
            # Aquí cargaríamos la imagen para el análisis
            frames.append(image_path)
    return frames

def analyze_prosody(api_key, image_folder, descriptions_json, video_duration):
    openai.api_key = api_key
    frames = prepare_images_for_analysis(image_folder)
    with open(descriptions_json, "r", encoding="utf-8") as f:
        descriptions = json.load(f)
    
    # Analizar las imágenes y las descripciones para sugerir un tono
    combined_text = " ".join(descriptions.values())
    
    # Solicitar a la IA que analice el tono de prosodia adecuado para el video completo
    tone_prompt = (
    f"Analiza las siguientes imágenes de frames del video y el resumen para determinar el tono de prosodia más adecuado:\n\n"
    f"Resumen del video: {combined_text}\n"
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

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": tone_prompt},
            {"role": "user", "content": "Proporcione una sugerencia de tono de prosodia para este video"}
        ]
    )
    
    prosody_suggestion = response["choices"][0]["message"]["content"]
    tokens_used = response["usage"]["total_tokens"]
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
    output_json = "prosody_analysis.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(prosody_json, f, indent=4, ensure_ascii=False)
    
    print("Análisis de prosodia guardado en:", output_json)
    return prosody_json

if __name__ == "__main__":
    video_file = "za-9mBZyNfQ_330_336.avi"  # Cambiar por el nombre del video
    api_key = "YOUR_API_KEY"
     
    # Detectar cambios de escena
    scene_times = detect_scene_changes(video_file, scene_output_folder="scenes")
    print(f"Cortes de escena detectados en los tiempos: {scene_times}")
    
    # Extraer los keyframes de las escenas detectadas
    keyframes, video_duration = extract_keyframes_from_scenes(video_file, scene_times)
    print("Keyframes seleccionados en los fotogramas:", keyframes)
    print("Duración del video (segundos):", video_duration)
    
    #if len(keyframes) > 0:
        #generate_audiodescriptions(api_key, "allframes")
    #summarize_audiodescriptions(api_key, "audiodescriptions.json", video_duration)
    #analyze_prosody(api_key, "allframes", "video_summary.json", video_duration)