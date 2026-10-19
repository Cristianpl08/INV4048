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
    
    # Crear diccionario para el JSON
    scenes_data = {
        "video_path": video_path,
        "total_scenes": len(scene_times),
        "scene_changes": [
            {
                "scene_number": idx + 1,
                "timestamp": time,
                "timestamp_formatted": str(datetime.timedelta(seconds=int(time)))
            }
            for idx, time in enumerate(scene_times)
        ]
    }
    
    # Guardar el JSON
    json_path = os.path.join(scene_output_folder, "scene_changes.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(scenes_data, f, indent=4)
    
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

def extract_keyframes_from_scenes(video_path, scene_times, output_folder="zYcY4mjLpxU_45_55"):
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


if __name__ == "__main__":
    video_file = "videosescenas/zYcY4mjLpxU_45_55.avi"  # Cambiar por el nombre del video
   
     

    scene_times = detect_scene_changes(video_file, scene_output_folder="scenes")
    print(f"Cortes de escena detectados en los tiempos: {scene_times}")
    

    keyframes, video_duration = extract_keyframes_from_scenes(video_file, scene_times)
    print("Keyframes seleccionados en los fotogramas:", keyframes)
    print("Duración del video (segundos):", video_duration)
    
