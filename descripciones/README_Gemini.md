# Descripciones con Gemini

Este código ha sido modificado para usar Google Gemini en lugar de OpenAI para generar descripciones, análisis de prosodia y resúmenes de videos.

## Cambios Principales

### 1. Importaciones
- Reemplazado `import openai` por `import google.generativeai as genai`

### 2. Configuración de API
- Cambiado de `openai.api_key = api_key` a `genai.configure(api_key=api_key)`
- Uso del modelo `gemini-1.5-flash` para todas las operaciones

### 3. Funciones Modificadas

#### `generate_audiodescriptions()`
- Cambiado de `openai.chat.completions.create()` a `model.generate_content()`
- Modificado el formato de entrada de imágenes para Gemini
- Ajustado el manejo de tokens y respuestas

#### `summarize_audiodescriptions()`
- Cambiado de `openai.chat.completions.create()` a `model.generate_content()`
- Ajustado el formato de prompt para Gemini
- Modificado el manejo de respuestas y tokens

#### `analyze_prosody()`
- Cambiado de `openai.chat.completions.create()` a `model.generate_content()`
- Ajustado el formato de prompt para Gemini
- Modificado el manejo de respuestas y tokens

### 4. Dependencias
- Agregado `google-generativeai` a requirements.txt
- Removido `openai` de las dependencias

## Instalación

1. Instalar las dependencias:
```bash
pip install -r requirements.txt
```

2. Obtener una API key de Google Gemini:
   - Ve a [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Crea una nueva API key
   - Reemplaza `"TU_API_KEY_DE_GEMINI_AQUI"` en el código con tu API key real

## Uso

El uso del código permanece igual que antes:

```python
# Procesar todos los videos
python DescripcionesGemini.py process_all

# Reprocesar solo el resumen de un video específico
python DescripcionesGemini.py reprocess_summary <nombre_del_video>

# Verificar y reprocesar resúmenes inválidos
python DescripcionesGemini.py check_summaries
```

## Notas Importantes

1. **API Key**: Asegúrate de reemplazar `"TU_API_KEY_DE_GEMINI_AQUI"` con tu API key real de Gemini.

2. **Modelo**: Se usa `gemini-1.5-flash` que es el modelo más reciente y eficiente de Gemini.

3. **Formato de Imágenes**: Gemini maneja las imágenes de manera diferente a OpenAI, por lo que se ajustó el formato de entrada.

4. **Tokens**: El conteo de tokens puede variar ligeramente entre OpenAI y Gemini.

5. **Funcionalidad**: Todas las funcionalidades originales se mantienen intactas, solo cambia el proveedor de IA.

## Diferencias con OpenAI

- **Velocidad**: Gemini puede ser más rápido en algunas operaciones
- **Costo**: Los precios pueden variar entre proveedores
- **Calidad**: La calidad de las descripciones puede variar ligeramente
- **Límites**: Los límites de tokens y requests pueden ser diferentes

## Solución de Problemas

Si encuentras errores relacionados con la API de Gemini:
1. Verifica que tu API key sea válida
2. Asegúrate de tener suficiente cuota disponible
3. Revisa los logs de error para más detalles 