import os
import json
import re
import unicodedata
import time
import torch
import nltk
from TTS.api import TTS
from openai import OpenAI
from thefuzz import fuzz
from pydub import AudioSegment
from pydub.silence import split_on_silence
import noisereduce as nr
import soundfile as sf
from IPython.display import Audio, display
import numpy as np
import pandas as pd
import opensmile
import matplotlib.pyplot as plt
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io
import os

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
os.makedirs("temp_drive_files", exist_ok=True)
os.makedirs("temp_output", exist_ok=True)
LOCAL_TEMP_DIR = "temp_drive_files"
LOCAL_OUTPUT_DIR = "temp_output"
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
from IPython.display import display
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
# --- LECTURA Y PREPARACIÓN DE LAS TAREAS DESDE GOOGLE DRIVE ---
tareas_de_generacion = []
print("--- Analizando la carpeta 'Input' en Google Drive y extrayendo datos ---")

carpetas_de_videos = [
    item for item in listar_archivos(drive_service, FOLDER_ID_INPUT)  # <-- CAMBIO CLAVE
    if item['mimeType'] == 'application/vnd.google-apps.folder'
]
print(f"Se encontraron {len(carpetas_de_videos)} carpetas de video para analizar.")

for video_folder in carpetas_de_videos:
    video_id_folder = video_folder['name']
    folder_id = video_folder['id']
    print(f"  Analizando subcarpeta: '{video_id_folder}'...")

    try:
        archivos_en_carpeta = listar_archivos(drive_service, folder_id)

        summary_file = next((f for f in archivos_en_carpeta if f['name'] == 'video_summary.json'), None)
        prosody_file = next((f for f in archivos_en_carpeta if f['name'] == 'prosody_analysis.json'), None)

        if summary_file and prosody_file:
            local_summary_path = descargar_archivo(drive_service, summary_file['id'], os.path.join(LOCAL_TEMP_DIR, f"{video_id_folder}_summary.json"))
            local_prosody_path = descargar_archivo(drive_service, prosody_file['id'], os.path.join(LOCAL_TEMP_DIR, f"{video_id_folder}_prosody.json"))

            if local_summary_path and local_prosody_path:
                with open(local_summary_path, 'r', encoding='utf-8') as f:
                    datos_summary = json.load(f)
                with open(local_prosody_path, 'r', encoding='utf-8') as f:
                    datos_prosody = json.load(f)

                my_text = limpiar_texto_summary(datos_summary["main_summary"])

                tareas_de_generacion.append({
                    "Video ID": video_id_folder,
                    "Texto a Generar": my_text,
                    "Emoción": datos_prosody["complementary_emotion"]
                })
                print(f"    -> Tarea para '{video_id_folder}' cargada exitosamente.")
        else:
            print(f"    -> Omitiendo '{video_id_folder}': No se encontraron los archivos video_summary.json o prosody_analysis.json.")

    except Exception as e:
        print(f"    -> Omitiendo '{video_id_folder}': Ocurrió un error inesperado. Error: {e}")

if tareas_de_generacion:
    df_tareas = pd.DataFrame(tareas_de_generacion)
    print("\n--- RESUMEN DE TAREAS A REALIZAR ---")
    display(df_tareas)
else:
    print("\nNo se encontraron tareas válidas para procesar.")

# --- BUCLE PRINCIPAL DE GENERACIÓN---
locutores = ["Andrea", "Sergio", "Sebastian"]
max_intentos_por_chunk = 3

if not tareas_de_generacion:
    print("La lista de tareas está vacía. No se generará ningún audio.")
else:
    for tarea_idx, tarea in enumerate(tareas_de_generacion):
        video_id, texto_a_generar, emocion_a_buscar = tarea["Video ID"], tarea["Texto a Generar"], tarea["Emoción"]

        print("\n" + "="*80)
        print(f"📄 TAREA {tarea_idx + 1} de {len(tareas_de_generacion)} | VIDEO: {video_id} | EMOCIÓN: {emocion_a_buscar}")
        print("="*80)

        chunks = split_text_into_chunks(texto_a_generar)

        for locutor in locutores:
            print(f"\n  🎤 Procesando para el locutor: {locutor}")

            ruta_referencia_voz_local = encontrar_y_descargar_referencia_drive(drive_service, FOLDER_ID_EMOCIONES_BASE, locutor, emocion_a_buscar)

            if not ruta_referencia_voz_local:
                print(f"    ❌ No se encontró audio de referencia. Saltando a siguiente locutor.")
                continue

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
                    print(f"    ✨ Audio final procesado localmente. Subiendo a la carpeta 'AD' en Drive...")
                    display(Audio(ruta_local_procesado, autoplay=False))

                    subir_archivo(drive_service, ruta_local_procesado, FOLDER_ID_OUTPUT_PROCESADOS)

            archivos_a_limpiar = temp_audio_files + [ruta_referencia_voz_local]
            if temp_audio_files and 'ruta_local_generado' in locals():
                archivos_a_limpiar.extend([ruta_local_generado, ruta_local_procesado])

            for temp_file in archivos_a_limpiar:
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)

    print("\n\n" + "#"*80)
    print("###      PROCESO COMPLETO DE GENERACIÓN FINALIZADO      ###")
    print("#"*80)

