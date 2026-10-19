import os
import time
import json
import subprocess
import shutil
from flask import Flask, request, jsonify
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from pymongo import MongoClient
from moviepy import VideoFileClip
from Descriptions import process_video

# Importar funciones para generación de audiodescripciones
try:
    import sys
    import importlib.util
    
    # Verificar si el archivo existe
    narrations_path = os.path.join(os.path.dirname(__file__), 'Narrations_ducking.py')
    if os.path.exists(narrations_path):
        sys.path.append('.')
        from Narrations_ducking import (
            cargar_tareas_locales, 
            procesar_generacion_local,
            ejecutar_analisis_completo_local,
            mezclar_audios_con_ffmpeg_local,
            TEMP_BASE_DIR,
            LOCAL_OUTPUT_DIR
        )
        NARRATIONS_AVAILABLE = True
        print("✅ Módulo de generación de audiodescripciones cargado exitosamente")
    else:
        raise ImportError("Archivo Narrations_ducking.py no encontrado")
        
except Exception as e:
    NARRATIONS_AVAILABLE = False
    print(f"⚠️ No se pudo cargar el módulo de audiodescripciones: {e}")
    print("Las audiodescripciones no estarán disponibles en este flujo")

app = Flask(__name__)

CLIENT_ID = '448213662107-7fuh61iinmeg78df9epa6ve54qm7mn2o.apps.googleusercontent.com'
CLIENT_SECRET = 'YOUR_GOOGLE_OAUTH_CLIENT_SECRET'
REFRESH_TOKEN = 'YOUR_GOOGLE_OAUTH_REFRESH_TOKEN'

# OpenAI API Key (agregar tu propia API key aquí)
OPENAI_API_KEY = "YOUR_API_KEY"

# MongoDB connection
MONGO_URI = "mongodb+srv://<username>:<password>@<cluster>/<database>"
mongo_client = MongoClient(MONGO_URI)
db = mongo_client['database']
projects_collection = db['projects']

