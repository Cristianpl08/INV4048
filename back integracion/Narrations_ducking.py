# -*- coding: utf-8 -*-
"""
PIPELINE COMPLETO DE GENERACIÓN Y POST-PRODUCCIÓN DE AUDIO - VERSIÓN LOCAL

Este script ha sido modificado para trabajar con archivos locales en lugar de Google Drive.
Integra un flujo de trabajo completo para la creación de pistas de audio descriptivo (AD).

ESTRUCTURA ESPERADA:
- temp/: Carpeta principal temporal
  - segment_xxx_descriptions/: Carpetas con descripciones de cada segmento
    - video_summary.json: Resumen del video 
    - prosody_analysis.json: Análisis de prosodia
  - Archivo de video original (.mp4, .mov, etc.)
  - Archivo JSON con tiempos (Main_Video.json, silent_segments_joined.json, etc.)
- Locutores/: Carpeta con audios de referencia por emoción
  - Andrea/: Audios de referencia para Andrea
  - Sergio/: Audios de referencia para Sergio  
  - Sebastian/: Audios de referencia para Sebastian

SALIDAS GENERADAS:
- temp/temp_output/: Audios TTS generados
- temp/evaluacion_prosodica/: Análisis prosódico y gráficas
- temp/mezclas_finales/: Mezclas finales con ducking

USO:
1. Asegurar que la estructura de archivos esté en su lugar
2. Ejecutar: resultado = ejecutar_pipeline_completo_local()
"""

import os
import json
import re
import unicodedata
import time
import torch
import nltk
import subprocess
import imageio_ffmpeg
from TTS.api import TTS
from openai import OpenAI
from thefuzz import fuzz
from pydub import AudioSegment
from pydub.silence import split_on_silence
import noisereduce as nr
import soundfile as sf
import numpy as np
import pandas as pd
import opensmile
import matplotlib.pyplot as plt
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

nltk.download('punkt', quiet=True)

def limpiar_texto_de_metadata(texto_completo):
    match = re.search(r"\s-\s[A-ZÁÉÍÓÚÑ]", texto_completo)
    if match:
        return texto_completo[:match.start()].strip()
    return texto_completo.strip()

def split_text_into_chunks(text, max_chars=800):
    if len(text) <= max_chars:
        return [text]
    sentences = nltk.tokenize.sent_tokenize(text, language='spanish')
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += (" " + sentence) if current_chunk else sentence
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def normalizar_para_comparacion(texto):
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if c.isalnum() or c.isspace()).strip()
    return " ".join(texto.split())

def verificar_audio_flexible(ruta_audio, texto_original, umbral_similitud=90):
    if not client:
        return False
    try:
        with open(ruta_audio, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_file, language="es")
        texto_transcrito = transcription.text
        if not texto_transcrito or len(texto_transcrito.strip()) < 5:
            print("    ⚠️ Verificación fallida: Whisper no detectó texto (posible ruido).")
            return False
        original_norm = normalizar_para_comparacion(texto_original)
        transcrito_norm = normalizar_para_comparacion(texto_transcrito)
        ratio = fuzz.ratio(original_norm, transcrito_norm)
        print(f"    -> Similitud del texto: {ratio}% (Umbral: {umbral_similitud}%)")
        if ratio >= umbral_similitud:
            return True
        else:
            print("    ⚠️ Verificación fallida: Baja similitud.")
            return False
    except Exception as e:
        print(f"    ❌ Error durante la verificación con Whisper: {e}")
        return False

def limpiar_audio_generado(ruta_entrada, ruta_salida):
    try:
        data, rate = sf.read(ruta_entrada)
        ruido_reducido_data = nr.reduce_noise(y=data, sr=rate)
        ruta_temp = "/content/temp_audio_limpio.wav"
        sf.write(ruta_temp, ruido_reducido_data, rate)
        audio = AudioSegment.from_wav(ruta_temp)
        chunks = split_on_silence(audio, min_silence_len=500, silence_thresh=audio.dBFS-16)
        audio_final = sum(chunks, AudioSegment.empty()) if chunks else audio
        audio_final.export(ruta_salida, format="wav")
        if os.path.exists(ruta_temp):
            os.remove(ruta_temp)
        return True
    except Exception as e:
        print(f"    ❌ Error durante la limpieza del audio: {e}")
        return False

def limpiar_texto_summary(texto_completo):
    delimitadores = ["- Emoción complementaria utilizada:", "Mecanismos de atención:", "Mecanismo de atención:", "Resumen:", "Número total de caracteres:", "**"]
    primera_posicion = -1
    for d in delimitadores:
        posicion_actual = texto_completo.find(d)
        if posicion_actual != -1 and (primera_posicion == -1 or posicion_actual < primera_posicion):
            primera_posicion = posicion_actual
    if primera_posicion != -1:
        texto_completo = texto_completo[:primera_posicion]
    texto_limpio = texto_completo.replace('\n', ' ').replace('*', '').replace('-', '').strip()
    return re.sub(r'\s+', ' ', texto_limpio)

def encontrar_archivo_emocion(ruta_carpeta_locutor, emocion):
    termino_busqueda = "".join(c for c in unicodedata.normalize('NFD', emocion.lower()) if unicodedata.category(c) != 'Mn')
    if not os.path.exists(ruta_carpeta_locutor): return None
    for nombre_archivo in os.listdir(ruta_carpeta_locutor):
        if nombre_archivo.lower().endswith('.wav'):
            nombre_norm = "".join(c for c in unicodedata.normalize('NFD', nombre_archivo.lower()) if unicodedata.category(c) != 'Mn')
            if termino_busqueda in nombre_norm:
                return os.path.join(ruta_carpeta_locutor, nombre_archivo)
    return None

def split_text_into_chunks(text, max_chars=800):
    try: nltk.data.find('tokenizers/punkt')
    except LookupError: nltk.download('punkt', quiet=True)
    if len(text) <= max_chars: return [text]
    sentences = nltk.tokenize.sent_tokenize(text, language='spanish')
    chunks, current_chunk = [], ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > max_chars:
            if current_chunk: chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += (" " + sentence) if current_chunk else sentence
    if current_chunk: chunks.append(current_chunk.strip())
    return chunks

def verificar_audio_flexible(ruta_audio, texto_original, umbral_similitud=90):
    if not client: return False
    try:
        with open(ruta_audio, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_file, language="es")
        texto_transcrito = transcription.text
        if not texto_transcrito or len(texto_transcrito.strip()) < 5:
            print("    ⚠️ Verificación fallida: Whisper no detectó texto.")
            return False
        original_norm = " ".join("".join(c for c in unicodedata.normalize('NFD', texto_original.lower()) if c.isalnum() or c.isspace()).split())
        transcrito_norm = " ".join("".join(c for c in unicodedata.normalize('NFD', texto_transcrito.lower()) if c.isalnum() or c.isspace()).split())
        ratio = fuzz.ratio(original_norm, transcrito_norm)
        print(f"    -> Similitud: {ratio}%. Original: '{original_norm[:50]}...'. Transcrito: '{transcrito_norm[:50]}...'.")
        return ratio >= umbral_similitud
    except Exception as e:
        print(f"    ❌ Error en verificación Whisper: {e}")
        return False

def limpiar_audio_generado(ruta_entrada, ruta_salida):
    try:
        data, rate = sf.read(ruta_entrada)
        ruido_reducido_data = nr.reduce_noise(y=data, sr=rate, prop_decrease=0.8)
        ruta_temp = "/content/temp_audio_limpio.wav"
        sf.write(ruta_temp, ruido_reducido_data, rate)
        audio = AudioSegment.from_wav(ruta_temp)
        audio_final = audio.fade_in(20).fade_out(150)
        audio_final.export(ruta_salida, format="wav")
        if os.path.exists(ruta_temp): os.remove(ruta_temp)
        return True
    except Exception as e:
        print(f"    ❌ Error durante la limpieza del audio: {e}")
        return False

