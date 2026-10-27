# Validación de la entrega — 6 octubre 2026

## Comprobado

- Dos notebooks nuevos válidos según nbformat; sus celdas Python compilan.
- Cinco pruebas de núcleo: entradas inválidas, referencias Unicode, sincronización y
  ducking medidos con audio real, rechazo de desbordamiento y video sin audio.
- Cuatro pruebas web: carga/edición y JSON, errores de carga/rutas, fallo asíncrono
  visible, generación de mezcla/previsualización y ZIP completo/segmentos/ambos.
  La última usa FFmpeg real y sustituye el TTS por un tono conocido; no mide calidad de voz.
- Interfaz verificada en navegador con video del corpus, recuperación del proyecto,
  selección de segmento, descripción/emoción, voces Qwen y cambio a locutores.
- 108 WAV del material recibido analizados con openSMILE: 48 referencias,
  30 salidas XTTS y 30 archivos finales XTTS. Figuras en `acustica/`.
- Dependencias XTTS y Spanish-F5 resueltas para Linux/Python 3.11; archivos lock en config.
- Spanish-F5 instalado localmente: importación F5TTS correcta y CUDA disponible.
  Se corrigieron incompatibilidades fijando Transformers 4.44.2 y datasets 3.3.2.

## Pendiente de ejecución científica

No se ejecutaron los pesos de Spanish-F5 ni una nueva tanda de 60 síntesis.
La importación correcta no demuestra calidad ni equivalencia perceptual. El notebook
opción 3 ejecuta ambos motores sobre los mismos textos, referencias y semillas,
conserva WAV raw y registra versiones; luego calcula figuras comparables.

No se ejecutó la sesión remota de Google Colab. Los modelos Chatterbox/Qwen3 y el
servidor Voicebox necesitan instalarse/descargarse para probar su inferencia real.
El conector Voicebox se implementó conforme a la API oficial, sin un servidor activo
contra el cual comprobar síntesis de extremo a extremo. La visión Ollama y la opción
GPT-4o tampoco se ejecutaron; no se usaron credenciales antiguas.

El manuscrito no está listo para afirmar diferencias entre dos motores hasta generar,
escuchar y evaluar ambas tandas. La auditoría identifica las afirmaciones afectadas.
No se fabricaron resultados ni se etiquetaron los audios XTTS finales como Spanish-F5.

## Actualización: notebook principal de inicio a fin

`EmotiveAD_Colab.ipynb` reemplaza la entrada limitada a JSON históricos. El flujo anterior
queda en `Reproducir_Corpus_Colab.ipynb`. Hay 11 pruebas V01 aprobadas tras el cambio:
las cinco originales y seis nuevas sobre unión de habla, escenas sin habla, caché,
ranking CLIP estable, contrato de diarización OpenAI y conexión de video a dos mezclas.

El nuevo recorrido se probó con medios reales y dobles de prueba para APIs/modelos.
Las dependencias API y CLIP también se resolvieron para Linux/Python 3.11 y se fijaron
en archivos lock. No se ejecutó inferencia CLIP real ni llamadas de pago. Los tres
notebooks se validaron estructuralmente y se compiló el código de sus celdas.
Consulta INTEGRACION_COMPLETA.md para los cambios respecto al código recibido.
