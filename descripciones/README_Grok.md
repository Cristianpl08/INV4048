# Descripciones con Grok

Este código ha sido modificado para usar xAI Grok en lugar de OpenAI para generar descripciones, análisis de prosodia y resúmenes de videos.

## Cambios Principales

### 1. Importaciones
- Reemplazado `import openai` por `from openai import OpenAI` para usar la librería oficial con base URL personalizada

### 2. Configuración de API
- Configuración usando `OpenAI` con `base_url="https://api.x.ai/v1"`
- Uso del modelo `grok-2-vision-latest` para todas las operaciones

### 3. Funciones Modificadas

#### `call_grok_api()`
- Nueva función que configura el cliente OpenAI con la base URL de Grok
- Maneja errores y retorna respuestas en formato compatible

#### `generate_audiodescriptions()`
- Cambiado para usar `call_grok_api()` en lugar de llamadas directas
- Modificado el modelo a `grok-2-vision-latest`
- Mantenido el formato de entrada de imágenes y prompts

#### `summarize_audiodescriptions()`
- Cambiado para usar `call_grok_api()` en lugar de llamadas directas
- Modificado el modelo a `grok-2-vision-latest`
- Mantenido el formato de prompts y manejo de respuestas

#### `analyze_prosody()`
- Cambiado para usar `call_grok_api()` en lugar de llamadas directas
- Modificado el modelo a `grok-2-vision-latest`
- Mantenido el formato de prompts y manejo de respuestas

### 4. Dependencias
- Agregado `openai` a requirements.txt
- Removido `requests` de las dependencias

## Instalación

1. Instalar las dependencias:
```bash
pip install openai torch torchvision opencv-python pillow katna scenedetect clip
```

2. La API key de Grok ya está configurada en el código:
   - API Key: `YOUR_XAI_API_KEY`
   - Base URL: `https://api.x.ai/v1`
   - Modelo: `grok-2-vision-latest`

## Uso

El uso del código permanece igual que antes:

```python
# Procesar todos los videos
python DescripcionesGrok.py process_all

# Reprocesar solo el resumen de un video específico
python DescripcionesGrok.py reprocess_summary <nombre_del_video>

# Verificar y reprocesar resúmenes inválidos
python DescripcionesGrok.py check_summaries
```

## Notas Importantes

1. **API Key**: La API key de Grok ya está configurada en el código.

2. **Implementación**: Se utiliza la librería oficial `openai` con una base URL personalizada para conectarse a la API de Grok.

3. **Compatibilidad**: El código mantiene la misma estructura y funcionalidad que las versiones con OpenAI, Claude y Gemini, solo cambiando la API utilizada.

4. **Modelo**: Se utiliza el modelo `grok-2-vision-latest` que es el modelo principal de Grok con capacidades de visión.

## Funcionalidades Mantenidas

- ✅ Extracción de keyframes con CLIP
- ✅ Generación de audiodescripciones detalladas
- ✅ Análisis de prosodia basado en emociones
- ✅ Generación de resúmenes con límites de caracteres
- ✅ Validación de resúmenes
- ✅ Procesamiento por lotes de videos
- ✅ Reprocesamiento selectivo de resúmenes
- ✅ Verificación y corrección de resúmenes inválidos

## Estructura de Archivos de Salida

```
output/
├── video_name/
│   ├── keyframes/
│   │   ├── keyframe_0.jpg
│   │   ├── keyframe_15.jpg
│   │   └── keyframes.json
│   ├── audiodescriptions.json
│   ├── prosody_analysis.json
│   └── video_summary.json
```

## Diferencias con otras versiones

- **OpenAI**: Usa `openai` y modelo `gpt-4o`
- **Claude**: Usa `anthropic` y modelo `claude-3-5-sonnet-20241022`
- **Gemini**: Usa `google.generativeai` y modelo `gemini-1.5-flash`
- **Grok**: Usa `openai` con base URL personalizada y modelo `grok-2-vision-latest` (este archivo)

## Configuración de la API

El código está configurado para usar:
- **API Key**: `YOUR_XAI_API_KEY`
- **Base URL**: `https://api.x.ai/v1`
- **Modelo**: `grok-2-vision-latest` 