"""## 2. Inicialización de Modelos y Rutas

Esta sección es crucial para la configuración del proyecto. Aquí se realizan las siguientes acciones:

* **Montar Google Drive**: Se conecta el notebook al almacenamiento de Google Drive para acceder a los archivos del proyecto.
* **Definir Estructura de Carpetas**: Se establecen las rutas de entrada (videos, JSON) y de salida (audios generados, audios procesados, evaluaciones y mezcla final).
* **Cargar Modelo TTS**: Se inicializa y carga en memoria el modelo `XTTS v2` de Coqui, preparándolo para la generación de voz.
* **Configurar Cliente OpenAI**: Se establece la conexión con la API de OpenAI, necesaria para la verificación de audio con Whisper.
"""

# Librerías para la API de Google Drive

# import os  # ya importado arriba

# Credenciales de autenticación directa
CLIENT_ID = '854426603654-alf13d79isla285q8h0sgpvljb77pts4.apps.googleusercontent.com'
CLIENT_SECRET = 'YOUR_GOOGLE_OAUTH_CLIENT_SECRET'
REFRESH_TOKEN = 'YOUR_GOOGLE_OAUTH_REFRESH_TOKEN'

# --- Alcance de permisos para la API de Drive ---
SCOPES = ['https://www.googleapis.com/auth/drive']
def autenticar_drive():
    """Maneja la autenticación con la API de Google Drive usando un refresh token."""
    try:
        creds = Credentials(
            token=None,
            refresh_token=REFRESH_TOKEN,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES
        )
        creds.refresh(Request())

        print("✅ Autenticación con Google Drive exitosa.")
        return build('drive', 'v3', credentials=creds)

    except Exception as e:
        print(f"❌ Error fatal durante la autenticación: {e}")
        print("Verifica que el CLIENT_ID, CLIENT_SECRET y REFRESH_TOKEN sean correctos y no hayan expirado.")
        return None

# Prueba para ver si la variable existe ANTES de la llamada
try:
    print(f"Verificando... El REFRESH_TOKEN es: {REFRESH_TOKEN[:10]}...") # Imprime solo los primeros 10 caracteres
except NameError:
    print("❌ Efectivamente, REFRESH_TOKEN no está definido en este punto.")

# Autentica primero para poder usar el servicio
drive_service = autenticar_drive()

# IDs de las carpetas de Google Drive (reemplazando las rutas de Colab)
FOLDER_ID_BASE_PROYECTO = "13rJEhFUNATi7qoYZNpUOAeLfVBkO9wPP"
FOLDER_ID_EMOCIONES_BASE = "16WAuMzjmC4xNPGbr3QWIYHspKBl4H2s7" # ID de la carpeta "Locutores"

# --- Carpetas temporales locales ---
TEMP_BASE_DIR = "temp"
os.makedirs(TEMP_BASE_DIR, exist_ok=True)
os.makedirs(os.path.join(TEMP_BASE_DIR, "temp_drive_files"), exist_ok=True)
os.makedirs(os.path.join(TEMP_BASE_DIR, "temp_output"), exist_ok=True)
LOCAL_TEMP_DIR = os.path.join(TEMP_BASE_DIR, "temp_drive_files")
LOCAL_OUTPUT_DIR = os.path.join(TEMP_BASE_DIR, "temp_output")

device = "cuda" if torch.cuda.is_available() else "cpu"

from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
from TTS.config.shared_configs import BaseDatasetConfig

torch.serialization.add_safe_globals([
    XttsConfig,
    XttsAudioConfig,
    BaseDatasetConfig,
    XttsArgs
])
print("Configuración de seguridad de PyTorch aplicada.")

print(f"Usando dispositivo: {device} para cargar el modelo TTS...")
tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2").to(device)
print("✅ Modelo TTS cargado.")

try:
    client = OpenAI(api_key="YOUR_API_KEY")
    client.models.list()
    print("✅ Cliente de OpenAI configurado y autenticado.")
except Exception as e:
    print(f"❌ Error al configurar el cliente de OpenAI. Revisa tu API Key. Error: {e}")
    client = None

def autenticar_drive():
    try:
        creds = Credentials(
            token=None,
            refresh_token=REFRESH_TOKEN,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES
        )
        creds.refresh(Request())
        print("✅ Autenticación con Google Drive exitosa.")
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Error fatal durante la autenticación: {e}")
        return None