def process_video_descriptions(temp_dir, segment_files):
    """Procesa las descripciones para todos los segmentos de video en la nueva estructura"""
    try:
        print("=== INICIANDO PROCESAMIENTO DE DESCRIPCIONES CON NUEVA ESTRUCTURA ===")
        
        description_results = []
        successful_descriptions = 0
        failed_descriptions = 0
        
        for segment_file in segment_files:
            try:
                print(f"\nProcesando descripciones para: {segment_file}")
                
                # Ruta completa del segmento de video
                segment_path = os.path.join(temp_dir, segment_file)
                
                # Crear carpeta de segmento con la nueva estructura
                # Extraer el nombre base del segmento (sin extensión)
                segment_name = os.path.splitext(segment_file)[0]
                
                # Crear carpeta del segmento (ej: temp/segment_001_00s/)
                segment_folder = os.path.join(temp_dir, segment_name)
                os.makedirs(segment_folder, exist_ok=True)
                
                print(f"  📁 Creada carpeta de segmento: {segment_folder}")
                
                # Procesar el video y generar descripciones directamente en la carpeta del segmento
                result_folder = process_video(
                    video_path=segment_path,
                    output_base_folder=segment_folder,
                    api_key=OPENAI_API_KEY
                )
                
                if result_folder:
                    # Verificar que se generaron los archivos esperados
                    expected_files = ['video_summary.json', 'prosody_analysis.json', 'audiodescriptions.json']
                    generated_files = []
                    
                    for expected_file in expected_files:
                        file_path = os.path.join(segment_folder, expected_file)
                        if os.path.exists(file_path):
                            generated_files.append(expected_file)
                            print(f"    ✅ Generado: {expected_file}")
                        else:
                            print(f"    ⚠️ No encontrado: {expected_file}")
                    
                    # Mover también otros archivos importantes a la carpeta del segmento
                    # si process_video los generó en una subcarpeta
                    if result_folder != segment_folder and os.path.exists(result_folder):
                        print(f"  🔄 Moviendo archivos desde {result_folder} a {segment_folder}")
                        for file_name in os.listdir(result_folder):
                            src_path = os.path.join(result_folder, file_name)
                            dst_path = os.path.join(segment_folder, file_name)
                            if os.path.isfile(src_path) and not os.path.exists(dst_path):
                                shutil.copy2(src_path, dst_path)
                                print(f"    📋 Copiado: {file_name}")
                    
                    description_results.append({
                        'segment_file': segment_file,
                        'segment_folder': segment_folder,
                        'generated_files': generated_files,
                        'status': 'success'
                    })
                    successful_descriptions += 1
                    print(f"✓ Descripciones generadas exitosamente para {segment_file}")
                    print(f"  📂 Carpeta de salida: {segment_folder}")
                    
                else:
                    description_results.append({
                        'segment_file': segment_file,
                        'segment_folder': segment_folder,
                        'status': 'failed',
                        'error': 'process_video returned None'
                    })
                    failed_descriptions += 1
                    print(f"✗ Error procesando descripciones para {segment_file}")
                    
            except Exception as segment_error:
                error_msg = f"Error procesando descripciones para {segment_file}: {str(segment_error)}"
                print(error_msg)
                description_results.append({
                    'segment_file': segment_file,
                    'segment_folder': os.path.join(temp_dir, os.path.splitext(segment_file)[0]),
                    'status': 'failed',
                    'error': error_msg
                })
                failed_descriptions += 1
        
        # Mostrar resumen del procesamiento de descripciones
        total_processed = successful_descriptions + failed_descriptions
        print(f"\n=== RESUMEN PROCESAMIENTO DE DESCRIPCIONES ===")
        print(f"Total segmentos procesados: {total_processed}")
        print(f"Exitosos: {successful_descriptions}")
        print(f"Fallidos: {failed_descriptions}")
        
        # Mostrar estructura final generada
        print(f"\n=== ESTRUCTURA GENERADA ===")
        for result in description_results:
            if result['status'] == 'success':
                print(f"📁 {result['segment_folder']}/")
                if os.path.exists(result['segment_folder']):
                    for item in os.listdir(result['segment_folder']):
                        print(f"  📄 {item}")
        print("=" * 50)
        
        return description_results
        
    except Exception as e:
        print(f"Error general en procesamiento de descripciones: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def process_audio_descriptions(temp_dir, project_id):
    """Procesa las audiodescripciones después de generar las descripciones con nueva estructura"""
    if not NARRATIONS_AVAILABLE:
        print("⚠️ Módulo de generación de audiodescripciones no disponible. Saltando...")
        return {
            'status': 'skipped',
            'reason': 'Narrations module not available',
            'audio_files': [],
            'analysis_files': [],
            'mix_files': []
        }
    
    try:
        print("\n=== INICIANDO PROCESAMIENTO DE AUDIODESCRIPCIONES CON NUEVA ESTRUCTURA ===")
        
        # Verificar que existan carpetas de segmentos con la nueva estructura
        segment_folders = []
        if os.path.exists(temp_dir):
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if (item.startswith('segment_') and item.endswith('s') and 
                    os.path.isdir(item_path)):
                    # Verificar que tenga los archivos necesarios
                    summary_file = os.path.join(item_path, 'video_summary.json')
                    prosody_file = os.path.join(item_path, 'prosody_analysis.json')
                    if os.path.exists(summary_file) and os.path.exists(prosody_file):
                        segment_folders.append(item)
                        print(f"  ✅ Segmento válido encontrado: {item}")
                    else:
                        print(f"  ⚠️ Segmento incompleto: {item} (faltan archivos JSON)")
        
        # Fallback: buscar carpetas de descripciones del método anterior
        if not segment_folders:
            print("No se encontraron carpetas de segmentos válidas, buscando carpetas de descripciones...")
            for item in os.listdir(temp_dir):
                if item.endswith('_descriptions') and os.path.isdir(os.path.join(temp_dir, item)):
                    segment_folders.append(item)
        
        if not segment_folders:
            print("⚠️ No se encontraron carpetas de segmentos o descripciones válidas")
            print(f"📂 Contenido de {temp_dir}:")
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path):
                    print(f"  📁 {item}/")
                    for subitem in os.listdir(item_path):
                        print(f"    📄 {subitem}")
                else:
                    print(f"  📄 {item}")
            return {
                'status': 'no_segments',
                'reason': 'No valid segment folders found',
                'audio_files': [],
                'analysis_files': [],
                'mix_files': []
            }
        
        print(f"🎯 Encontradas {len(segment_folders)} carpetas de segmentos para procesar:")
        for folder in segment_folders:
            print(f"  - {folder}")
        
        # Configurar el directorio base temporal para este proyecto
        project_temp_dir = temp_dir
        
        # Crear estructura de carpetas necesarias
        os.makedirs(os.path.join(project_temp_dir, "temp_output"), exist_ok=True)
        
        # 1. Cargar tareas desde archivos locales
        print("PASO AD-1: Cargando tareas de generación desde nueva estructura...")
        
        # Temporalmente cambiar la función para trabajar con el directorio del proyecto
        import Narrations_ducking
        original_temp_base = getattr(Narrations_ducking, 'TEMP_BASE_DIR', project_temp_dir)
        original_local_output = getattr(Narrations_ducking, 'LOCAL_OUTPUT_DIR', os.path.join(project_temp_dir, "temp_output"))
        
        # Actualizar rutas para este proyecto específico
        Narrations_ducking.TEMP_BASE_DIR = project_temp_dir
        Narrations_ducking.LOCAL_OUTPUT_DIR = os.path.join(project_temp_dir, "temp_output")
        
        try:
            # Cargar tareas desde las descripciones generadas
            print(f"📁 Buscando tareas en directorio: {project_temp_dir}")
            print(f"📁 Segmentos disponibles: {segment_folders}")
            
            tareas = cargar_tareas_locales(project_temp_dir)
            
            if not tareas:
                print("⚠️ No se encontraron tareas válidas para procesar audiodescripciones")
                print("🔍 Verificando estructura de carpetas de segmentos:")
                for segment_folder in segment_folders:
                    segment_path = os.path.join(project_temp_dir, segment_folder)
                    print(f"  📂 {segment_folder}:")
                    if os.path.isdir(segment_path):
                        for item in os.listdir(segment_path):
                            item_path = os.path.join(segment_path, item)
                            if os.path.isdir(item_path):
                                print(f"    📁 {item}/")
                                try:
                                    for subitem in os.listdir(item_path):
                                        print(f"      📄 {subitem}")
                                except:
                                    print(f"      ❌ Error listando {item}")
                            else:
                                print(f"    📄 {item}")
                        
                return {
                    'status': 'no_tasks',
                    'reason': 'No valid description tasks found',
                    'audio_files': [],
                    'analysis_files': [],
                    'mix_files': []
                }
            
            print(f"✅ Se encontraron {len(tareas)} tareas para procesar")
            for i, tarea in enumerate(tareas):
                print(f"  📋 Tarea {i+1}: Video ID: {tarea.get('Video ID')}, Emoción: {tarea.get('Emoción')}, Texto: {tarea.get('Texto a Generar', '')[:100]}...")
            
            # 2. Procesar generación TTS
            print("PASO AD-2: Generando audios TTS...")
            print(f"🔧 Directorio de salida TTS: {Narrations_ducking.LOCAL_OUTPUT_DIR}")
            
            # Actualizar las tareas globalmente en el módulo
            Narrations_ducking.tareas_de_generacion = tareas
            
            # Verificar prerequisitos para TTS
            print("🔍 Verificando prerequisitos para TTS:")
            try:
                # Verificar si las librerías TTS están disponibles
                import torch
                print(f"  ✅ PyTorch disponible - CUDA: {torch.cuda.is_available()}")
            except ImportError as torch_error:
                print(f"  ❌ PyTorch no disponible: {torch_error}")
                
            try:
                from TTS.api import TTS
                print("  ✅ TTS API disponible")
            except ImportError as tts_error:
                print(f"  ❌ TTS API no disponible: {tts_error}")
                
            try:
                from openai import OpenAI
                print("  ✅ OpenAI API disponible")
            except ImportError as openai_error:
                print(f"  ❌ OpenAI API no disponible: {openai_error}")
            
            print("🚀 Iniciando generación TTS...")
            archivos_audio = procesar_generacion_local()
            
            print(f"📊 Resultado generación TTS:")
            print(f"  📁 Directorio verificado: {Narrations_ducking.LOCAL_OUTPUT_DIR}")
            if os.path.exists(Narrations_ducking.LOCAL_OUTPUT_DIR):
                archivos_en_directorio = os.listdir(Narrations_ducking.LOCAL_OUTPUT_DIR)
                print(f"  📄 Archivos en directorio: {archivos_en_directorio}")
            else:
                print("  ❌ Directorio de salida no existe")
                
            print(f"✅ Se generaron {len(archivos_audio)} archivos de audio")
            
            # 3. Análisis prosódico (opcional)
            analysis_files = []
            try:
                print("PASO AD-3: Ejecutando análisis prosódico...")
                df_analisis = ejecutar_analisis_completo_local()
                if df_analisis is not None:
                    # Buscar archivos de análisis generados
                    eval_dir = os.path.join(project_temp_dir, "evaluacion_prosodica")
                    if os.path.exists(eval_dir):
                        analysis_files = [f for f in os.listdir(eval_dir) if f.endswith(('.csv', '.png'))]
                    print(f"✅ Análisis prosódico completado - {len(analysis_files)} archivos generados")
                else:
                    print("⚠️ El análisis prosódico no se pudo completar")
            except Exception as analysis_error:
                print(f"⚠️ Error en análisis prosódico: {analysis_error}")
            
            # 4. Mezcla final (opcional)
            mix_files = []
            try:
                print("PASO AD-4: Ejecutando mezcla final...")
                mezclar_audios_con_ffmpeg_local(temp_dir=project_temp_dir)
                
                # Buscar archivos de mezcla generados
                mix_dir = os.path.join(project_temp_dir, "mezclas_finales")
                if os.path.exists(mix_dir):
                    mix_files = [f for f in os.listdir(mix_dir) if f.endswith('.wav')]
                    
                print(f"✅ Mezcla final completada - {len(mix_files)} archivos generados")
            except Exception as mix_error:
                print(f"⚠️ Error en mezcla final: {mix_error}")
            
            # Recopilar todos los archivos generados
            audio_files = []
            if os.path.exists(Narrations_ducking.LOCAL_OUTPUT_DIR):
                audio_files = [f for f in os.listdir(Narrations_ducking.LOCAL_OUTPUT_DIR) 
                              if f.endswith('.wav') and not f.startswith('temp_')]
            
            print(f"\n=== RESUMEN AUDIODESCRIPCIONES ===")
            print(f"Segmentos procesados: {len(segment_folders)}")
            print(f"Tareas TTS generadas: {len(tareas)}")
            print(f"Archivos TTS generados: {len(audio_files)}")
            print(f"Archivos de análisis: {len(analysis_files)}")
            print(f"Archivos de mezcla: {len(mix_files)}")
            print("=" * 40)
            
            return {
                'status': 'success',
                'audio_files': audio_files,
                'analysis_files': analysis_files,
                'mix_files': mix_files,
                'tasks_processed': len(tareas),
                'segments_processed': len(segment_folders)
            }
            
        finally:
            # Restaurar rutas originales
            Narrations_ducking.TEMP_BASE_DIR = original_temp_base
            Narrations_ducking.LOCAL_OUTPUT_DIR = original_local_output
        
    except Exception as e:
        print(f"❌ Error general en procesamiento de audiodescripciones: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'status': 'error',
            'error': str(e),
            'audio_files': [],
            'analysis_files': [],
            'mix_files': []
        }

