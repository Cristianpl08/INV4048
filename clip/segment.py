import torch
import clip
import cv2
import os
import numpy as np
from PIL import Image

def extract_keyframes(video_path, output_folder="keyframes2"):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
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
        return []
    
    frames_tensor = torch.cat([f[0] for f in frames])
    with torch.no_grad():
        image_features = model.encode_image(frames_tensor)
    
    image_features /= image_features.norm(dim=-1, keepdim=True)
    similarities = torch.mm(image_features, image_features.T)
    diversity_scores = similarities.sum(dim=1)
    
    num_keyframes = 7  # Seleccionar siempre 7 keyframes
    keyframe_indices = torch.argsort(diversity_scores)[:num_keyframes]
    
    selected_frames = [frames[idx] for idx in keyframe_indices.cpu().numpy()]
    
    os.makedirs(output_folder, exist_ok=True)
    for idx, (_, frame, frame_num) in enumerate(selected_frames):
        frame_path = os.path.join(output_folder, f"keyframe_{frame_num}.jpg")
        Image.fromarray(frame).save(frame_path, format="JPEG", quality=95)  # Guardar correctamente en RGB
    
    return [frame[2] for frame in selected_frames]

if __name__ == "__main__":
    video_file = "za-9mBZyNfQ_330_336.avi"  # Cambiar por el nombre del video
    keyframes = extract_keyframes(video_file)
    print("Keyframes seleccionados en los fotogramas:", keyframes)