def crear_o_obtener_carpeta(service, nombre_carpeta, id_carpeta_padre):
    query = f"name='{nombre_carpeta}' and mimeType='application/vnd.google-apps.folder' and '{id_carpeta_padre}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id)").execute()
    items = results.get('files', [])

    if items:
        folder_id = items[0].get('id')
        print(f"✔️ La carpeta '{nombre_carpeta}' ya existe con ID: {folder_id}")
        return folder_id
    else:
        file_metadata = {
            'name': nombre_carpeta,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [id_carpeta_padre]
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = folder.get('id')
        print(f"✅ Carpeta '{nombre_carpeta}' creada con ID: {folder_id}")
        return folder_id

if drive_service:
    print("\nVerificando y/o creando la estructura de carpetas final en Google Drive...")

    print("\nBuscando la carpeta 'Input'...")
    FOLDER_ID_INPUT = crear_o_obtener_carpeta(drive_service, "Input", FOLDER_ID_BASE_PROYECTO)

    print("\nCreando carpetas de salida...")
    FOLDER_ID_OUTPUT_MAIN = crear_o_obtener_carpeta(drive_service, "Output AD", FOLDER_ID_BASE_PROYECTO)

    FOLDER_ID_AD = crear_o_obtener_carpeta(drive_service, "AD", FOLDER_ID_OUTPUT_MAIN)
    FOLDER_ID_EVALUACION = crear_o_obtener_carpeta(drive_service, "Evaluación prosódica", FOLDER_ID_OUTPUT_MAIN)

    print("\n✅ Estructura de carpetas completa y lista.")

    FOLDER_ID_OUTPUT_PROCESADOS = FOLDER_ID_AD

else:
    print("❌ No se pudo autenticar con Google Drive. El script no puede continuar.")
    exit()

import pandas as pd
# from IPython.display import display  # No disponible en entorno estándar
import io

# FUNCIONES DE UTILIDAD DE DRIVE
def listar_archivos(service, folder_id):
    query = f"'{folder_id}' in parents and trashed=false"
    try:
        results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
        return results.get('files', [])
    except Exception as e:
        print(f"Error al listar archivos en la carpeta {folder_id}: {e}")
        return []

def descargar_archivo(service, file_id, local_path):
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        with open(local_path, 'wb') as f:
            f.write(fh.getvalue())
        return local_path
    except Exception as e:
        print(f"Error al descargar el archivo {file_id}: {e}")
        return None

def subir_archivo(service, local_path, folder_id):
    try:
        file_metadata = {
            'name': os.path.basename(local_path),
            'parents': [folder_id]
        }
        media = MediaFileUpload(local_path, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"    -> Archivo '{os.path.basename(local_path)}' subido a Drive con ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        print(f"    -> Error al subir el archivo {os.path.basename(local_path)}: {e}")
        return None

def encontrar_y_descargar_referencia_drive(service, base_emociones_id, locutor, emocion):
    carpetas_locutores = listar_archivos(service, base_emociones_id)
    id_carpeta_locutor = next((c['id'] for c in carpetas_locutores if c['name'] == locutor), None)

    if not id_carpeta_locutor:
        print(f"  ⚠️ ¡Advertencia! No se encontró la carpeta para el locutor '{locutor}' en Drive.")
        return None

    archivos_emocion = listar_archivos(service, id_carpeta_locutor)
    termino_busqueda = "".join(c for c in unicodedata.normalize('NFD', emocion.lower()) if unicodedata.category(c) != 'Mn')

    archivo_referencia = None
    for archivo in archivos_emocion:
        nombre_norm = "".join(c for c in unicodedata.normalize('NFD', archivo['name'].lower()) if unicodedata.category(c) != 'Mn')
        if termino_busqueda in nombre_norm and archivo['name'].lower().endswith('.wav'):
            archivo_referencia = archivo
            break

    if not archivo_referencia:
        print(f"  ⚠️ ¡Advertencia! No se encontró archivo de referencia para la emoción '{emocion}'.")
        return None

    print(f"  -> Usando audio de referencia de Drive: {archivo_referencia['name']}")
    ruta_local_referencia = os.path.join(LOCAL_TEMP_DIR, archivo_referencia['name'])
    descargar_archivo(service, archivo_referencia['id'], ruta_local_referencia)

    return ruta_local_referencia

"""## 3. Carga y Preparación de Tareas de Generación Locales

El siguiente código escanea las carpetas locales de entrada definidas previamente. Busca los archivos `prosody_analysis.json` para extraer la **emoción principal** y los `video_summary.json` para obtener el **texto a sintetizar**.

Toda esta información se organiza en una tabla (DataFrame de Pandas) que resume las tareas de generación que se realizarán a continuación.
"""

def cargar_tareas_locales(temp_dir="temp"):
    """Carga las tareas de generación desde archivos locales en la nueva estructura de segmentos"""
    tareas_de_generacion = []
    print("--- Analizando archivos locales y extrayendo datos de segmentos ---")
    
    # Buscar carpetas de segmentos en el directorio temporal (nueva estructura)
    # Estructura esperada: temp/segment_001_00s/, temp/segment_002_45s/, etc.
    segment_folders = []
    if os.path.exists(temp_dir):
        for item in os.listdir(temp_dir):
            # Buscar carpetas que sigan el patrón segment_XXX_XXs
            if item.startswith('segment_') and item.endswith('s') and os.path.isdir(os.path.join(temp_dir, item)):
                segment_folders.append(item)
    
    # Si no se encuentran carpetas de segmentos, buscar por el método anterior (_descriptions)
    if not segment_folders:
        print("No se encontraron carpetas de segmentos, buscando carpetas de descripciones...")
        for item in os.listdir(temp_dir):
            if item.endswith('_descriptions') and os.path.isdir(os.path.join(temp_dir, item)):
                segment_folders.append(item)
    
    print(f"Se encontraron {len(segment_folders)} carpetas de segmentos/descripciones para analizar.")
    
    for segment_folder in segment_folders:
        folder_path = os.path.join(temp_dir, segment_folder)
        print(f"  🔍 Analizando carpeta: '{segment_folder}'...")
        
        try:
            # Buscar archivos JSON necesarios
            summary_file = None
            prosody_file = None
            
            # Verificar si es la nueva estructura de segmentos
            if segment_folder.startswith('segment_') and segment_folder.endswith('s'):
                # Nueva estructura: temp/segment_XXX_XXs/video_summary.json y prosody_analysis.json
                potential_summary = os.path.join(folder_path, 'video_summary.json')
                potential_prosody = os.path.join(folder_path, 'prosody_analysis.json')
                
                if os.path.isfile(potential_summary):
                    summary_file = potential_summary
                    print(f"    ✅ Encontrado video_summary.json: {summary_file}")
                
                if os.path.isfile(potential_prosody):
                    prosody_file = potential_prosody
                    print(f"    ✅ Encontrado prosody_analysis.json: {prosody_file}")
                
                # Extraer video_id del nombre del segmento
                video_id = segment_folder
                
            else:
                # Estructura anterior con _descriptions
                video_id = segment_folder.replace('_descriptions', '')
                
                # Buscar subcarpeta con el nombre del video
                video_subfolder = None
                for item in os.listdir(folder_path):
                    item_path = os.path.join(folder_path, item)
                    if os.path.isdir(item_path) and item == video_id:
                        video_subfolder = item_path
                        break
                
                if video_subfolder:
                    print(f"    📁 Encontrada subcarpeta de video: {video_subfolder}")
                    # Buscar archivos JSON en la subcarpeta del video
                    for item in os.listdir(video_subfolder):
                        item_path = os.path.join(video_subfolder, item)
                        if os.path.isfile(item_path):
                            if item == 'video_summary.json':
                                summary_file = item_path
                                print(f"    ✅ Encontrado video_summary.json: {item_path}")
                            elif item == 'prosody_analysis.json':
                                prosody_file = item_path
                                print(f"    ✅ Encontrado prosody_analysis.json: {item_path}")
                else:
                    # Fallback: buscar directamente en la carpeta de descripciones
                    print(f"    🔍 No se encontró subcarpeta '{video_id}', buscando archivos directamente...")
                    for item in os.listdir(folder_path):
                        item_path = os.path.join(folder_path, item)
                        if os.path.isfile(item_path):
                            if item == 'video_summary.json':
                                summary_file = item_path
                            elif item == 'prosody_analysis.json':
                                prosody_file = item_path
                        # También buscar en subcarpetas
                        elif os.path.isdir(item_path):
                            for subitem in os.listdir(item_path):
                                subitem_path = os.path.join(item_path, subitem)
                                if os.path.isfile(subitem_path):
                                    if subitem == 'video_summary.json':
                                        summary_file = subitem_path
                                    elif subitem == 'prosody_analysis.json':
                                        prosody_file = subitem_path
            
            if summary_file and prosody_file:
                print(f"    📄 Archivos encontrados:")
                print(f"      Summary: {summary_file}")
                print(f"      Prosody: {prosody_file}")
                
                # Cargar los datos de los archivos JSON
                with open(summary_file, 'r', encoding='utf-8') as f:
                    datos_summary = json.load(f)
                with open(prosody_file, 'r', encoding='utf-8') as f:
                    datos_prosody = json.load(f)
                
                # Extraer el texto del resumen principal
                if isinstance(datos_summary, dict) and "main_summary" in datos_summary:
                    my_text = limpiar_texto_summary(datos_summary["main_summary"])
                elif isinstance(datos_summary, str):
                    my_text = limpiar_texto_summary(datos_summary)
                else:
                    print(f"    ⚠️ Formato de summary no reconocido: {type(datos_summary)}")
                    my_text = str(datos_summary)
                
                # Extraer la emoción complementaria
                if isinstance(datos_prosody, dict):
                    emocion = datos_prosody.get("complementary_emotion", "neutral")
                else:
                    print(f"    ⚠️ Formato de prosody no reconocido: {type(datos_prosody)}")
                    emocion = "neutral"
                
                tareas_de_generacion.append({
                    "Video ID": video_id,
                    "Texto a Generar": my_text,
                    "Emoción": emocion,
                    "Carpeta Origen": folder_path,
                    "Summary File": summary_file,
                    "Prosody File": prosody_file
                })
                print(f"    ✅ Tarea para '{video_id}' cargada exitosamente.")
                print(f"        - Emoción: {emocion}")
                print(f"        - Texto (primeros 100 chars): {my_text[:100]}...")
            else:
                print(f"    ❌ Omitiendo '{video_id}': No se encontraron los archivos necesarios.")
                print(f"      Summary encontrado: {'✅' if summary_file else '❌'}")
                print(f"      Prosody encontrado: {'✅' if prosody_file else '❌'}")
                
                # Mostrar estructura de archivos para debug
                print(f"    🔍 Estructura de archivos en {folder_path}:")
                for item in os.listdir(folder_path):
                    item_path = os.path.join(folder_path, item)
                    if os.path.isdir(item_path):
                        print(f"      📁 {item}/:")
                        try:
                            for subitem in os.listdir(item_path):
                                print(f"        📄 {subitem}")
                        except:
                            print(f"        ❌ Error listando contenido")
                    else:
                        print(f"      📄 {item}")
                        
        except Exception as e:
            print(f"    ❌ Error procesando '{segment_folder}': {str(e)}")
            import traceback
            traceback.print_exc()
    
    if not tareas_de_generacion:
        print("\n❌ No se encontraron tareas válidas para procesar.")
        print("📋 Verificación final de la estructura esperada:")
        if os.path.exists(temp_dir):
            print(f"Contenido de {temp_dir}:")
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path):
                    print(f"  📁 {item}/")
                    try:
                        for subitem in os.listdir(item_path):
                            print(f"    📄 {subitem}")
                    except:
                        print(f"    ❌ Error listando {item}")
                else:
                    print(f"  📄 {item}")
    else:
        print(f"\n✅ Se cargaron {len(tareas_de_generacion)} tareas para procesamiento TTS.")
        
    return tareas_de_generacion

def encontrar_archivo_emocion_local(ruta_carpeta_locutor, emocion):
    """Versión local de encontrar_archivo_emocion"""
    termino_busqueda = "".join(c for c in unicodedata.normalize('NFD', emocion.lower()) if unicodedata.category(c) != 'Mn')
    if not os.path.exists(ruta_carpeta_locutor): 
        return None
    
    for nombre_archivo in os.listdir(ruta_carpeta_locutor):
        if nombre_archivo.lower().endswith('.wav'):
            nombre_norm = "".join(c for c in unicodedata.normalize('NFD', nombre_archivo.lower()) if unicodedata.category(c) != 'Mn')
            if termino_busqueda in nombre_norm:
                return os.path.join(ruta_carpeta_locutor, nombre_archivo)
    return None

# --- LECTURA Y PREPARACIÓN DE LAS TAREAS DESDE ARCHIVOS LOCALES ---
tareas_de_generacion = cargar_tareas_locales()

if tareas_de_generacion:
    df_tareas = pd.DataFrame(tareas_de_generacion)
    print("\n--- RESUMEN DE TAREAS A REALIZAR ---")
    print(df_tareas.to_string(index=False))
else:
    print("\nNo se encontraron tareas válidas para procesar.")

"""## 4. Proceso Principal de Generación de Audio (TTS) Local

Este es el núcleo del proceso de síntesis de voz adaptado para trabajar con archivos locales. El código itera sobre cada tarea definida en la tabla anterior y realiza lo siguiente:

* **Selecciona el Locutor**: Procesa la tarea para cada uno de los locutores definidos (Andrea, Sergio, etc.).
* **Busca el Audio de Referencia**: Encuentra el archivo de audio del locutor que corresponde a la emoción principal requerida en la carpeta local.
* **Genera por Fragmentos**: Divide textos largos en fragmentos más pequeños para asegurar una alta calidad y evitar errores.
* **Verifica con Whisper**: Después de generar cada fragmento, lo transcribe con Whisper y lo compara con el texto original para asegurar su fidelidad.
* **Limpia y Guarda**: Una vez verificados todos los fragmentos, los une y aplica un post-procesamiento antes de guardarlos en la carpeta temporal.
"""

# --- BUCLE PRINCIPAL DE GENERACIÓN LOCAL ---

locutores = ["Andrea", "Sergio", "Sebastian"]
max_intentos_por_chunk = 3

# Ruta base donde están los archivos de emociones de los locutores
RUTA_EMOCIONES_BASE = "Locutores"  # Ajustar según la estructura local

def procesar_generacion_local():
    """Función principal para procesar la generación de audio local"""
    print("🔧 DEBUG: Iniciando procesar_generacion_local()")
    
    # Verificar que las tareas estén cargadas
    print(f"🔧 DEBUG: tareas_de_generacion tiene {len(tareas_de_generacion) if tareas_de_generacion else 0} elementos")
    
    if not tareas_de_generacion:
        print("❌ La lista de tareas está vacía. No se generará ningún audio.")
        return []
    
    # Verificar inicialización de TTS
    print("🔧 DEBUG: Verificando inicialización de TTS...")
    global tts
    if 'tts' not in globals() or tts is None:
        print("🔧 DEBUG: TTS no inicializado, inicializando...")
        try:
            tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
            print("✅ TTS inicializado correctamente")
        except Exception as tts_error:
            print(f"❌ Error al inicializar TTS: {tts_error}")
            return []
    else:
        print("✅ TTS ya estaba inicializado")
    
    # Verificar directorio de salida
    print(f"🔧 DEBUG: LOCAL_OUTPUT_DIR = {LOCAL_OUTPUT_DIR}")
    if not os.path.exists(LOCAL_OUTPUT_DIR):
        print(f"📁 Creando directorio de salida: {LOCAL_OUTPUT_DIR}")
        os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
    
    archivos_generados = []
    
    for tarea_idx, tarea in enumerate(tareas_de_generacion):
        video_id, texto_a_generar, emocion_a_buscar = tarea["Video ID"], tarea["Texto a Generar"], tarea["Emoción"]
        carpeta_origen = tarea.get("Carpeta Origen", "")

        print("\n" + "="*80)
        print(f"📄 TAREA {tarea_idx + 1} de {len(tareas_de_generacion)} | VIDEO: {video_id} | EMOCIÓN: {emocion_a_buscar}")
        print("="*80)

        chunks = split_text_into_chunks(texto_a_generar)

        for locutor in locutores:
            print(f"\n  🎤 Procesando para el locutor: {locutor}")

            # Buscar audio de referencia en la carpeta local
            ruta_carpeta_locutor = os.path.join(RUTA_EMOCIONES_BASE, locutor)
            ruta_referencia_voz_local = encontrar_archivo_emocion_local(ruta_carpeta_locutor, emocion_a_buscar)

            if not ruta_referencia_voz_local:
                print(f"    ❌ No se encontró audio de referencia para {locutor} con emoción {emocion_a_buscar}. Saltando...")
                continue

            print(f"  -> Usando audio de referencia local: {ruta_referencia_voz_local}")
            temp_audio_files = []

            for i, chunk in enumerate(chunks):
                print(f"    Fragmento [{i+1}/{len(chunks)}]:")
                intentos, verificado = 0, False
                ruta_temp_chunk = os.path.join(LOCAL_OUTPUT_DIR, f"temp_{video_id}_{locutor}_{i}.wav")

                while intentos < max_intentos_por_chunk:
                    intentos += 1
                    print(f"      -> Intento {intentos}/{max_intentos_por_chunk}: Generando audio...")
                    tts.tts_to_file(
                        text=chunk.replace('.', ''),
                        speaker_wav=ruta_referencia_voz_local,
                        language="es",
                        file_path=ruta_temp_chunk,
                        temperature=0.65, top_k=50, top_p=0.85, repetition_penalty=1.2
                    )

                    print(f"      -> Verificando con Whisper...")
                    verificado = verificar_audio_flexible(ruta_temp_chunk, chunk)
                    if verificado:
                        print(f"      -> ✅ Verificación exitosa.")
                        break

                if not verificado:
                    print(f"      -> ⚠️  Verificación fallida tras {max_intentos_por_chunk} intentos. Se usará el último audio generado.")

                temp_audio_files.append(ruta_temp_chunk)

            if temp_audio_files:
                print(f"\n    ⚙️  Procesando audio final para '{locutor}'...")
                combined_audio = sum([AudioSegment.from_wav(f) for f in temp_audio_files], AudioSegment.empty())

                nombre_base = f"{video_id}_{locutor}_{emocion_a_buscar}.wav"

                ruta_local_generado = os.path.join(LOCAL_OUTPUT_DIR, f"generado_{nombre_base}")
                ruta_local_procesado = os.path.join(LOCAL_OUTPUT_DIR, f"{nombre_base}")

                combined_audio.export(ruta_local_generado, format="wav")

                if limpiar_audio_generado(ruta_local_generado, ruta_local_procesado):
                    print(f"    ✨ Audio final procesado y guardado en: {ruta_local_procesado}")
                    archivos_generados.append(ruta_local_procesado)
                    
                    # Mostrar información del audio generado
                    try:
                        audio_info = AudioSegment.from_wav(ruta_local_procesado)
                        print(f"    📊 Duración: {len(audio_info)/1000:.2f}s")
                    except:
                        pass

            # Limpiar archivos temporales
            archivos_a_limpiar = temp_audio_files
            if temp_audio_files and 'ruta_local_generado' in locals():
                archivos_a_limpiar.append(ruta_local_generado)

            for temp_file in archivos_a_limpiar:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass

    print("\n\n" + "#"*80)
    print("###      PROCESO COMPLETO DE GENERACIÓN FINALIZADO      ###")
    print("#"*80)
    
    return archivos_generados

# Ejecutar la generación local
# archivos_audio_generados = procesar_generacion_local()

"""## 7. Evaluación Prosódica de los Audios Generados

Una vez que todos los audios han sido generados, procesados y guardados en la carpeta `Audio Procesado Final`, esta sección final se encarga de realizar un análisis objetivo de sus características prosódicas utilizando la librería `openSMILE`.

**Proceso de Evaluación:**
1.  **Análisis con openSMILE:** Se extraen 88 características de cada audio utilizando el set de features `eGeMAPSv02`.
2.  **Selección y Normalización:** Se seleccionan 4 características clave (Intensidad, Entonación, Ritmo, Duración) y se normalizan en una escala del 1 al 5 para poder compararlas.
3.  **Generación de Gráficas:** Se crean y guardan varias visualizaciones:
    * Promedio por emoción.
    * Promedio por video.
    * Comparativa de locutores para cada video.
    * Gráficas individuales para cada archivo de audio.
"""

import opensmile
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

def analizar_prosodia_opensmile_local(carpeta_audios_local, carpeta_salida_local):
    """Análisis prosódico usando archivos locales"""
    print("\n--- 🔎 1. Analizando archivos de audio locales con openSMILE ---")

    if not os.path.exists(carpeta_audios_local):
        print(f"    ⚠️ La carpeta {carpeta_audios_local} no existe.")
        return None

    archivos_wav_locales = [f for f in os.listdir(carpeta_audios_local) if f.lower().endswith(".wav")]
    
    if not archivos_wav_locales:
        print(f"    ⚠️ No se encontraron archivos .wav en {carpeta_audios_local}.")
        return None

    rutas_completas_wav = [os.path.join(carpeta_audios_local, f) for f in archivos_wav_locales]
    print(f"    ✅ {len(rutas_completas_wav)} archivos encontrados para análisis.")

    try:
        smile = opensmile.Smile(
            feature_set=opensmile.FeatureSet.eGeMAPSv02,
            feature_level=opensmile.FeatureLevel.Functionals
        )
        print(f"    Procesando {len(rutas_completas_wav)} archivos con el set eGeMAPSv02...")
        df_features_full = smile.process_files(rutas_completas_wav)

        # Guardar análisis completo
        os.makedirs(carpeta_salida_local, exist_ok=True)
        ruta_csv_completo_local = os.path.join(carpeta_salida_local, "Analisis_openSMILE_Completo.csv")
        df_features_full.to_csv(ruta_csv_completo_local)
        print(f"    ✅ Análisis completo guardado en: {ruta_csv_completo_local}")

        # Seleccionar características relevantes
        feature_mapping = {
            'Intensidad': 'loudness_sma3_amean', 
            'Entonación': 'F0semitoneFrom27.5Hz_sma3nz_amean',
            'Ritmo': 'VoicedSegmentsPerSec', 
            'Duración': 'MeanUnvoicedSegmentLength'
        }
        
        # Verificar que las columnas existen
        columnas_disponibles = df_features_full.columns.tolist()
        feature_mapping_filtrado = {k: v for k, v in feature_mapping.items() if v in columnas_disponibles}
        
        if not feature_mapping_filtrado:
            print("    ⚠️ No se encontraron las características esperadas en el análisis.")
            return None
            
        df_selected = df_features_full[list(feature_mapping_filtrado.values())].copy()
        df_selected.columns = list(feature_mapping_filtrado.keys())

        # Normalización
        def normalize_zscore_1_5(df, columns):
            df_norm = df.copy()
            for col in columns:
                mean, std = df_norm[col].mean(), df_norm[col].std()
                if std == 0 or pd.isna(std): 
                    df_norm[col] = 3
                    continue
                z = (df_norm[col] - mean) / std
                min_z, max_z = z.min(), z.max()
                df_norm[col] = 1 + 4 * (z - min_z) / (max_z - min_z) if max_z != min_z else 3
                df_norm[col] = df_norm[col].clip(1, 5)
            return df_norm

        df_normalized = normalize_zscore_1_5(df_selected, list(feature_mapping_filtrado.keys()))
        df_normalized.reset_index(inplace=True)
        df_normalized['Archivo'] = df_normalized['file'].apply(lambda f: os.path.basename(f))

        # Parsear nombres de archivo
        regex_pattern = r'^(?P<Video_ID>.+?)_(?P<Locutor>Andrea|Sergio|Sebastian)_(?P<Emocion>.+)\.wav$'
        df_parsed = df_normalized['Archivo'].str.extract(regex_pattern)
        df_normalized = pd.concat([df_normalized, df_parsed], axis=1)

        # Correcciones de nombres de emociones
        correcciones = {
            "extasis": "Éxtasis", "aceptacion": "Aceptación", "admiracion": "Admiración", 
            "aprension": "Aprensión", "distraccion": "Distracción", "asombro": "Asombro", 
            "pensamientoprofundo": "Pensamiento profundo", "duelo": "Duelo", 
            "aburrimiento": "Aburrimiento", "aversion": "Aversión", "molestia": "Molestia", 
            "furia": "Furia", "interes": "Interés", "vigilancia": "Vigilancia"
        }
        if 'Emocion' in df_normalized.columns:
            df_normalized["Emocion"] = df_normalized["Emocion"].str.replace(' ', '').str.lower().map(correcciones).fillna(df_normalized["Emocion"])

        print("    ✅ Análisis y selección de características finalizado.")
        return df_normalized
        
    except Exception as e:
        print(f"    ❌ Error durante el análisis con openSMILE: {e}")
        return None

    print(f"    ✅ {len(rutas_locales_wav)} archivos descargados a una carpeta temporal.")

    smile = opensmile.Smile(
        feature_set=opensmile.FeatureSet.eGeMAPSv02,
        feature_level=opensmile.FeatureLevel.Functionals
    )
    print(f"    Procesando {len(rutas_locales_wav)} archivos con el set eGeMAPSv02...")
    df_features_full = smile.process_files(rutas_locales_wav)

    ruta_csv_completo_local = os.path.join(LOCAL_OUTPUT_DIR, "Analisis_openSMILE_Completo.csv")
    df_features_full.to_csv(ruta_csv_completo_local)
    print(f"    Subiendo análisis completo a la carpeta 'Evaluación prosódica'...")
    subir_archivo(service, ruta_csv_completo_local, id_carpeta_salida)

    feature_mapping = {
        'Intensidad': 'loudness_sma3_amean', 'Entonación': 'F0semitoneFrom27.5Hz_sma3nz_amean',
        'Ritmo': 'VoicedSegmentsPerSec', 'Duración': 'MeanUnvoicedSegmentLength'
    }
    df_selected = df_features_full[list(feature_mapping.values())].copy()
    df_selected.columns = list(feature_mapping.keys())

    def normalize_zscore_1_5(df, columns):
        df_norm = df.copy()
        for col in columns:
            mean, std = df_norm[col].mean(), df_norm[col].std()
            if std == 0 or pd.isna(std): df_norm[col] = 3; continue
            z = (df_norm[col] - mean) / std
            min_z, max_z = z.min(), z.max()
            df_norm[col] = 1 + 4 * (z - min_z) / (max_z - min_z) if max_z != min_z else 3
            df_norm[col] = df_norm[col].clip(1, 5)
        return df_norm

    df_normalized = normalize_zscore_1_5(df_selected, list(feature_mapping.keys()))
    df_normalized.reset_index(inplace=True)
    df_normalized['Archivo'] = df_normalized['file'].apply(lambda f: os.path.basename(f))

    regex_pattern = r'^(?P<Video_ID>.+?)_(?P<Locutor>Andrea|Sergio|Sebastian)_(?P<Emocion>.+)\.wav$'
    df_parsed = df_normalized['Archivo'].str.extract(regex_pattern)
    df_normalized = pd.concat([df_normalized, df_parsed], axis=1)

    correcciones = {"extasis": "Éxtasis", "aceptacion": "Aceptación", "admiracion": "Admiración", "aprension": "Aprensión", "distraccion": "Distracción", "asombro": "Asombro", "pensamientoprofundo": "Pensamiento profundo", "duelo": "Duelo", "aburrimiento": "Aburrimiento", "aversion": "Aversión", "molestia": "Molestia", "furia": "Furia", "interes": "Interés", "vigilancia": "Vigilancia"}
    df_normalized["Emocion"] = df_normalized["Emocion"].str.replace(' ', '').str.lower().map(correcciones).fillna(df_normalized["Emocion"])

    print("    ✅ Análisis y selección de características finalizado.")
    return df_normalized

def _crear_grafica_radar(ax, angles, features, valores, titulo, color, etiqueta=''):
    ax.plot(angles, valores, 'o-', linewidth=2, color=color, label=etiqueta)
    ax.fill(angles, valores, alpha=0.2, color=color)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(features, fontsize=8)
    ax.set_yticks(range(1, 6))
    ax.set_ylim(0, 5)
    ax.set_title(titulo, y=1.1, fontdict={'fontsize': 12, 'fontweight': 'bold'})

def graficar_y_subir(fig, service, nombre_archivo, id_carpeta_salida):
    ruta_local = os.path.join(LOCAL_OUTPUT_DIR, nombre_archivo)
    fig.savefig(ruta_local, dpi=150)
    plt.close(fig) # Cierra la figura para liberar memoria
    print(f"    Subiendo '{nombre_archivo}'...")
    subir_archivo(service, ruta_local, id_carpeta_salida)

def graficar_comparativa_emociones(df_norm, service, id_carpeta_salida, angles, features):
    print("\n--- Generando Gráfica Comparativa de Emociones ---")
    df_promedio = df_norm.groupby("Emocion")[features].mean()

    fig, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(polar=True))
    colormap = plt.cm.get_cmap('gist_rainbow', len(df_promedio))

    for i, (emocion, row) in enumerate(df_promedio.iterrows()):
        valores = row.tolist() + [row[0]]
        _crear_grafica_radar(ax, angles, features, valores, "Análisis Promedio por Emoción", colormap(i), etiqueta=emocion)

    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    plt.tight_layout()
    graficar_y_subir(fig, service, "Grafica_Comparativa_Emociones.png", id_carpeta_salida)