def cut_video_segments(video_path, segments_json_path, output_dir):
    """Corta el video en segmentos basándose en silent_segments_joined.json"""
    try:
        # Leer los segmentos del archivo JSON
        with open(segments_json_path, 'r') as f:
            segments_data = json.load(f)
        
        # Cargar el video
        video = VideoFileClip(video_path)
        
        segment_files = []
        successful_segments = 0
        failed_segments = 0
        
        # Procesar cada segmento
        for i, segment in enumerate(segments_data):
            start_time = segment.get('start', 0)
            end_time = segment.get('end', 0)
            
            # Nombre del archivo de salida
            segment_filename = f"segment_{i+1:03d}_{start_time:.2f}s_{end_time:.2f}s.mp4"
            segment_path = os.path.join(output_dir, segment_filename)
            
            try:
                # Crear el clip del segmento usando subclipped (método correcto en MoviePy)
                segment_clip = video.subclipped(start_time, end_time)
                
                # Guardar el segmento con manejo de errores específico
                try:
                    segment_clip.write_videofile(segment_path)
                    segment_clip.close()
                    segment_files.append(segment_filename)
                    successful_segments += 1
                    print(f"✓ Segmento creado: {segment_filename}")
                    
                except Exception as write_error:
                    # Si falla con audio, intentar sin audio
                    if "'NoneType' object has no attribute 'stdout'" in str(write_error) or "stdout" in str(write_error):
                        try:
                            print(f"⚠ Error de audio en {segment_filename}, intentando sin audio...")
                            segment_clip_no_audio = segment_clip.without_audio()
                            segment_clip_no_audio.write_videofile(segment_path)
                            segment_clip_no_audio.close()
                            segment_files.append(segment_filename)
                            successful_segments += 1
                            print(f"✓ Segmento creado sin audio: {segment_filename}")
                        except Exception as no_audio_error:
                            print(f"✗ Error procesando segmento {segment_filename}: {str(no_audio_error)}")
                            failed_segments += 1
                    else:
                        print(f"✗ Error procesando segmento {segment_filename}: {str(write_error)}")
                        failed_segments += 1
                    
                    # Limpiar recursos
                    try:
                        segment_clip.close()
                    except:
                        pass
                        
            except Exception as segment_error:
                print(f"✗ Error creando segmento {segment_filename}: {str(segment_error)}")
                failed_segments += 1
        
        # Cerrar el video original
        video.close()
        
        # Mostrar resumen
        total_segments = successful_segments + failed_segments
        print(f"\n=== RESUMEN CORTE DE SEGMENTOS ===")
        print(f"Total segmentos procesados: {total_segments}")
        print(f"Exitosos: {successful_segments}")
        print(f"Fallidos: {failed_segments}")
        
        # Retornar los archivos exitosos (aunque algunos hayan fallado)
        if successful_segments > 0:
            return segment_files
        else:
            raise Exception("No se pudo crear ningún segmento de video")
        
    except Exception as e:
        print(f"Error cortando video en segmentos: {str(e)}")
        raise

