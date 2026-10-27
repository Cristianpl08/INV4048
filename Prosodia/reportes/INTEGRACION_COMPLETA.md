# Integración desde video nuevo — V01

## Qué se corrigió

La entrega previa empezaba en los JSON del corpus. El notebook principal ahora cubre
la primera parte de `EmotivaAD (1).ipynb` y la síntesis/mezcla de
`Integracion_final_(1).ipynb` en una sola ejecución. Los originales permanecen intactos.

El original diarizaba con pyannote.ai y analizaba imágenes con GPT-4o. Se conserva esa
opción y se añade diarización OpenAI. No se confunden los hablantes detectados en el
video con las voces Andrea, Sergio y Sebastian usadas para audiodescribir.

## Una carpeta y un contrato

| Etapa | Entrada | Salida usada por la siguiente etapa |
|---|---|---|
| Carga | Video subido o ruta de Drive | `source/video.*`, `source.json`, `project_source.json` |
| Extracción | Video canónico | `source/audio.wav`, mono 16 kHz para API |
| Diarización | WAV y proveedor seleccionado | `diarization.json`, respuesta API, `speakers/index.json` y WAV por turno |
| Escenas y huecos | Unión de turnos de habla y escenas | `scenes.json`, `candidates.json`, `Main_video.json` |
| CLIP | Video y tiempos absolutos seleccionados | `segments/sNNN/keyframes/keyframes.json` e imágenes |
| GPT: descripción | Fotogramas ordenados | `segments/sNNN/audiodescriptions.json` |
| GPT: prosodia | Imágenes y descripciones | `segments/sNNN/prosody_analysis.json` |
| GPT: resumen | Descripciones, prosodia y tiempo disponible | `segments/sNNN/video_summary.json` con `main_summary` |
| Revisión | Resumen, emoción y tiempos de todos los segmentos | `projects.json`, entrada canónica de ambos motores |
| TTS | JSON revisado + WAV emocional del locutor | `results/<motor>/<locutor>/raw/sNNN.wav` y procedencia |
| Mezcla | Video ORIGINAL, tiempos ABSOLUTOS y WAV | `final/video_ad.mp4`, `mix.wav`, `ad_timed.wav`, `timeline.json` |
| Evaluación | Manifiesto de WAV raw y referencias | `evaluacion_raw/` con CSV y figuras |

La raíz es `proyectos/<nombre>`. Los JSON globales de intercambio se actualizan desde
el proyecto revisado al renderizar. Los JSON dentro de cada segmento conservan las
respuestas GPT originales, para distinguir el borrador de los cambios humanos.

## Reparaciones y diferencias explícitas

- Se eliminó la búsqueda ambigua por nombres e IDs de carpetas Drive, las copias
  manuales entre notebooks y los nombres de video escritos a mano. Drive se monta
  una vez y las rutas se propagan explícitamente.
- La unión de intervalos de habla se calcula antes de buscar huecos: los hablantes
  superpuestos o anidados no producen silencios falsos. Si no hay habla, el video
  queda disponible; antes se devolvía una lista vacía.
- No se unen huecos atravesando hasta dos segundos de diálogo como podía hacer el
  original. Se aplica un margen configurable alrededor del habla.
- PySceneDetect conserva el umbral de contenido 27. Los intervalos se limitan por
  escena y duración; los fragmentos demasiado cortos se descartan de forma explícita.
- Se conserva CLIP ViT-B/32, muestreo cada 30 cuadros y ranking por suma de similitudes
  para elegir hasta 15 fotogramas. Se ejecuta en un proceso aislado con lotes pequeños.
  Se evita la división por cero en escenas idénticas. Los umbrales de diversidad y
  similitud que el original imprimía sin aplicar no se presentan como controles activos.
  La implementación usa los pesos equivalentes `openai/clip-vit-base-patch32` mediante
  Transformers. Los tiempos se guardan tanto absolutos como relativos al segmento.
- Las tres etapas GPT conservan su función, pero ahora exigen salida estructurada;
  no se interpreta Markdown como si fuera JSON. Los prompts se han formalizado y
  deben documentarse al repetir el experimento; no se afirma reproducción bit a bit.
- GPT-4o se fija en `gpt-4o-2024-08-06` de forma configurable. La diarización OpenAI
  utiliza un modelo distinto, `gpt-4o-transcribe-diarize`, con `diarized_json` y
  `chunking_strategy=auto`. Un fallo API no se reemplaza por una descripción inventada.
- Los análisis API se reutilizan solo con entradas y archivos de salida verificados.
  pyannote conserva el identificador del trabajo para no reenviarlo al reanudar.
- Los TTS comparten texto, emoción, referencia y contrato de salida. La síntesis no
  borra la puntuación. Las mezclas no truncan palabras: un exceso de duración requiere
  acortar el texto o revisar el intervalo. Los WAV originales no se alteran.
- Los videos sin audio no se envían a diarización; se procesan como ausencia de habla.
  La versión limita cada proyecto a 10 minutos, 100 intervalos y audio API <24 MB.

## Reanudar

Repite la celda de la etapa fallida. `run_status.json` identifica la etapa. Si una
mezcla indica `needs_edit`, edita `projects.json` en el widget y repite guardar/render.
No repitas análisis después de editar manualmente el texto: eso vuelve a componer
el borrador GPT. Tras reiniciar Colab, monta Drive, configura secretos, selecciona el
mismo proyecto, recupera el JSON en el editor e instala los entornos necesarios.

## Validación y límites

La prueba de integración usa un video con audio real, simula solamente las APIs y la
síntesis, y verifica ambas salidas de seis segundos y el inicio de voz en su tiempo
absoluto. Se prueban hablantes anidados, ausencia de habla, escenas, caché y ranking
CLIP con imágenes idénticas. Esto prueba la conexión de archivos y tiempos, no la
calidad perceptual ni las credenciales de los servicios externos.

No se han ejecutado llamadas facturadas ni una sesión remota Colab con tus claves.
Tampoco se ha generado aquí una tanda científica nueva de ambos motores. Para el
paper, guarda los proyectos revisados y las versiones de los modelos junto a los
resultados; no uses la reparación como evidencia de una mejora perceptual.

## Fuentes de los contratos API

- [OpenAI: transcripción y diarización](https://developers.openai.com/api/docs/guides/speech-to-text)
- [SDK oficial pyannote.ai](https://github.com/pyannote/pyannoteAI-python-sdk)
- [OpenAI CLIP ViT-B/32](https://huggingface.co/openai/clip-vit-base-patch32)