def graficar_promedio_por_video(df_norm, service, id_carpeta_salida, angles, features):
    print("\n--- Generando Gráfica de Promedios por Video ---")
    df_promedio = df_norm.groupby("Video_ID")[features].mean()
    num_videos = len(df_promedio)
    num_cols = min(num_videos, 4)
    num_rows = (num_videos + num_cols - 1) // num_cols

    fig, axes = plt.subplots(figsize=(20, 5 * num_rows), nrows=num_rows, ncols=num_cols, subplot_kw=dict(polar=True))
    axes = axes.flatten()

    for i, (video_id, row) in enumerate(df_promedio.iterrows()):
        valores = row.tolist() + [row[0]]
        _crear_grafica_radar(axes[i], angles, features, valores, video_id, "darkorange")

    for j in range(i + 1, len(axes)): fig.delaxes(axes[j])
    fig.suptitle("Análisis Prosódico Promedio por Video", fontsize=16)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    graficar_y_subir(fig, service, "Grafica_Promedio_Videos.png", id_carpeta_salida)

def graficar_comparativa_locutores_por_video(df_norm, service, id_carpeta_salida, angles, features):
    print("\n--- Generando Gráfica Comparativa de Locutores por Video ---")
    videos = df_norm["Video_ID"].unique()
    num_videos = len(videos)
    num_cols = min(num_videos, 4)
    num_rows = (num_videos + num_cols - 1) // num_cols

    colores_locutor = {'Andrea': 'red', 'Sergio': 'blue', 'Sebastian': 'green'}

    fig, axes = plt.subplots(figsize=(20, 5 * num_rows), nrows=num_rows, ncols=num_cols, subplot_kw=dict(polar=True))
    axes = axes.flatten()

    for i, video_id in enumerate(videos):
        ax = axes[i]
        df_video = df_norm[df_norm["Video_ID"] == video_id]
        for locutor, color in colores_locutor.items():
            df_locutor = df_video[df_video["Locutor"] == locutor]
            if not df_locutor.empty:
                valores = df_locutor[features].iloc[0].tolist() + [df_locutor[features].iloc[0, 0]]
                _crear_grafica_radar(ax, angles, features, valores, video_id, color, etiqueta=locutor)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize='small')

    for j in range(i + 1, len(axes)): fig.delaxes(axes[j])
    fig.suptitle("Comparativa de Locutores por Video", fontsize=16)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    graficar_y_subir(fig, service, "Grafica_Comparativa_Locutores.png", id_carpeta_salida)

