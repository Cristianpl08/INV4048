#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para crear una estructura de ejemplo para probar el nuevo flujo con segmentos.
Este script crea carpetas de ejemplo con la estructura esperada:

temp/
├── segment_001_00s/
│   ├── keyframes/
│   ├── audiodescriptions.json
│   ├── prosody_analysis.json
│   ├── video_summary.json
│   ├── audio.wav
│   ├── diarization.json
│   ├── segment_000.json
│   └── silent_segments_joined/
└── segment_002_45s/
    ├── keyframes/
    ├── audiodescriptions.json
    ├── prosody_analysis.json
    ├── video_summary.json
    ├── audio.wav
    ├── diarization.json
    ├── segment_000.json
    └── silent_segments_joined/
"""

import os
import json
from datetime import datetime

def create_example_structure(base_temp_dir="temp"):
    """Crea una estructura de ejemplo para probar el nuevo flujo"""
    
    print("=== CREANDO ESTRUCTURA DE EJEMPLO ===")
    
    # Datos de ejemplo para los segmentos
    segments_data = [
        {
            "name": "segment_001_00s",
            "start_time": "00:00",
            "summary": "En esta escena inicial vemos una persona caminando por un parque durante una tarde soleada. Los árboles están llenos de hojas verdes y se puede observar un ambiente tranquilo y relajante.",
            "emotion": "tranquilidad",
            "keyframes_count": 5
        },
        {
            "name": "segment_002_45s", 
            "start_time": "00:45",
            "summary": "La cámara se enfoca en un primer plano del protagonista quien muestra una expresión de sorpresa al descubrir algo inesperado en su camino. Su rostro refleja asombro y curiosidad.",
            "emotion": "asombro",
            "keyframes_count": 3
        }
    ]
    
    # Crear estructura para cada segmento
    for segment_data in segments_data:
        segment_path = os.path.join(base_temp_dir, segment_data["name"])
        
        print(f"\n📁 Creando segmento: {segment_data['name']}")
        
        # Crear carpeta principal del segmento
        os.makedirs(segment_path, exist_ok=True)
        
        # Crear subcarpetas
        subcarpetas = ["keyframes", "silent_segments_joined"]
        for subcarpeta in subcarpetas:
            os.makedirs(os.path.join(segment_path, subcarpeta), exist_ok=True)
            print(f"  📂 {subcarpeta}/")
        
        # Crear archivo video_summary.json
        video_summary = {
            "main_summary": segment_data["summary"],
            "segment_id": segment_data["name"],
            "start_time": segment_data["start_time"],
            "processing_date": datetime.now().isoformat(),
            "word_count": len(segment_data["summary"].split()),
            "character_count": len(segment_data["summary"])
        }
        
        summary_path = os.path.join(segment_path, "video_summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(video_summary, f, ensure_ascii=False, indent=2)
        print(f"  ✅ video_summary.json")
        
        # Crear archivo prosody_analysis.json
        prosody_analysis = {
            "complementary_emotion": segment_data["emotion"],
            "primary_emotion": segment_data["emotion"],
            "confidence_score": 0.85,
            "analysis_timestamp": datetime.now().isoformat(),
            "segment_duration": 45.0,
            "emotional_intensity": "medium",
            "recommended_voice_parameters": {
                "speed": "normal",
                "pitch": "medium",
                "volume": "normal"
            }
        }
        
        prosody_path = os.path.join(segment_path, "prosody_analysis.json")
        with open(prosody_path, 'w', encoding='utf-8') as f:
            json.dump(prosody_analysis, f, ensure_ascii=False, indent=2)
        print(f"  ✅ prosody_analysis.json")
        
        # Crear archivo audiodescriptions.json
        audiodescriptions = {
            "segment_id": segment_data["name"],
            "descriptions": [
                {
                    "timestamp": "00:00",
                    "description": segment_data["summary"][:100] + "...",
                    "confidence": 0.9
                }
            ],
            "total_descriptions": 1,
            "processing_metadata": {
                "model_used": "example_model",
                "processing_time": "2.5s"
            }
        }
        
        audiodesc_path = os.path.join(segment_path, "audiodescriptions.json")
        with open(audiodesc_path, 'w', encoding='utf-8') as f:
            json.dump(audiodescriptions, f, ensure_ascii=False, indent=2)
        print(f"  ✅ audiodescriptions.json")
        
        # Crear archivo diarization.json
        diarization = {
            "speakers": ["SPEAKER_001", "SPEAKER_002"],
            "segments": [
                {
                    "start": 0.0,
                    "end": 45.0,
                    "speaker": "SPEAKER_001",
                    "confidence": 0.95
                }
            ],
            "total_speakers": 2
        }
        
        diarization_path = os.path.join(segment_path, "diarization.json")
        with open(diarization_path, 'w', encoding='utf-8') as f:
            json.dump(diarization, f, ensure_ascii=False, indent=2)
        print(f"  ✅ diarization.json")
        
        # Crear archivo segment_000.json
        segment_info = {
            "segment_number": 0,
            "start_time": 0.0,
            "end_time": 45.0,
            "duration": 45.0,
            "video_file": f"{segment_data['name']}.mp4",
            "metadata": {
                "resolution": "1920x1080",
                "fps": 30,
                "created": datetime.now().isoformat()
            }
        }
        
        segment_info_path = os.path.join(segment_path, "segment_000.json")
        with open(segment_info_path, 'w', encoding='utf-8') as f:
            json.dump(segment_info, f, ensure_ascii=False, indent=2)
        print(f"  ✅ segment_000.json")
        
        # Crear archivos en silent_segments_joined/
        silent_segments_path = os.path.join(segment_path, "silent_segments_joined")
        
        # silent_segments_with_speaker_001.json
        silent_segments_speaker = {
            "speaker": "SPEAKER_001",
            "silent_segments": [
                {"start": 10.0, "end": 15.0, "duration": 5.0},
                {"start": 30.0, "end": 35.0, "duration": 5.0}
            ],
            "total_silent_time": 10.0
        }
        
        silent_speaker_path = os.path.join(silent_segments_path, "silent_segments_with_speaker_001.json")
        with open(silent_speaker_path, 'w', encoding='utf-8') as f:
            json.dump(silent_segments_speaker, f, ensure_ascii=False, indent=2)
        print(f"  ✅ silent_segments_joined/silent_segments_with_speaker_001.json")
        
        # speaker_SPEAKER_001.json y speaker_SPEAKER_002.json
        for speaker_id in ["SPEAKER_001", "SPEAKER_002"]:
            speaker_data = {
                "speaker_id": speaker_id,
                "total_speaking_time": 20.0 if speaker_id == "SPEAKER_001" else 15.0,
                "segments": [
                    {
                        "start": 0.0 if speaker_id == "SPEAKER_001" else 20.0,
                        "end": 20.0 if speaker_id == "SPEAKER_001" else 35.0,
                        "confidence": 0.95
                    }
                ]
            }
            
            speaker_path = os.path.join(silent_segments_path, f"speaker_{speaker_id}.json")
            with open(speaker_path, 'w', encoding='utf-8') as f:
                json.dump(speaker_data, f, ensure_ascii=False, indent=2)
            print(f"  ✅ silent_segments_joined/speaker_{speaker_id}.json")
        
        # Crear archivo de audio de ejemplo (placeholder)
        audio_path = os.path.join(segment_path, "audio.wav")
        with open(audio_path, 'wb') as f:
            # Escribir un header WAV básico como placeholder
            f.write(b'RIFF')
            f.write((36).to_bytes(4, 'little'))
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write((16).to_bytes(4, 'little'))
            f.write((1).to_bytes(2, 'little'))  # PCM
            f.write((1).to_bytes(2, 'little'))  # Mono
            f.write((44100).to_bytes(4, 'little'))  # Sample rate
            f.write((88200).to_bytes(4, 'little'))  # Byte rate
            f.write((2).to_bytes(2, 'little'))  # Block align
            f.write((16).to_bytes(2, 'little'))  # Bits per sample
            f.write(b'data')
            f.write((0).to_bytes(4, 'little'))  # Data size
        print(f"  ✅ audio.wav (placeholder)")
        
        # Crear keyframes de ejemplo
        keyframes_path = os.path.join(segment_path, "keyframes")
        for i in range(segment_data["keyframes_count"]):
            keyframe_file = os.path.join(keyframes_path, f"keyframe_{i:03d}.jpg")
            with open(keyframe_file, 'wb') as f:
                # Escribir un header JPEG básico como placeholder
                f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00')
                f.write(b'\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c ')
                f.write(b'$.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4')
                f.write(b'\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda')
                f.write(b'\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\x00\xff\xd9')
            print(f"  🖼️ keyframes/keyframe_{i:03d}.jpg")
    
    # Crear carpetas de salida adicionales
    output_dirs = ["temp_output", "evaluacion_prosodica", "mezclas_finales"]
    for output_dir in output_dirs:
        output_path = os.path.join(base_temp_dir, output_dir)
        os.makedirs(output_path, exist_ok=True)
        print(f"\n📂 {output_dir}/")
    
    print(f"\n✅ ESTRUCTURA DE EJEMPLO CREADA EXITOSAMENTE")
    print(f"📁 Directorio base: {os.path.abspath(base_temp_dir)}")
    print(f"🔧 Segmentos creados: {len(segments_data)}")
    print("\n📋 Para probar el flujo, ejecuta:")
    print("from Narrations_ducking import cargar_tareas_locales, procesar_generacion_local")
    print("tareas = cargar_tareas_locales('temp')")
    print("print(f'Tareas encontradas: {len(tareas)}')")

if __name__ == "__main__":
    create_example_structure()