@app.route('/upload', methods=['POST'])
def upload_file():
    print('Request form:', request.form)
    print('Request files:', request.files)
    if 'file' not in request.files:
        print('No file part in request.files')
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    print('File object:', file)
    if file.filename == '':
        print('No selected file')
        return jsonify({'error': 'No selected file'}), 400

    # 1. Crear documento en MongoDB
    project_doc = {"original_filename": file.filename, "status": "processing"}
    result = projects_collection.insert_one(project_doc)
    project_id = str(result.inserted_id)
    print('MongoDB project_id:', project_id)

    # 2. Guardar archivo temporal en carpeta segmentada por project_id
    ext = os.path.splitext(file.filename)[1]
    temp_dir = os.path.join('temp', project_id)
    os.makedirs(temp_dir, exist_ok=True)
    filename = f"{project_id}{ext}"
    filepath = os.path.join(temp_dir, filename)
    file.save(filepath)
    print('File saved to:', filepath)

    try:
        print("=== INICIANDO PROCESO SECUENCIAL ===")
        
        # PASO 1: Ejecutar el proceso de diarización completo
        print("PASO 1: Ejecutando diarización y generación de segmentos...")
        diarization_cmd = [
            'python', 'Diarization.py', filepath, temp_dir
        ]
        print('Running diarization:', diarization_cmd)
        result_diarization = subprocess.run(diarization_cmd, check=True, capture_output=True, text=True)
        print("Diarización completada exitosamente")
        
        # Verificar que result_diarization no sea None antes de acceder a sus atributos
        if result_diarization and hasattr(result_diarization, 'stdout') and result_diarization.stdout:
            print("Output:", result_diarization.stdout)
        if result_diarization and hasattr(result_diarization, 'stderr') and result_diarization.stderr:
            print("Stderr:", result_diarization.stderr)

        # PASO 2: Verificar que se generaron los archivos de diarización
        print("PASO 2: Verificando archivos de diarización...")
        segments_json_path = os.path.join(temp_dir, 'silent_segments_joined.json')
        
        if not os.path.exists(segments_json_path):
            raise Exception(f"No se encontró el archivo de segmentos: {segments_json_path}")
        
        print(f"✓ Archivo de segmentos encontrado: {segments_json_path}")
        
        # PASO 3: Cortar el video en segmentos usando silent_segments_joined.json
        print("PASO 3: Cortando video en segmentos...")
        
        # Buscar el archivo de video original en el directorio temporal
        video_file_path = None
        for fname in os.listdir(temp_dir):
            if fname.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                video_file_path = os.path.join(temp_dir, fname)
                break
        
        if not video_file_path:
            # Si no hay video, usar el archivo original
            video_file_path = filepath
        
        segment_files = cut_video_segments(video_file_path, segments_json_path, temp_dir)
        print(f"✓ Se crearon {len(segment_files)} segmentos de video")

        # PASO 3.5: Procesar descripciones para cada segmento de video
        print("PASO 3.5: Procesando descripciones para todos los segmentos...")
        description_results = process_video_descriptions(temp_dir, segment_files)
        print(f"✓ Procesamiento de descripciones completado")

        # PASO 3.6: Procesar audiodescripciones (TTS, análisis prosódico y mezcla)
        print("PASO 3.6: Procesando audiodescripciones...")
        audio_description_results = process_audio_descriptions(temp_dir, project_id)
        print(f"✓ Procesamiento de audiodescripciones completado: {audio_description_results['status']}")

        # PASO 4: Verificar todos los archivos generados
        print("PASO 4: Verificando todos los archivos generados...")
        
        generated_files = []
        for fname in os.listdir(temp_dir):
            if os.path.isfile(os.path.join(temp_dir, fname)):
                generated_files.append(fname)
                print(f"Archivo generado: {fname}")
        
        # PASO 5: Configurar credenciales y servicio de Drive
        print("PASO 5: Configurando Google Drive...")
        creds = Credentials(
            None,
            refresh_token=REFRESH_TOKEN,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            token_uri='https://oauth2.googleapis.com/token'
        )
        service = build('drive', 'v3', credentials=creds)

        # PASO 6: Crear carpeta en Drive para este proyecto
        print("PASO 6: Creando carpeta en Drive...")
        folder_metadata = {
            'name': f'project_{project_id}',
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': ['195TbCi27MxDtzV9RATxQ2bBHwsSDUmzb']
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        drive_folder_id = folder.get('id')
        print(f"Carpeta creada en Drive: {drive_folder_id}")

        # PASO 7: Crear subcarpetas organizadas y subir archivos a Drive
        print("PASO 7: Creando estructura de carpetas y subiendo archivos a Drive...")
        
        # Crear subcarpetas
        def create_subfolder(parent_id, folder_name):
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            return folder.get('id')
        
        diarization_folder_id = create_subfolder(drive_folder_id, 'diarization')
        segments_folder_id = create_subfolder(drive_folder_id, 'segments')
        video_folder_id = create_subfolder(drive_folder_id, 'video')
        descriptions_folder_id = create_subfolder(drive_folder_id, 'descriptions')
        
        # Crear carpetas para audiodescripciones
        audiodescriptions_folder_id = create_subfolder(drive_folder_id, 'audiodescriptions')
        tts_folder_id = create_subfolder(audiodescriptions_folder_id, 'tts_audios')
        analysis_folder_id = create_subfolder(audiodescriptions_folder_id, 'prosodic_analysis')
        mix_folder_id = create_subfolder(audiodescriptions_folder_id, 'final_mixes')
        
        print(f"✓ Subcarpetas creadas: diarization, segments, video, descriptions, audiodescriptions")
        
        uploaded_files = []
        upload_errors = []
        audiodescription_files_uploaded = []
        
        # Función helper para subir archivo a carpeta específica
        def upload_file_to_folder(filename, folder_id, folder_name):
            try:
                fpath = os.path.join(temp_dir, filename)
                if os.path.isfile(fpath):
                    print(f"Subiendo {filename} a carpeta {folder_name}...")
                    media = MediaFileUpload(fpath)
                    metadata = {
                        'name': filename,
                        'parents': [folder_id]
                    }
                    upload = service.files().create(
                        body=metadata,
                        media_body=media,
                        fields='id,webContentLink,webViewLink'
                    ).execute()
                    
                    uploaded_files.append({
                        'filename': filename,
                        'folder': folder_name,
                        'file_id': upload.get('id'),
                        'download_url': upload.get('webContentLink'),
                        'view_url': upload.get('webViewLink')
                    })
                    
                    # Cerrar el archivo media para liberar recursos
                    if hasattr(media, '_fd') and not media._fd.closed:
                        media._fd.close()
                    
                    print(f"✓ {filename} subido exitosamente a {folder_name}")
                    return True
            except Exception as upload_error:
                error_msg = f"Error subiendo {filename} a {folder_name}: {str(upload_error)}"
                print(error_msg)
                upload_errors.append(error_msg)
                return False
        
        # Organizar y subir archivos según su tipo
        for fname in generated_files:
            if fname.endswith('.json') or fname.startswith('speaker_'):
                # Archivos de diarización
                upload_file_to_folder(fname, diarization_folder_id, 'diarization')
            elif fname.startswith('segment_') and fname.endswith('.mp4'):
                # Segmentos de video
                upload_file_to_folder(fname, segments_folder_id, 'segments')
            elif fname.endswith(('.mov', '.mp4', '.avi', '.mkv')):
                # Video original
                upload_file_to_folder(fname, video_folder_id, 'video')
            elif fname == 'audio.wav':
                # Audio original - se sube a la carpeta raíz del proyecto
                upload_file_to_folder(fname, drive_folder_id, 'proyecto_raiz')
            else:
                # Otros archivos - se suben a la carpeta raíz del proyecto
                upload_file_to_folder(fname, drive_folder_id, 'proyecto_raiz')

        # Subir archivos de descripciones
        print("Subiendo archivos de descripciones...")
        description_files_uploaded = []
        for fname in os.listdir(temp_dir):
            if fname.endswith('_descriptions'):
                # Esta es una carpeta de descripciones
                desc_folder_path = os.path.join(temp_dir, fname)
                if os.path.isdir(desc_folder_path):
                    # Crear subcarpeta en Drive para este segmento
                    segment_desc_folder_id = create_subfolder(descriptions_folder_id, fname)
                    
                    # Buscar archivos recursivamente en la carpeta de descripciones
                    def upload_descriptions_recursively(folder_path, drive_folder_id, parent_name=""):
                        for item in os.listdir(folder_path):
                            item_path = os.path.join(folder_path, item)
                            
                            if os.path.isfile(item_path):
                                # Es un archivo, subirlo
                                try:
                                    print(f"Subiendo archivo de descripción: {item}")
                                    media = MediaFileUpload(item_path)
                                    metadata = {
                                        'name': item,
                                        'parents': [drive_folder_id]
                                    }
                                    upload = service.files().create(
                                        body=metadata,
                                        media_body=media,
                                        fields='id,webContentLink,webViewLink'
                                    ).execute()
                                    
                                    description_files_uploaded.append({
                                        'filename': item,
                                        'segment_folder': fname,
                                        'parent_folder': parent_name,
                                        'folder': 'descriptions',
                                        'file_id': upload.get('id'),
                                        'download_url': upload.get('webContentLink'),
                                        'view_url': upload.get('webViewLink')
                                    })
                                    
                                    # Cerrar el archivo media
                                    if hasattr(media, '_fd') and not media._fd.closed:
                                        media._fd.close()
                                    
                                    print(f"✓ {item} subido exitosamente")
                                    
                                except Exception as desc_upload_error:
                                    error_msg = f"Error subiendo archivo de descripción {item}: {str(desc_upload_error)}"
                                    print(error_msg)
                                    upload_errors.append(error_msg)
                                    
                            elif os.path.isdir(item_path):
                                # Es una carpeta, crear subcarpeta en Drive y procesar recursivamente
                                subfolder_name = f"{parent_name}_{item}" if parent_name else item
                                subfolder_id = create_subfolder(drive_folder_id, item)
                                upload_descriptions_recursively(item_path, subfolder_id, subfolder_name)
                    
                    # Iniciar subida recursiva
                    upload_descriptions_recursively(desc_folder_path, segment_desc_folder_id)

        # Subir archivos de audiodescripciones
        print("Subiendo archivos de audiodescripciones...")
        audiodescription_files_uploaded = []
        
        if audio_description_results['status'] == 'success':
            # Subir archivos TTS
            tts_output_dir = os.path.join(temp_dir, "temp_output")
            if os.path.exists(tts_output_dir):
                for audio_file in audio_description_results['audio_files']:
                    audio_path = os.path.join(tts_output_dir, audio_file)
                    if os.path.isfile(audio_path):
                        try:
                            print(f"Subiendo archivo TTS: {audio_file}")
                            media = MediaFileUpload(audio_path)
                            metadata = {
                                'name': audio_file,
                                'parents': [tts_folder_id]
                            }
                            upload = service.files().create(
                                body=metadata,
                                media_body=media,
                                fields='id,webContentLink,webViewLink'
                            ).execute()
                            
                            audiodescription_files_uploaded.append({
                                'filename': audio_file,
                                'type': 'tts_audio',
                                'folder': 'audiodescriptions/tts_audios',
                                'file_id': upload.get('id'),
                                'download_url': upload.get('webContentLink'),
                                'view_url': upload.get('webViewLink')
                            })
                            
                            if hasattr(media, '_fd') and not media._fd.closed:
                                media._fd.close()
                            
                            print(f"✓ {audio_file} subido exitosamente")
                        except Exception as audio_upload_error:
                            error_msg = f"Error subiendo archivo TTS {audio_file}: {str(audio_upload_error)}"
                            print(error_msg)
                            upload_errors.append(error_msg)
            
            # Subir archivos de análisis prosódico
            analysis_dir = os.path.join(temp_dir, "evaluacion_prosodica")
            if os.path.exists(analysis_dir):
                for analysis_file in audio_description_results['analysis_files']:
                    analysis_path = os.path.join(analysis_dir, analysis_file)
                    if os.path.isfile(analysis_path):
                        try:
                            print(f"Subiendo archivo de análisis: {analysis_file}")
                            media = MediaFileUpload(analysis_path)
                            metadata = {
                                'name': analysis_file,
                                'parents': [analysis_folder_id]
                            }
                            upload = service.files().create(
                                body=metadata,
                                media_body=media,
                                fields='id,webContentLink,webViewLink'
                            ).execute()
                            
                            audiodescription_files_uploaded.append({
                                'filename': analysis_file,
                                'type': 'prosodic_analysis',
                                'folder': 'audiodescriptions/prosodic_analysis',
                                'file_id': upload.get('id'),
                                'download_url': upload.get('webContentLink'),
                                'view_url': upload.get('webViewLink')
                            })
                            
                            if hasattr(media, '_fd') and not media._fd.closed:
                                media._fd.close()
                            
                            print(f"✓ {analysis_file} subido exitosamente")
                        except Exception as analysis_upload_error:
                            error_msg = f"Error subiendo archivo de análisis {analysis_file}: {str(analysis_upload_error)}"
                            print(error_msg)
                            upload_errors.append(error_msg)
            
            # Subir archivos de mezcla final
            mix_dir = os.path.join(temp_dir, "mezclas_finales")
            if os.path.exists(mix_dir):
                for mix_file in audio_description_results['mix_files']:
                    mix_path = os.path.join(mix_dir, mix_file)
                    if os.path.isfile(mix_path):
                        try:
                            print(f"Subiendo archivo de mezcla: {mix_file}")
                            media = MediaFileUpload(mix_path)
                            metadata = {
                                'name': mix_file,
                                'parents': [mix_folder_id]
                            }
                            upload = service.files().create(
                                body=metadata,
                                media_body=media,
                                fields='id,webContentLink,webViewLink'
                            ).execute()
                            
                            audiodescription_files_uploaded.append({
                                'filename': mix_file,
                                'type': 'final_mix',
                                'folder': 'audiodescriptions/final_mixes',
                                'file_id': upload.get('id'),
                                'download_url': upload.get('webContentLink'),
                                'view_url': upload.get('webViewLink')
                            })
                            
                            if hasattr(media, '_fd') and not media._fd.closed:
                                media._fd.close()
                            
                            print(f"✓ {mix_file} subido exitosamente")
                        except Exception as mix_upload_error:
                            error_msg = f"Error subiendo archivo de mezcla {mix_file}: {str(mix_upload_error)}"
                            print(error_msg)
                            upload_errors.append(error_msg)

        # PASO 8: Obtener el enlace de la carpeta en Drive
        folder_link = f"https://drive.google.com/drive/folders/{drive_folder_id}"
        print(f"Enlace de la carpeta en Drive: {folder_link}")

        # PASO 9: Actualizar documento en MongoDB con la información completa
        print("PASO 9: Actualizando información en MongoDB...")
        update_data = {
            "files": uploaded_files,
            "description_files": description_files_uploaded,
            "audiodescription_files": audiodescription_files_uploaded,
            "description_results": description_results,
            "audio_description_results": audio_description_results,
            "drive_folder_id": drive_folder_id,
            "drive_folder_link": folder_link,
            "status": "completed",
            "total_files": len(uploaded_files),
            "total_description_files": len(description_files_uploaded),
            "total_audiodescription_files": len(audiodescription_files_uploaded),
            "video_segments_created": len(segment_files),
            "descriptions_processed": len([r for r in description_results if r['status'] == 'success']),
            "audiodescriptions_processed": audio_description_results.get('tasks_processed', 0),
            "processing_errors": upload_errors if upload_errors else None
        }
        
        projects_collection.update_one(
            {"_id": result.inserted_id},
            {"$set": update_data}
        )

        # PASO 10: Limpiar archivos temporales locales
        print("PASO 10: Limpiando archivos temporales...")
        time.sleep(1)  # Pausa para asegurar que los archivos se cerraron
        
        files_removed = []
        removal_errors = []
        
        # Limpiar archivos de descripciones primero
        for fname in os.listdir(temp_dir):
            if fname.endswith('_descriptions'):
                desc_folder_path = os.path.join(temp_dir, fname)
                if os.path.isdir(desc_folder_path):
                    try:
                        # Eliminar archivos dentro de la carpeta de descripciones recursivamente
                        def remove_folder_recursively(folder_path):
                            for item in os.listdir(folder_path):
                                item_path = os.path.join(folder_path, item)
                                if os.path.isfile(item_path):
                                    os.remove(item_path)
                                    files_removed.append(f"{os.path.relpath(item_path, temp_dir)}")
                                elif os.path.isdir(item_path):
                                    remove_folder_recursively(item_path)
                                    os.rmdir(item_path)
                        
                        remove_folder_recursively(desc_folder_path)
                        
                        # Eliminar la carpeta de descripciones
                        os.rmdir(desc_folder_path)
                        files_removed.append(fname)
                        print(f"✓ Carpeta de descripciones eliminada: {fname}")
                        
                    except Exception as desc_removal_error:
                        error_msg = f"Error eliminando carpeta de descripciones {fname}: {str(desc_removal_error)}"
                        print(error_msg)
                        removal_errors.append(error_msg)
        
        # Limpiar archivos de audiodescripciones
        audiodesc_folders = ['temp_output', 'evaluacion_prosodica', 'mezclas_finales']
        for folder_name in audiodesc_folders:
            folder_path = os.path.join(temp_dir, folder_name)
            if os.path.exists(folder_path):
                try:
                    def remove_folder_recursively(folder_path):
                        for item in os.listdir(folder_path):
                            item_path = os.path.join(folder_path, item)
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                                files_removed.append(f"{os.path.relpath(item_path, temp_dir)}")
                            elif os.path.isdir(item_path):
                                remove_folder_recursively(item_path)
                                os.rmdir(item_path)
                    
                    remove_folder_recursively(folder_path)
                    os.rmdir(folder_path)
                    files_removed.append(folder_name)
                    print(f"✓ Carpeta de audiodescripciones eliminada: {folder_name}")
                    
                except Exception as audiodesc_removal_error:
                    error_msg = f"Error eliminando carpeta de audiodescripciones {folder_name}: {str(audiodesc_removal_error)}"
                    print(error_msg)
                    removal_errors.append(error_msg)
        
        # Limpiar archivos restantes
        for fname in os.listdir(temp_dir):
            try:
                file_path = os.path.join(temp_dir, fname)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    files_removed.append(fname)
                    print(f"✓ Archivo temporal eliminado: {fname}")
            except Exception as removal_error:
                error_msg = f"Error eliminando {fname}: {str(removal_error)}"
                print(error_msg)
                removal_errors.append(error_msg)
        
        try:
            os.rmdir(temp_dir)
            print(f"✓ Directorio temporal eliminado: {temp_dir}")
        except Exception as dir_error:
            print(f"Error eliminando directorio {temp_dir}: {str(dir_error)}")

        print("=== PROCESO COMPLETADO EXITOSAMENTE ===")

        # Respuesta final con toda la información
        response_data = {
            'project_id': project_id,
            'status': 'completed',
            'drive_folder_link': folder_link,
            'drive_folder_id': drive_folder_id,
            'uploaded_files': uploaded_files,
            'description_files': description_files_uploaded,
            'audiodescription_files': audiodescription_files_uploaded,
            'description_results': description_results,
            'audio_description_results': audio_description_results,
            'total_files_processed': len(uploaded_files),
            'total_description_files': len(description_files_uploaded),
            'total_audiodescription_files': len(audiodescription_files_uploaded),
            'video_segments_created': len(segment_files),
            'descriptions_processed': len([r for r in description_results if r['status'] == 'success']),
            'descriptions_failed': len([r for r in description_results if r['status'] == 'failed']),
            'audiodescriptions_processed': audio_description_results.get('tasks_processed', 0),
            'audiodescription_status': audio_description_results.get('status', 'unknown'),
            'tts_files_generated': len(audio_description_results.get('audio_files', [])),
            'analysis_files_generated': len(audio_description_results.get('analysis_files', [])),
            'mix_files_generated': len(audio_description_results.get('mix_files', [])),
            'files_removed_locally': files_removed,
            'upload_errors': upload_errors if upload_errors else None,
            'removal_errors': removal_errors if removal_errors else None
        }

        return jsonify(response_data)

    except subprocess.CalledProcessError as e:
        error_msg = f"Error en proceso de diarización: {str(e)}"
        print(error_msg)
        
        # Verificar y mostrar stdout/stderr si están disponibles
        try:
            if hasattr(e, 'stdout') and e.stdout is not None:
                print("Stdout:", e.stdout)
        except Exception:
            pass
            
        try:
            if hasattr(e, 'stderr') and e.stderr is not None:
                print("Stderr:", e.stderr)
        except Exception:
            pass
        
        # Actualizar estado en MongoDB
        projects_collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"status": "failed", "error": error_msg}}
        )
        
        # Limpiar archivos temporales en caso de error
        cleanup_temp_files(temp_dir)
        
        return jsonify({'error': error_msg}), 500
        
    except Exception as e:
        error_msg = f"Error general en el proceso: {str(e)}"
        print(error_msg)
        
        # Actualizar estado en MongoDB
        projects_collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"status": "failed", "error": error_msg}}
        )
        
        # Limpiar archivos temporales en caso de error
        cleanup_temp_files(temp_dir)
        
        return jsonify({'error': error_msg}), 500

