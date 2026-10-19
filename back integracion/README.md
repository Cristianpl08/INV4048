# Sistema Integrado de Diarización y Descripciones de Video

Este sistema procesa videos para crear segmentos con diarización de hablantes y generar descripciones automáticas usando OpenAI.

## Características

- ✅ Diarización de video (separación por hablantes)
- ✅ Segmentación automática de video
- ✅ Generación de descripciones con IA para cada segmento
- ✅ Análisis de keyframes y prosodia
- ✅ Subida automática a Google Drive
- ✅ Almacenamiento de metadatos en MongoDB

## Flujo de Procesamiento

1. **Upload del video** → Se carga el archivo de video
2. **Diarización** → Se ejecuta `Diarization.py` para separar hablantes
3. **Segmentación** → Se corta el video en segmentos basados en la diarización
4. **Descripciones** → Se procesan descripciones para cada segmento usando `Descriptions.py`
5. **Organización** → Se crean carpetas organizadas:
   - `diarization/` - Archivos JSON de diarización
   - `segments/` - Videos segmentados
   - `video/` - Video original
   - `descriptions/` - Descripciones generadas para cada segmento
6. **Upload a Drive** → Todo se sube a Google Drive
7. **MongoDB** → Se guardan metadatos y enlaces

## Estructura de Archivos Generados

```
proyecto_{id}/
├── diarization/
│   ├── silent_segments_joined.json
│   ├── speaker_segments.json
│   └── audio.wav
├── segments/
│   ├── segment_001_0.00s_15.50s.mp4
│   ├── segment_002_15.50s_32.10s.mp4
│   └── ...
├── video/
│   └── video_original.mp4
└── descriptions/
    ├── segment_001_descriptions/
    │   ├── keyframes/
    │   ├── audiodescriptions.json
    │   ├── prosody_analysis.json
    │   └── video_summary.json
    ├── segment_002_descriptions/
    │   └── ...
    └── ...
```

## Configuración Requerida

### 1. Variables de Entorno / Configuración

```python
# En app.py, configura:
CLIENT_ID = 'tu_google_client_id'
CLIENT_SECRET = 'tu_google_client_secret'
REFRESH_TOKEN = 'tu_refresh_token'
OPENAI_API_KEY = 'tu_openai_api_key'
MONGO_URI = 'tu_mongodb_connection_string'
```

### 2. Dependencias

Instala las dependencias:
```bash
pip install -r requirements.txt
```

## Uso

### 1. Iniciar el Servidor

```bash
python app.py
```

El servidor se ejecutará en `http://localhost:5000`

### 2. Enviar Video para Procesamiento

```bash
curl -X POST -F "file=@tu_video.mp4" http://localhost:5000/upload
```

O usando el script de prueba:
```bash
python test_integration.py
```

### 3. Verificar Estado del Proyecto

```bash
curl http://localhost:5000/project/{project_id}
```

### 4. Listar Todos los Proyectos

```bash
curl http://localhost:5000/projects
```

## Respuesta del API

El endpoint `/upload` retorna:

```json
{
  "project_id": "60f7b1234567890123456789",
  "status": "completed",
  "drive_folder_link": "https://drive.google.com/drive/folders/xyz",
  "drive_folder_id": "xyz123",
  "uploaded_files": [...],
  "description_files": [...],
  "total_files_processed": 15,
  "total_description_files": 12,
  "video_segments_created": 3,
  "descriptions_processed": 3,
  "descriptions_failed": 0
}
```

## Archivos de Descripciones Generados

Para cada segmento se generan:

- **keyframes/**: Imágenes clave extraídas del video
- **audiodescriptions.json**: Descripciones detalladas de cada keyframe
- **prosody_analysis.json**: Análisis de prosodia y sugerencias de narración
- **video_summary.json**: Resumen general del contenido del segmento

## Resolución de Problemas

### Error de Permisos de Google Drive
- Verifica que las credenciales de Google estén correctas
- Asegúrate de que el refresh token sea válido

### Error de OpenAI API
- Verifica que la API key de OpenAI sea válida
- Revisa los límites de uso de tu cuenta

### Error de MongoDB
- Verifica la conexión a MongoDB
- Asegúrate de que la base de datos esté accesible

### Problemas con FFmpeg
- Instala FFmpeg en tu sistema
- En Windows: `winget install FFmpeg`
- En Ubuntu: `sudo apt install ffmpeg`
- En macOS: `brew install ffmpeg`

## Logs y Debugging

El sistema imprime logs detallados durante el procesamiento. Revisa la consola donde ejecutas `app.py` para información de debugging.

## Limitaciones

- Los videos muy largos pueden tomar mucho tiempo en procesarse
- Se requiere conexión a internet para OpenAI y Google Drive
- El procesamiento de descripciones depende de los límites de la API de OpenAI

## Soporte

Para problemas o preguntas, revisa los logs del sistema y verifica:
1. Conexiones de red
2. Credenciales de APIs
3. Dependencias instaladas
4. Espacio en disco disponible