def generar_graficas_analisis(df_norm, service, id_carpeta_salida):
    if df_norm is None or df_norm.empty:
        print("\n    ⚠️ No se generaron datos de análisis para graficar.")
        return

    print("\n--- 🎨 2. Iniciando Generación de Gráficas ---")
    columnas_graficas = ["Intensidad", "Entonación", "Ritmo", "Duración"]
    angles = np.linspace(0, 2 * np.pi, len(columnas_graficas), endpoint=False).tolist() + [0]

    graficar_comparativa_emociones(df_norm, service, id_carpeta_salida, angles, columnas_graficas)
    graficar_promedio_por_video(df_norm, service, id_carpeta_salida, angles, columnas_graficas)
    graficar_comparativa_locutores_por_video(df_norm, service, id_carpeta_salida, angles, columnas_graficas)


def generar_graficas_analisis_local(df_norm, carpeta_salida):
    """Generar gráficas de análisis prosódico en archivos locales"""
    if df_norm is None or df_norm.empty:
        print("\n    ⚠️ No se generaron datos de análisis para graficar.")
        return

    print("\n--- 🎨 2. Iniciando Generación de Gráficas ---")
    columnas_graficas = ["Intensidad", "Entonación", "Ritmo", "Duración"]
    # Filtrar solo las columnas que existen
    columnas_disponibles = [col for col in columnas_graficas if col in df_norm.columns]
    
    if not columnas_disponibles:
        print("    ⚠️ No se encontraron columnas válidas para graficar.")
        return
        
    angles = np.linspace(0, 2 * np.pi, len(columnas_disponibles), endpoint=False).tolist() + [0]

    os.makedirs(carpeta_salida, exist_ok=True)

    # Gráfica comparativa de emociones (si existe la columna Emocion)
    if 'Emocion' in df_norm.columns and not df_norm['Emocion'].isnull().all():
        print("\n--- Generando Gráfica Comparativa de Emociones ---")
        df_promedio = df_norm.groupby("Emocion")[columnas_disponibles].mean()

        fig, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(polar=True))
        colormap = plt.cm.get_cmap('gist_rainbow', len(df_promedio))

        for i, (emocion, row) in enumerate(df_promedio.iterrows()):
            valores = row.tolist() + [row.iloc[0]]
            _crear_grafica_radar(ax, angles, columnas_disponibles, valores, "Análisis Promedio por Emoción", colormap(i), etiqueta=emocion)

        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        plt.tight_layout()
        
        ruta_grafica = os.path.join(carpeta_salida, "Grafica_Comparativa_Emociones.png")
        fig.savefig(ruta_grafica, dpi=150)
        plt.close(fig)
        print(f"    ✅ Gráfica guardada: {ruta_grafica}")

    # Gráfica promedio por video (si existe la columna Video_ID)
    if 'Video_ID' in df_norm.columns and not df_norm['Video_ID'].isnull().all():
        print("\n--- Generando Gráfica de Promedios por Video ---")
        df_promedio = df_norm.groupby("Video_ID")[columnas_disponibles].mean()
        num_videos = len(df_promedio)
        
        if num_videos > 0:
            num_cols = min(num_videos, 4)
            num_rows = (num_videos + num_cols - 1) // num_cols

            fig, axes = plt.subplots(figsize=(20, 5 * num_rows), nrows=num_rows, ncols=num_cols, subplot_kw=dict(polar=True))
            if num_videos == 1:
                axes = [axes]
            elif num_rows == 1:
                axes = axes if isinstance(axes, (list, np.ndarray)) else [axes]
            else:
                axes = axes.flatten()

            for i, (video_id, row) in enumerate(df_promedio.iterrows()):
                valores = row.tolist() + [row.iloc[0]]
                _crear_grafica_radar(axes[i], angles, columnas_disponibles, valores, video_id, "darkorange")

            for j in range(i + 1, len(axes)): 
                fig.delaxes(axes[j])
            
            fig.suptitle("Análisis Prosódico Promedio por Video", fontsize=16)
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            
            ruta_grafica = os.path.join(carpeta_salida, "Grafica_Promedio_Videos.png")
            fig.savefig(ruta_grafica, dpi=150)
            plt.close(fig)
            print(f"    ✅ Gráfica guardada: {ruta_grafica}")