def cleanup_temp_files(temp_dir):
    """Función auxiliar para limpiar archivos temporales en caso de error"""
    try:
        if os.path.exists(temp_dir):
            print(f"Limpiando archivos temporales en: {temp_dir}")
            
            import shutil
            
            # Eliminar todas las carpetas de descripciones recursivamente
            for fname in os.listdir(temp_dir):
                if fname.endswith('_descriptions'):
                    desc_folder_path = os.path.join(temp_dir, fname)
                    if os.path.isdir(desc_folder_path):
                        try:
                            shutil.rmtree(desc_folder_path)
                            print(f"✓ Carpeta de descripciones eliminada recursivamente: {fname}")
                        except Exception as desc_ex:
                            print(f'Error removing description folder {fname}: {str(desc_ex)}')
            
            # Limpiar archivos restantes
            for fname in os.listdir(temp_dir):
                try:
                    file_path = os.path.join(temp_dir, fname)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        print(f"✓ Archivo temporal eliminado: {fname}")
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        print(f"✓ Directorio temporal eliminado recursivamente: {fname}")
                except Exception as ex:
                    print(f'Error removing temp file/folder {fname}: {str(ex)}')
            
            try:
                os.rmdir(temp_dir)
                print(f"✓ Directorio temporal eliminado: {temp_dir}")
            except Exception as ex:
                print(f'Error removing temp directory: {str(ex)}')
    except Exception as ex:
        print(f'Error in cleanup_temp_files: {str(ex)}')