import opensmile
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

def analizar_prosodia_opensmile(service, id_carpeta_audios, id_carpeta_salida):
    print("\n--- 🔎 1. Analizando archivos de audio con openSMILE ---")

    print(f"    Descargando archivos .wav desde la carpeta 'AD'...")
    archivos_en_drive = listar_archivos(service, id_carpeta_audios)
    archivos_wav_drive = [f for f in archivos_en_drive if f['name'].lower().endswith(".wav")]

    if not archivos_wav_drive:
        print(f"    ⚠️ No se encontraron archivos .wav en la carpeta de Drive. No se puede continuar.")
        return None

    rutas_locales_wav = []
    for archivo_drive in archivos_wav_drive:
        ruta_local = os.path.join(LOCAL_TEMP_DIR, archivo_drive['name'])
        descargar_archivo(service, archivo_drive['id'], ruta_local)
        rutas_locales_wav.append(ruta_local)

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


def ejecutar_analisis_completo(service, id_carpeta_audios, id_carpeta_evaluacion):
    print("\n" + "="*80)
    print("###      INICIANDO FASE DE EVALUACIÓN PROSÓDICA      ###")
    print("="*80)

    df_analisis = analizar_prosodia_opensmile(service, id_carpeta_audios, id_carpeta_evaluacion)

    generar_graficas_analisis(df_analisis, service, id_carpeta_evaluacion)

    if df_analisis is not None and not df_analisis.empty:
        ruta_csv_final_local = os.path.join(LOCAL_OUTPUT_DIR, "Analisis_Prosodico_Normalizado.csv")
        df_analisis.to_csv(ruta_csv_final_local, index=False)
        print("\n    Subiendo reporte CSV final...")
        subir_archivo(service, ruta_csv_final_local, id_carpeta_evaluacion)

    for f in os.listdir(LOCAL_TEMP_DIR): os.remove(os.path.join(LOCAL_TEMP_DIR, f))
    for f in os.listdir(LOCAL_OUTPUT_DIR): os.remove(os.path.join(LOCAL_OUTPUT_DIR, f))

    print("\n" + "#"*80)
    print("###      EVALUACIÓN PROSÓDICA FINALIZADA      ###")
    print("#"*80)

ejecutar_analisis_completo(
    service=drive_service,
    id_carpeta_audios=FOLDER_ID_AD,
    id_carpeta_evaluacion=FOLDER_ID_EVALUACION
)

import json
import os
import re
import subprocess
import imageio_ffmpeg

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

def find_file_in_drive(service, folder_id, file_pattern):
    files = listar_archivos(service, folder_id)
    for f in files:
        if re.search(file_pattern, f['name'], re.IGNORECASE):
            print(f"    -> Archivo encontrado en Drive: {f['name']}")
            return f
    print(f"    ⚠️ No se encontró ningún archivo que coincida con '{file_pattern}' en la carpeta especificada.")
    return None