def ejecutar_analisis_completo_local():
    """Función principal para ejecutar análisis prosódico local"""
    print("\n" + "="*80)
    print("###      INICIANDO FASE DE EVALUACIÓN PROSÓDICA LOCAL      ###")
    print("="*80)

    # Analizar archivos de audio en la carpeta de salida
    carpeta_evaluacion = os.path.join(TEMP_BASE_DIR, "evaluacion_prosodica")
    df_analisis = analizar_prosodia_opensmile_local(LOCAL_OUTPUT_DIR, carpeta_evaluacion)

    if df_analisis is not None:
        generar_graficas_analisis_local(df_analisis, carpeta_evaluacion)

        # Guardar reporte CSV final
        ruta_csv_final_local = os.path.join(carpeta_evaluacion, "Analisis_Prosodico_Normalizado.csv")
        df_analisis.to_csv(ruta_csv_final_local, index=False)
        print(f"\n    ✅ Reporte CSV guardado: {ruta_csv_final_local}")
    else:
        print("\n    ⚠️ No se pudo completar el análisis prosódico.")

    print("\n" + "#"*80)
    print("###      EVALUACIÓN PROSÓDICA FINALIZADA      ###")
    print("#"*80)

    return df_analisis

"""## 6. Función Principal de Ejecución Local

Esta función coordina todo el proceso de generación de audiodescripciones trabajando con archivos locales.
"""

