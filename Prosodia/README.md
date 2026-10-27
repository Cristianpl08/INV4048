# V01 Original — Colab y evaluación reproducible

Abre **EmotiveAD_Colab.ipynb** en Google Colab. Sube esta carpeta completa a
`Mi unidad/EmotiveAD/V01 Original` y selecciona una GPU. Ejecuta las celdas en orden.
La primera celda permite cambiar la ruta. No necesitas copiar credenciales antiguas.

## Generar ambos motores a partir de las AD que ya existen

Abre **AD_Existente_XTTS_SpanishF5_Colab.ipynb** para trabajar directamente con
`datos/Prueba 2 VDMS (XTTS)/1. Input`. No requiere diarización, CLIP ni claves API.
Usa también `datos/Locutores` y `datos/videos prueba mp4`.

El notebook valida las 10 AD, separa las notas de análisis del texto de locución,
permite revisarlo, genera XTTS y Spanish-F5 para los tres locutores y calcula las
seis familias de gráficos en PNG/SVG/PDF. Con la selección completa produce 60 WAV
y 30 pares; las gráficas comprueban cobertura antes de declarar éxito. La mezcla
con video es opcional y está desactivada por defecto. Resultados en
`resultados_AD_existentes/`, sin modificar los JSON fuente.

La preparación local del 15 de octubre de 2026 confirmó 10 entradas y retiró notas o
marcas Markdown de 7 textos. El registro está en
`reportes/preparacion_AD_existentes/text_preparation_audit.json`. Se validó la
estructura del notebook y tres pruebas del limpiador. La síntesis real se ejecutará
en Colab; esta preparación no generó ni inventó resultados de los modelos.

## Flujo principal: video nuevo, de inicio a fin

`EmotiveAD_Colab.ipynb` ahora es el notebook completo. Ya no requiere JSON previos:

1. Monta Drive e instala FFmpeg y un Python aislado.
2. Lee `OPENAI_API_KEY` y, con el proveedor original, `PYANNOTE_API_KEY` de Secretos.
3. Permite subir un video o indicar su ruta en Drive.
4. Extrae audio, diariza por API, guarda turnos y recortes de hablantes, detecta escenas
   y propone intervalos sin habla con margen de seguridad.
5. Selecciona fotogramas con CLIP ViT-B/32. GPT-4o genera por separado descripciones,
   análisis prosódico y resumen para locución; guarda los tres JSON por segmento.
6. Muestra un editor de `projects.json` para revisar tiempos, texto y emoción.
7. Instala XTTS, Spanish-F5 o ambos en entornos separados y genera todas las voces.
8. Ajusta la duración dentro del límite elegido, sincroniza, aplica ducking y muestra
   cada video completo por motor/locutor.
9. Calcula gráficos sobre WAV originales y descarga el proyecto con sus resultados.

Selecciona `pyannote` para conservar el proveedor original; `openai` utiliza
`gpt-4o-transcribe-diarize`. En ambos casos descripción y prosodia usan GPT-4o.
Cada API requiere su propia clave y saldo; no son llamadas a la suscripción web de ChatGPT.

La raíz de cada ejecución es `proyectos/PROJECT_NAME`. No hace falta copiar a mano
archivos entre carpetas ni introducir IDs de Drive para cada etapa. Usa otro nombre
para otro video. El núcleo guarda estado y caché para reanudar etapas fallidas.

`Reproducir_Corpus_Colab.ipynb` conserva el flujo de los JSON históricos para el paper.
Consulta `reportes/INTEGRACION_COMPLETA.md` para el mapa de entradas/salidas y cambios.

## Contenido

- `datos/`: copia de los videos, los 48 WAV de referencia, los JSON, los resultados y las versiones históricas recibidas.
- `originales_sanitizados/`: los tres notebooks originales, sin credenciales ni salidas incrustadas, más el artículo. Son archivo histórico; utiliza los notebooks nuevos para ejecutar.
- `EmotiveAD_Colab.ipynb`: carga → diarización → escenas/CLIP → GPT/JSON → síntesis → ducking → evaluación → descarga.
- `Reproducir_Corpus_Colab.ipynb`: repetir únicamente el corpus histórico.
- `Graficas_Paper_Colab.ipynb`: recalcular y exportar figuras del conjunto existente.
- `emotivead/`: implementación compartida con V02.
- `reportes/AUDITORIA.md`: hallazgos, evidencia y límites del paper.
- `reportes/acustica/`: figuras PNG, SVG y PDF ya generadas con los audios reales.

Los archivos que entregaste también permanecen intactos en la carpeta superior.

## Opciones de síntesis

| Opción | Motor | Audios esperados para 10 videos y 3 locutores |
|---|---|---:|
| 1 | XTTS v2 | 30 |
| 2 | Spanish-F5 | 30 |
| 3 | XTTS v2 + Spanish-F5 | 60 |

Spanish-F5 carga explícitamente `jpgallegoar/F5-Spanish`, `model_1200000.safetensors`,
`vocab.txt` y la arquitectura `F5TTS_Base`. No carga por error el modelo general F5 v1.
Las tres voces usan la referencia de la misma emoción y exactamente el mismo texto por video.
No se eliminan los puntos del texto como ocurría antes.