def mezclar_audios_con_ffmpeg_drive(service, id_input, id_ad, id_output, locutores_a_mezclar):
    print("\n" + "="*80)
    print("###      🎧 INICIANDO PROCESO DE MEZCLA (MÉTODO FFmpeg)      ###")
    print("="*80)

    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"    -> Usando FFmpeg desde: {ffmpeg_path}")

        print("\n--- 📂 1. Buscando y descargando archivos base ---")
        video_file_info = find_file_in_drive(service, id_input, r'\.(mp4|mov)$')
        json_file_info = find_file_in_drive(service, id_input, r'Main_Video\.json$')

        if not video_file_info or not json_file_info:
            print("❌ Error: Faltan el video original o el archivo Main_Video.json.")
            return

        local_video_path = descargar_archivo(service, video_file_info['id'], os.path.join(LOCAL_TEMP_DIR, video_file_info['name']))
        local_json_path = descargar_archivo(service, json_file_info['id'], os.path.join(LOCAL_TEMP_DIR, json_file_info['name']))

        with open(local_json_path, 'r', encoding='utf-8') as f:
            segmentos = sorted(json.load(f), key=lambda x: x.get('start', 0))

        print("\n--- 🎤 2. Descargando audios de la carpeta 'AD' ---")
        audios_ad_drive = [f for f in listar_archivos(service, id_ad) if f['name'].lower().endswith('.wav')]
        for audio_info in audios_ad_drive:
            descargar_archivo(service, audio_info['id'], os.path.join(LOCAL_TEMP_DIR, audio_info['name']))
        print(f"    -> ✅ {len(audios_ad_drive)} audios de diálogo descargados.")

        for locutor in locutores_a_mezclar:
            print("\n" + "-"*60)
            print(f"    GENERANDO MEZCLA PARA: {locutor.upper()}")
            print("-"*60)

            comando_ffmpeg = [ffmpeg_path, '-y', '-i', local_video_path]
            inputs_dialogo = []
            archivos_locales = os.listdir(LOCAL_TEMP_DIR)

            for segment in segmentos:
                segmento_id = str(segment.get('id', ''))
                encontrado = None
                for nombre_archivo in archivos_locales:
                    if (segmento_id in nombre_archivo) and (locutor in nombre_archivo) and nombre_archivo.lower().endswith('.wav'):
                        encontrado = nombre_archivo
                        break
                if encontrado:
                    ruta_encontrada = os.path.join(LOCAL_TEMP_DIR, encontrado)
                    inputs_dialogo.append({'path': ruta_encontrada, 'start': segment.get('start', 0)})
                    comando_ffmpeg.extend(['-i', ruta_encontrada])

            if not inputs_dialogo:
                print(f"    ⚠️ No se encontraron diálogos para {locutor}. Saltando...")
                continue

            filtro = ""
            ducking_filter = "[0:a]"
            for segment in segmentos:
                start_s = segment.get('start', 0)
                end_s = segment.get('end', 0)
                ducking_filter += f"volume=enable='between(t,{start_s},{end_s})':volume=0.125,"
            ducking_filter = ducking_filter.rstrip(',') + "[audio_base];"
            filtro += ducking_filter

            streams_para_mezclar = "[audio_base]"
            for i, dialogo in enumerate(inputs_dialogo):
                input_index = i + 1
                start_ms = int(dialogo['start'] * 1000)
                filtro += f"[{input_index}:a]highpass=f=100,equalizer=f=3000:width_type=h:width=2000:g=3,adelay={start_ms}|{start_ms}[dialogo{i}];"
                streams_para_mezclar += f"[dialogo{i}]"

            filtro += f"{streams_para_mezclar}amix=inputs={len(inputs_dialogo) + 1},loudnorm[audio_final]"

            nombre_salida = f"Audiodescripcion_{locutor}.wav"
            ruta_salida_local = os.path.join(LOCAL_OUTPUT_DIR, nombre_salida)

            comando_ffmpeg.extend([
                '-filter_complex', filtro,
                '-map', '[audio_final]',
                ruta_salida_local
            ])

            print("    -> ⚙️ Ejecutando FFmpeg para procesar el audio...")
            resultado = subprocess.run(comando_ffmpeg, capture_output=True, text=True, encoding='utf-8')

            if resultado.returncode == 0:
                print(f"    -> ✅ Audio '{nombre_salida}' generado exitosamente.")
                print(f"    -> 📤 Subiendo resultado a 'Output AD'...")
                subir_archivo(service, ruta_salida_local, id_output)
            else:
                print(f"    ❌ ERROR al ejecutar FFmpeg para {locutor}.")
                print("\n--- Log de Error de FFmpeg ---")
                print(resultado.stderr)
                print("--- Fin del Log ---")

    except Exception as e:
        print(f"❌ Ocurrió un error inesperado en el script: {e}")
    finally:
        for folder in [LOCAL_TEMP_DIR, LOCAL_OUTPUT_DIR]:
            for filename in os.listdir(folder):
                try:
                    os.remove(os.path.join(folder, filename))
                except OSError as e:
                    print(f"    -> No se pudo eliminar el archivo temporal {filename}: {e}")
        print("\n    -> Limpieza de archivos temporales completada.")

    print("\n" + "#"*80)
    print("###      ✨ TODOS LOS PROCESOS DE MEZCLA FINALIZADOS      ###")
    print("#"*80)

LOCUTORES_PARA_LA_MEZCLA = ["Andrea", "Sergio", "Sebastian"]

mezclar_audios_con_ffmpeg_drive(
    service=drive_service,
    id_input=FOLDER_ID_INPUT,
    id_ad=FOLDER_ID_AD,
    id_output=FOLDER_ID_OUTPUT_MAIN,
    locutores_a_mezclar=LOCUTORES_PARA_LA_MEZCLA
)