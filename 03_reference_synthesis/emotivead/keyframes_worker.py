"""Isolated CLIP worker preserving original ViT-B/32 diversity ranking."""
import json
import math
import sys
from pathlib import Path


def select_indices(features, minimum=5, maximum=15):
    import numpy as np
    features = np.asarray(features, dtype=float)
    features /= np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-12)
    scores = (features @ features.T).sum(axis=1)
    # Sorting sums is equivalent to the old min-max ranking, without division by zero.
    count = len(features) if len(features) <= minimum else min(maximum, max(minimum, len(features)//2))
    return sorted(np.argsort(scores, kind='stable')[:count].tolist())


def main():
    import cv2
    import numpy as np
    import torch
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model_id = 'openai/clip-vit-base-patch32'
    model = CLIPModel.from_pretrained(model_id).to(device).eval()
    processor = CLIPProcessor.from_pretrained(model_id)
    cap = cv2.VideoCapture(request['video'])
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps <= 0:
        raise ValueError('CLIP no puede abrir el video o leer FPS.')
    try:
        for seg in request['segments']:
            numbers, images, vectors = [], [], []
            for frame_number in range(math.ceil(seg['start']*fps), max(math.ceil(seg['start']*fps)+1, int(seg['end']*fps)), 30):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ok, frame = cap.read()
                if not ok: continue
                images.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
                numbers.append(frame_number)
            if not images: raise ValueError('Segmento sin fotogramas decodificables.')
            for start in range(0, len(images), 8):
                batch = processor(images=images[start:start+8], return_tensors='pt').to(device)
                with torch.inference_mode():
                    vectors.extend(model.get_image_features(**batch).float().cpu().numpy())
            chosen = select_indices(np.asarray(vectors))
            folder = Path(request['output'])/seg['id']/'keyframes'
            folder.mkdir(parents=True, exist_ok=True)
            index = []
            for i in chosen:
                path = folder/f'keyframe_{numbers[i]}.jpg'
                images[i].thumbnail((1024, 1024))
                images[i].save(path, quality=95)
                index.append({'filename': path.name, 'frame_number': numbers[i],
                              'timestamp': numbers[i]/fps, 'timestamp_relative': numbers[i]/fps-seg['start'],
                              'model': model_id})
            (folder/'keyframes.json').write_text(json.dumps(index, indent=2), encoding='utf-8')
    finally:
        cap.release()


if __name__ == '__main__': main()