def ejecutar_pipeline_completo_local(temp_dir="temp", ejecutar_analisis_prosodico=True, ejecutar_mezcla=True):
    """
    Ejecuta el pipeline completo de generación de audiodescripciones de forma local
    
    Args:
        temp_dir: Directorio temporal donde se encuentran los archivos
        ejecutar_analisis_prosodico: Si ejecutar el análisis prosódico
        ejecutar_mezcla: Si ejecutar la mezcla final
    """
    print("\n" + "="*100)
    print("###      🚀 INICIANDO PIPELINE COMPLETO DE AUDIODESCRIPCIONES LOCAL      ###")
    print("="*100)
    
    try:
        # 1. Generar audios TTS
        print("\n📝 PASO 1: Generando audios TTS...")
        archivos_generados = procesar_generacion_local()
        
        if not archivos_generados:
            print("❌ No se generaron archivos de audio. Terminando...")
            return
            
        print(f"✅ Se generaron {len(archivos_generados)} archivos de audio")
        
        # 2. Análisis prosódico (opcional)
        if ejecutar_analisis_prosodico:
            print("\n📊 PASO 2: Ejecutando análisis prosódico...")
            df_analisis = ejecutar_analisis_completo_local()
            if df_analisis is not None:
                print("✅ Análisis prosódico completado")
            else:
                print("⚠️ El análisis prosódico no se pudo completar")
        else:
            print("\n⏭️ PASO 2: Análisis prosódico omitido")
        
        # 3. Mezcla final (opcional)
        if ejecutar_mezcla:
            print("\n🎧 PASO 3: Ejecutando mezcla final...")
            mezclar_audios_con_ffmpeg_local(temp_dir=temp_dir)
            print("✅ Mezcla final completada")
        else:
            print("\n⏭️ PASO 3: Mezcla final omitida")
            
        # 4. Resumen final
        print("\n" + "="*100)
        print("###      ✨ PIPELINE COMPLETO FINALIZADO EXITOSAMENTE      ###")
        print("="*100)
        
        print("\n📁 ARCHIVOS GENERADOS:")
        print(f"  • Audios TTS: {LOCAL_OUTPUT_DIR}")
        if ejecutar_analisis_prosodico:
            print(f"  • Análisis prosódico: {os.path.join(TEMP_BASE_DIR, 'evaluacion_prosodica')}")
        if ejecutar_mezcla:
            print(f"  • Mezclas finales: {os.path.join(TEMP_BASE_DIR, 'mezclas_finales')}")
            
        return {
            'audios_generados': archivos_generados,
            'analisis_completado': ejecutar_analisis_prosodico,
            'mezcla_completada': ejecutar_mezcla
        }
        
    except Exception as e:
        print(f"\n❌ ERROR EN EL PIPELINE: {e}")
        import traceback
        traceback.print_exc()
        return None

# Comentar las ejecuciones automáticas para permitir uso manual
# Si deseas ejecutar automáticamente, descomenta las siguientes líneas:

# print("\n🔥 EJECUTANDO PIPELINE COMPLETO...")
# resultado = ejecutar_pipeline_completo_local(
#     temp_dir=TEMP_BASE_DIR,
#     ejecutar_analisis_prosodico=True,
#     ejecutar_mezcla=True
# )

print("\n" + "="*80)
print("📋 INSTRUCCIONES DE USO:")
print("="*80)
print("Para ejecutar el pipeline completo, usar:")
print("  resultado = ejecutar_pipeline_completo_local()")
print("\nPara ejecutar solo generación TTS:")
print("  archivos = procesar_generacion_local()")
print("\nPara ejecutar solo análisis prosódico:")
print("  analisis = ejecutar_analisis_completo_local()")
print("\nPara ejecutar solo mezcla:")
print("  mezclar_audios_con_ffmpeg_local()")
print("="*80)

"""## 5. Ducking y Sincronización Local

El siguiente script automatiza la post-producción de la pista de audio final usando archivos locales. El proceso es el siguiente:

1.  **Carga los Archivos**: Toma el video original y el archivo `JSON` con los tiempos precisos desde la carpeta temporal.
2.  **Extrae el Audio Base**: Obtiene la pista de audio original del archivo de video.
3.  **Aplica Ducking**: Atenúa automáticamente el volumen del audio base durante los intervalos especificados.
4.  **Sincroniza y Mezcla**: Carga cada audio de diálogo generado y lo inserta en la pista base.
5.  **Exporta los Resultados**: Genera archivos de audio final en la carpeta temporal.
"""

