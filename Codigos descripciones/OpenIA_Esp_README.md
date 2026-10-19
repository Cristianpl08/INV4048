
# OpenIA_Esp.py

Este script implementa una solución de procesamiento de video y generación de resúmenes utilizando la IA OpenIA en español. El flujo principal del código es el siguiente:

## Funcionamiento técnico y flujo

1. **Procesamiento de video**: 
   - Utiliza `cv2`, `Katna` y `scenedetect` para analizar videos
   - Detecta cambios de escena y segmentos relevantes
   - Extrae fotogramas clave que representan momentos significativos

2. **Mecanismos de Atención**:
   - Analiza elementos clave en cada escena: personajes, expresiones, acciones, escenarios
   - Prioriza información relevante para la comprensión narrativa
   - Evita sobrecarga descriptiva manteniendo la pertinencia contextual

3. **Generación de Descripción Semántica**:
   - Construye un relato coherente y contextualizado de cada escena
   - Utiliza la API de OpenAI para generar narrativas detalladas
   - Integra elementos temporales y contextuales para mayor comprensión

4. **Caracterización Emocional**:
   - Identifica la emoción predominante en cada escena
   - Utiliza el modelo de Plutchik con 16 interpretaciones emocionales
   - Asocia cada emoción con parámetros prosódicos específicos

5. **Ajuste de Características Prosódicas**:
   - Adapta elementos como intensidad, entonación y ritmo
   - Ajusta la duración de pausas según el contexto narrativo
   - Genera descripciones emocionalmente congruentes

6. **Validación y Almacenamiento**:
   - Verifica la calidad y coherencia de las descripciones
   - Almacena resultados y metadatos en formato JSON
   - Guarda información prosódica para posterior procesamiento

## Principales módulos y dependencias
- `cv2`, `Katna`, `scenedetect`: Procesamiento y análisis de video.
- `PIL`, `base64`, `numpy`: Manipulación de imágenes y datos.
- `clip`, `torch`: Extracción de características semánticas de imágenes.
- `openai`: Interfaz con la API OpenAI.
- `json`, `os`, `datetime`, `re`: Utilidades generales y manejo de archivos.

## Uso
El script está diseñado para generar audiodescripciones prosódicas enriquecidas a partir de contenido audiovisual, optimizando la accesibilidad y experiencia narrativa para personas con discapacidad visual.

## Requisitos
- Python 3.x
- Dependencias listadas en el código
- Acceso a la API de OpenAI
- Espacio suficiente para almacenamiento de datos intermedios

## Autor
Desarrollado por crist.
