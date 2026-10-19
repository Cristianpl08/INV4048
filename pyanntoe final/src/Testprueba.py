import os
import time
import json
import requests
from moviepy.video.io.VideoFileClip import VideoFileClip
from pydub import AudioSegment
from pyannoteai.sdk import Client
import cv2
from scenedetect import detect, ContentDetector

# Configure PYANNOTE_API_TOKEN in your environment before running the script.
API_TOKEN = os.environ.get("PYANNOTE_API_TOKEN")
if not API_TOKEN:
    raise RuntimeError(
        "PYANNOTE_API_TOKEN is not set. Copy .env.example and export a valid token."
    )

# 1. Extraer audio del video local
def extract_audio(video_path, audio_path):
    video = VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path, codec='pcm_s16le')
    print(f"Audio extraído en: {audio_path}")

# 2. Subir el audio y diarizar usando el SDK oficial
def diarize_with_sdk(audio_path):
    client = Client(API_TOKEN)
    media_url = client.upload(audio_path)
    job_id = client.diarize(media_url)
    print("Esperando resultado de diarización...")
    while True:
        job = client.retrieve(job_id)
        if job["status"] == "succeeded":
            print("¡Diarización completada!")
            return job["output"]["diarization"]
        elif job["status"] in ["failed", "canceled"]:
            raise Exception("Job failed or canceled")
        time.sleep(5)

# 3. Guardar la diarización en JSON
def save_json(data, filename):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Resultado guardado en {filename}")

# 4. Diarización inversa: reconstruir audios por hablante
def split_speakers(audio_path, diarization_json):
    audio = AudioSegment.from_wav(audio_path)
    speakers = {}
    for segment in diarization_json:
        speaker = segment["speaker"]
        start = int(segment["start"] * 1000)
        end = int(segment["end"] * 1000)
        if speaker not in speakers:
            speakers[speaker] = AudioSegment.empty()
        speakers[speaker] += audio[start:end]
    for speaker, seg_audio in speakers.items():
        out_path = f"speaker_{speaker}.wav"
        seg_audio.export(out_path, format="wav")
        print(f"Audio de {speaker} guardado en {out_path}")

def find_silent_segments(diarization_json, audio_duration=None):
    """
    Encuentra segmentos sin hablantes (silencios) y les asigna un número de identificación.
    Retorna una lista con 'id', 'start', 'end' y 'duration'.
    """
    # Ordenar los segmentos por tiempo de inicio
    segments = sorted(diarization_json, key=lambda x: x["start"])
    
    silent_segments = []
    segment_id = 1

    # Silencio inicial si el primer hablante no empieza en 0
    if segments[0]["start"] > 0:
        silent_segments.append({
            "id": segment_id,
            "start": 0.0,
            "end": segments[0]["start"],
            "duration": round(segments[0]["start"] - 0.0, 3)
        })
        segment_id += 1

    # Silencios entre los segmentos
    for i in range(len(segments) - 1):
        current_end = segments[i]["end"]
        next_start = segments[i + 1]["start"]
        if next_start > current_end:
            silent_segments.append({
                "id": segment_id,
                "start": current_end,
                "end": next_start,
                "duration": round(next_start - current_end, 3)
            })
            segment_id += 1

    # Silencio final si se conoce la duración del audio
    if audio_duration and segments[-1]["end"] < audio_duration:
        silent_segments.append({
            "id": segment_id,
            "start": segments[-1]["end"],
            "end": audio_duration,
            "duration": round(audio_duration - segments[-1]["end"], 3)
        })

    return silent_segments

def join_close_segments(silent_segments, video_path, max_gap=2.0):
    """
    Une segmentos que están muy cerca (gap <= max_gap segundos) y verifica si hay cambios de escena.
    Si hay cambio de escena en el segmento unido, los separa de nuevo.
    """
    print(f"Uniendo segmentos con gap <= {max_gap} segundos...")
    
    # Detectar todas las escenas del video
    scenes = detect(video_path, ContentDetector(threshold=27.0))
    scene_times = [(scene[0].get_seconds(), scene[1].get_seconds()) for scene in scenes]
    
    joined_segments = []
    i = 0
    
    while i < len(silent_segments):
        current_segment = silent_segments[i].copy()
        segments_to_join = [current_segment]
        
        # Buscar segmentos consecutivos que estén muy cerca
        j = i + 1
        while j < len(silent_segments):
            gap = silent_segments[j]["start"] - current_segment["end"]
            if gap <= max_gap:
                segments_to_join.append(silent_segments[j].copy())
                current_segment = silent_segments[j]
                j += 1
            else:
                break
        
        # Si solo hay un segmento, agregarlo directamente
        if len(segments_to_join) == 1:
            joined_segments.append(segments_to_join[0])
            i += 1
        else:
            # Unir los segmentos
            joined_start = segments_to_join[0]["start"]
            joined_end = segments_to_join[-1]["end"]
            joined_duration = joined_end - joined_start
            
            # Verificar si hay cambios de escena en el segmento unido
            has_scene_change = False
            for scene_start, scene_end in scene_times:
                # Verificar si hay un cambio de escena dentro del segmento unido
                if (scene_start > joined_start and scene_start < joined_end):
                    has_scene_change = True
                    break
            
            if has_scene_change:
                print(f"Cambio de escena detectado en segmento unido {joined_start:.3f}s - {joined_end:.3f}s, manteniendo separados")
                # Mantener los segmentos separados
                joined_segments.extend(segments_to_join)
            else:
                print(f"Uniendo segmentos {joined_start:.3f}s - {joined_end:.3f}s (sin cambios de escena)")
                # Crear el segmento unido
                joined_segment = {
                    "id": len(joined_segments) + 1,
                    "start": joined_start,
                    "end": joined_end,
                    "duration": round(joined_duration, 3),
                    "joined_from": [seg["id"] for seg in segments_to_join]
                }
                joined_segments.append(joined_segment)
            
            i = j
    
    # Reasignar IDs secuenciales
    for idx, segment in enumerate(joined_segments, start=1):
        segment["id"] = idx
    
    return joined_segments