@app.route('/project/<project_id>/audiodescriptions', methods=['POST'])
def process_project_audiodescriptions(project_id):
    """Procesar audiodescripciones para un proyecto existente"""
    if not NARRATIONS_AVAILABLE:
        return jsonify({'error': 'Narrations module not available'}), 400
    
    try:
        from bson.objectid import ObjectId
        project = projects_collection.find_one({"_id": ObjectId(project_id)})
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        if project.get('status') != 'completed':
            return jsonify({'error': 'Project not completed yet'}), 400
        
        # Verificar si ya tiene audiodescripciones
        if project.get('audio_description_results', {}).get('status') == 'success':
            return jsonify({'message': 'Audiodescriptions already processed', 'project': project})
        
        # Crear directorio temporal para reprocessar
        temp_dir = os.path.join('temp', f"{project_id}_audiodesc")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Aquí necesitarías descargar los archivos de descripciones desde Drive
        # Por simplicidad, asumo que están disponibles localmente
        
        # Procesar audiodescripciones
        audio_description_results = process_audio_descriptions(temp_dir, project_id)
        
        # Actualizar proyecto en MongoDB
        projects_collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"audio_description_results": audio_description_results}}
        )
        
        # Limpiar archivos temporales
        cleanup_temp_files(temp_dir)
        
        return jsonify({
            'project_id': project_id,
            'status': 'audiodescriptions_completed',
            'audio_description_results': audio_description_results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/project/<project_id>', methods=['GET'])
def get_project_status(project_id):
    """Obtener el estado y información de un proyecto específico"""
    try:
        from bson.objectid import ObjectId
        project = projects_collection.find_one({"_id": ObjectId(project_id)})
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Convertir ObjectId a string para JSON
        project['_id'] = str(project['_id'])
        
        return jsonify(project)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/projects', methods=['GET'])
def list_projects():
    """Listar todos los proyectos"""
    try:
        projects = list(projects_collection.find().sort('_id', -1).limit(50))
        
        # Convertir ObjectIds a strings
        for project in projects:
            project['_id'] = str(project['_id'])
        
        return jsonify({'projects': projects})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