Cada motor tiene su propio Python 3.11. Colab conserva sus paquetes del kernel; no se
fuerzan NumPy antiguo ni versiones manuales de las bibliotecas CUDA de la sesión.
`setup_envs.py` comprueba dependencias e importaciones y guarda las versiones resueltas.
La disponibilidad de GPU, memoria y duración de sesión de Colab depende del servicio.

## Contrato histórico (Reproducir_Corpus_Colab)

La importación lee `main_summary` de `video_summary.json` y `complementary_emotion` de
`prosody_analysis.json`. Se verifica el WAV emocional de cada locutor normalizando
acentos Unicode, mayúsculas, números iniciales y espacios.

En el dataset recibido cada resumen corresponde a **un clip completo**, por lo que
se importa un intervalo `[0, duración del clip]`. Los JSON de fotogramas no se tratan
como segmentos temporales: no tienen los límites de narración necesarios. Para
selecciones temporales nuevas utiliza el notebook principal completo o V02.

```text
outputs/
  projects.json
  audio_manifest.json
  failures.json
  <video_id>/
    project.json
    audio_manifest.json
    <motor>/<locutor>/
      raw/s001.wav
      raw/s001.provenance.json
      final/s001_fitted.wav
      final/ad_timed.wav
      final/mix.wav
      final/video_ad.mp4
      final/timeline.json
    mix_report.json
  evaluacion_raw/
```

La síntesis original se conserva en `raw`. La copia de escucha puede acelerarse hasta
el límite configurado; si no cabe, la mezcla queda en `needs_edit` y conserva la voz
para descarga. No se recorta ni se extiende el intervalo silenciosamente.
El ducking reduce el audio original durante la voz, con entrada/salida gradual.
No requiere Demucs ni elimina el diálogo original por completo.

El manifiesto registra texto, emoción, motor, referencia, hash de referencia, semilla,
duración y versiones de paquetes. La reanudación exige coincidencia del trabajo y del
hash del WAV, no únicamente que exista el nombre del archivo. Guarda los manifiestos,
los archivos `.freeze.txt` y los checkpoints de la ejecución usada en el paper.

Spanish-F5 requiere el texto exacto del audio de referencia. Puedes añadir un `.txt`
con el mismo nombre junto al WAV. Sin `.txt`, el motor utiliza su transcriptor local;
revisa esa transcripción antes de fijar el experimento. La etiqueta emocional no es
un control calibrado de F0, intensidad o duración: estos motores se condicionan con
el audio emocional del locutor.

## Ejecución local alternativa

Desde esta carpeta, con Python 3.11 o 3.12 y FFmpeg disponible (se incluye respaldo mediante imageio-ffmpeg):

```sh
python -m pip install -r requirements.txt uv
python setup_envs.py --engines xtts spanish_f5 --target .engines
python run_pipeline.py --root datos --output outputs --prepare-only --option 3
python run_pipeline.py --root datos --output outputs --option 3 --env .engines/env.json --mix
python evaluate.py --root datos --output reportes/acustica
```

XTTS requiere que el usuario acepte su licencia y configure `COQUI_TOS_AGREED=1`.
El notebook incluye una casilla explícita; no se acepta automáticamente.

Para evaluar **nuevas** generaciones, usa:

```sh
python evaluate.py --root datos --manifest outputs/audio_manifest.json --stage raw --output outputs/evaluacion_raw
```

## Alcance de verificación

Se verificaron en este equipo la importación de 10 videos, 48 referencias, la extracción
acústica de 108 WAV, las figuras, las reglas de intervalos, la mezcla real con FFmpeg,
la API y la interfaz web. Ver `reportes/VALIDACION.md` para el resultado final.
No se ha ejecutado una sesión de Colab ni inferencia GPU nueva con XTTS, Spanish-F5,
Chatterbox o Qwen. Los adaptadores y los notebooks están preparados para esa validación;
no representan 60 nuevas síntesis ya realizadas.

## Fuentes y licencias

Consulta `../V02 Platform/MODELOS_Y_LICENCIAS.md`. El código de un motor, sus pesos
y sus datos de entrenamiento pueden tener licencias distintas. Revoca las credenciales
que estaban incrustadas en tus notebooks originales antes de compartirlos.

## Nuevos JSON y preservación del experimento

El experimento importa los resúmenes originales sin volver a generarlos. Para nuevos
videos, `generate_descriptions.py` admite `--provider openai` (GPT-4o, requiere
OPENAI_API_KEY propia y tiene coste) o `--provider ollama` (Qwen local). Los JSON
resultantes son borradores que deben revisarse; `run_pipeline.py --projects ruta/projects.json`
permite sintetizarlos con los dos motores. Esta extensión no reproduce automáticamente
el experimento semántico de ocho modelos del artículo.

Las figuras existentes corresponden exclusivamente al corpus XTTS recibido. Ejecuta
la opción 3 y evalúa su manifiesto para comparar etapas raw equivalentes. No compares
XTTS ya acelerado con F5 sin ajustar: cambiaría las medidas acústicas.