def detect_scene_changes_in_segments(video_path, silent_segments, min_scene_duration=2.0):
    """
    Detecta cambios de escena dentro de los segmentos silenciosos.
    Si un segmento contiene múltiples escenas, lo divide en sub-segmentos.
    """
    print("Detectando cambios de escena en el video...")
    
    # Detectar todas las escenas del video usando la API moderna
    scenes = detect(video_path, ContentDetector(threshold=27.0))
    
    # Convertir las escenas a una lista de tiempos
    scene_times = []
    for scene in scenes:
        start_time = scene[0].get_seconds()
        end_time = scene[1].get_seconds()
        scene_times.append((start_time, end_time))
    
    print(f"Detectadas {len(scene_times)} escenas en total")
    
    # Procesar cada segmento silencioso
    processed_segments = []
    
    for segment in silent_segments:
        segment_start = segment["start"]
        segment_end = segment["end"]
        segment_duration = segment["duration"]
        
        # Encontrar escenas que se superponen con este segmento
        overlapping_scenes = []
        for scene_start, scene_end in scene_times:
            # Verificar si hay superposición
            if (scene_start < segment_end and scene_end > segment_start):
                # Calcular la intersección
                overlap_start = max(scene_start, segment_start)
                overlap_end = min(scene_end, segment_end)
                if overlap_end > overlap_start:
                    overlapping_scenes.append((overlap_start, overlap_end))
        
        # Si no hay escenas superpuestas o solo una, mantener el segmento original
        if len(overlapping_scenes) <= 1:
            processed_segments.append(segment)
        else:
            # Dividir el segmento en sub-segmentos basados en las escenas
            sub_segments = []
            current_id = segment["id"]
            
            for i, (scene_start, scene_end) in enumerate(overlapping_scenes):
                sub_duration = scene_end - scene_start
                
                # Solo incluir sub-segmentos con duración mayor a min_scene_duration
                if sub_duration >= min_scene_duration:
                    sub_segments.append({
                        "id": f"{current_id}_{i+1}",
                        "start": round(scene_start, 3),
                        "end": round(scene_end, 3),
                        "duration": round(sub_duration, 3),
                        "original_segment_id": current_id,
                        "scene_number": i + 1
                    })
            
            # Si no se generaron sub-segmentos válidos, mantener el original
            if not sub_segments:
                processed_segments.append(segment)
            else:
                processed_segments.extend(sub_segments)
    
    # Reasignar IDs secuenciales
    for idx, segment in enumerate(processed_segments, start=1):
        segment["id"] = idx
    
    return processed_segments

# FLUJO COMPLETO
if __name__ == "__main__":
    video_file = "recortado.mov"
    audio_file = "audio.wav"
    diarization_json_file = "diarization.json"
    

    # Paso 1: Extraer audio
    extract_audio(video_file, audio_file)

    # Paso 2 y 3: Subir audio y diarizar
    diarization = diarize_with_sdk(audio_file)

    # Paso 4: Guardar resultado
    save_json(diarization, diarization_json_file)

    # Paso 5: Diarización inversa
    split_speakers(audio_file, diarization)
    
    audio_duration = AudioSegment.from_wav(audio_file).duration_seconds
    silent_segments = find_silent_segments(diarization, audio_duration)

    # Filtrar solo los silencios mayores a 2 segundos
    long_silent_segments = [s for s in silent_segments if s["duration"] > 2.0]

    # Reasignar IDs de forma secuencial
    for idx, segment in enumerate(long_silent_segments, start=1):
        segment["id"] = idx

    # Paso 6: Unir segmentos cercanos y verificar cambios de escena
    joined_segments = join_close_segments(long_silent_segments, video_file, max_gap=2.0)
    save_json(joined_segments, "silent_segments_joined.json")
    print(f"Segmentos después de unir cercanos: {len(joined_segments)}")

    # Paso 7: Detectar cambios de escena dentro de los segmentos
    print("Procesando cambios de escena en segmentos silenciosos...")
    final_segments = detect_scene_changes_in_segments(video_file, joined_segments, min_scene_duration=2.0)

    # Paso 8: Guardar los segmentos finales con información de escenas
    save_json(final_segments, "silent_segments_with_scenes.json")
    print(f"Procesamiento completado. {len(final_segments)} segmentos finales generados.")
    print("Segmentos con cambios de escena:")
    for segment in final_segments:
        if "scene_number" in segment:
            print(f"  Segmento {segment['id']}: {segment['start']:.3f}s - {segment['end']:.3f}s (Escena {segment['scene_number']})")
        else:
            print(f"  Segmento {segment['id']}: {segment['start']:.3f}s - {segment['end']:.3f}s")