def find_file_local(folder_path, file_pattern):
    """Buscar archivo en carpeta local que coincida con el patrón"""
    if not os.path.exists(folder_path):
        return None
        
    for filename in os.listdir(folder_path):
        if re.search(file_pattern, filename, re.IGNORECASE):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                print(f"    -> Archivo encontrado: {filename}")
                return {'name': filename, 'path': file_path}
    
    print(f"    ⚠️ No se encontró ningún archivo que coincida con '{file_pattern}' en {folder_path}")
    return None

def mezclar_audios_con_ffmpeg_local(temp_dir="temp", locutores_a_mezclar=None):
    """Mezcla de audios usando archivos locales"""
    if locutores_a_mezclar is None:
        locutores_a_mezclar = ["Andrea", "Sergio", "Sebastian"]
        
    print("\n" + "="*80)
    print("###      🎧 INICIANDO PROCESO DE MEZCLA LOCAL (FFmpeg)      ###")
    print("="*80)

    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"    -> Usando FFmpeg desde: {ffmpeg_path}")

        print("\n--- 📂 1. Buscando archivos base locales ---")
        
        # Buscar video original en la carpeta temp
        video_file_info = find_file_local(temp_dir, r'\.(mp4|mov|avi|mkv)$')
        
        # Buscar archivo JSON de tiempos - puede estar en diferentes ubicaciones
        json_file_info = None
        posibles_rutas_json = [
            temp_dir,
            os.path.join(temp_dir, "diarization"),
            "."  # directorio actual
        ]
        
        for ruta in posibles_rutas_json:
            if os.path.exists(ruta):
                json_file_info = find_file_local(ruta, r'(Main_Video|silent_segments_joined|speaker_segments)\.json$')
                if json_file_info:
                    break

        if not video_file_info:
            print("❌ Error: No se encontró el video original.")
            return
            
        if not json_file_info:
            print("❌ Error: No se encontró el archivo JSON de tiempos.")
            print("    Rutas buscadas:", posibles_rutas_json)
            return

        local_video_path = video_file_info['path']
        local_json_path = json_file_info['path']
        
        print(f"    -> Video: {local_video_path}")
        print(f"    -> JSON: {local_json_path}")

        # Cargar segmentos de tiempo
        with open(local_json_path, 'r', encoding='utf-8') as f:
            datos_json = json.load(f)
            
        # Adaptar formato según el tipo de archivo JSON
        segmentos = []
        if isinstance(datos_json, list):
            # Si es una lista directa de segmentos
            segmentos = sorted(datos_json, key=lambda x: x.get('start', 0))
        elif 'segments' in datos_json:
            # Si tiene una clave 'segments'
            segmentos = sorted(datos_json['segments'], key=lambda x: x.get('start', 0))
        else:
            print("❌ Error: Formato de JSON no reconocido.")
            return

        print(f"    -> Se encontraron {len(segmentos)} segmentos de tiempo")

        print("\n--- 🎤 2. Buscando audios generados ---")
        audios_generados = []
        if os.path.exists(LOCAL_OUTPUT_DIR):
            for filename in os.listdir(LOCAL_OUTPUT_DIR):
                if filename.lower().endswith('.wav') and not filename.startswith('temp_'):
                    audios_generados.append(filename)
        
        print(f"    -> ✅ {len(audios_generados)} audios de diálogo encontrados.")

        # Crear carpeta de salida para las mezclas
        carpeta_mezclas = os.path.join(TEMP_BASE_DIR, "mezclas_finales")
        os.makedirs(carpeta_mezclas, exist_ok=True)

        for locutor in locutores_a_mezclar:
            print("\n" + "-"*60)
            print(f"    GENERANDO MEZCLA PARA: {locutor.upper()}")
            print("-"*60)

            comando_ffmpeg = [ffmpeg_path, '-y', '-i', local_video_path]
            inputs_dialogo = []

            # Buscar audios para este locutor
            for segment in segmentos:
                segmento_id = str(segment.get('id', ''))
                encontrado = None
                
                for nombre_archivo in audios_generados:
                    if (segmento_id in nombre_archivo or 
                        f"segment_{segmento_id.zfill(3)}" in nombre_archivo) and \
                       (locutor in nombre_archivo) and \
                       nombre_archivo.lower().endswith('.wav'):
                        encontrado = nombre_archivo
                        break
                
                if encontrado:
                    ruta_encontrada = os.path.join(LOCAL_OUTPUT_DIR, encontrado)
                    inputs_dialogo.append({
                        'path': ruta_encontrada, 
                        'start': segment.get('start', 0)
                    })
                    comando_ffmpeg.extend(['-i', ruta_encontrada])

            if not inputs_dialogo:
                print(f"    ⚠️ No se encontraron diálogos para {locutor}. Saltando...")
                continue

            print(f"    -> Se encontraron {len(inputs_dialogo)} diálogos para {locutor}")

            # Construir filtro de ducking
            filtro = ""
            ducking_filter = "[0:a]"
            for segment in segmentos:
                start_s = segment.get('start', 0)
                end_s = segment.get('end', 0)
                ducking_filter += f"volume=enable='between(t,{start_s},{end_s})':volume=0.125,"
            ducking_filter = ducking_filter.rstrip(',') + "[audio_base];"
            filtro += ducking_filter

            # Agregar filtros para cada diálogo
            streams_para_mezclar = "[audio_base]"
            for i, dialogo in enumerate(inputs_dialogo):
                input_index = i + 1
                start_ms = int(dialogo['start'] * 1000)
                filtro += f"[{input_index}:a]highpass=f=100,equalizer=f=3000:width_type=h:width=2000:g=3,adelay={start_ms}|{start_ms}[dialogo{i}];"
                streams_para_mezclar += f"[dialogo{i}]"

            filtro += f"{streams_para_mezclar}amix=inputs={len(inputs_dialogo) + 1},loudnorm[audio_final]"

            # Archivo de salida
            nombre_salida = f"Audiodescripcion_{locutor}.wav"
            ruta_salida_local = os.path.join(carpeta_mezclas, nombre_salida)

            comando_ffmpeg.extend([
                '-filter_complex', filtro,
                '-map', '[audio_final]',
                ruta_salida_local
            ])

            print("    -> ⚙️ Ejecutando FFmpeg para procesar el audio...")
            resultado = subprocess.run(comando_ffmpeg, capture_output=True, text=True, encoding='utf-8')

            if resultado.returncode == 0:
                print(f"    -> ✅ Audio '{nombre_salida}' generado exitosamente.")
                print(f"    -> � Guardado en: {ruta_salida_local}")
                
                # Mostrar información del archivo generado
                try:
                    audio_info = AudioSegment.from_wav(ruta_salida_local)
                    print(f"    -> 📊 Duración: {len(audio_info)/1000:.2f}s")
                except:
                    pass
                    
            else:
                print(f"    ❌ ERROR al ejecutar FFmpeg para {locutor}.")
                print("\n--- Log de Error de FFmpeg ---")
                print(resultado.stderr)
                print("--- Fin del Log ---")

    except Exception as e:
        print(f"❌ Ocurrió un error inesperado en el script: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "#"*80)
    print("###      ✨ PROCESO DE MEZCLA LOCAL FINALIZADO      ###")
    print("#"*80)

# Ejecutar el proceso de mezcla local
# print("\n--- Iniciando proceso de mezcla con archivos locales ---")
# LOCUTORES_PARA_LA_MEZCLA = ["Andrea", "Sergio", "Sebastian"]
# mezclar_audios_con_ffmpeg_local(
#     temp_dir=TEMP_BASE_DIR,
#     locutores_a_mezclar=LOCUTORES_PARA_LA_MEZCLA
# )