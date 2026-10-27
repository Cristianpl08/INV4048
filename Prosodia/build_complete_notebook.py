"""Generate the default complete Colab workflow; no secrets or embedded outputs."""
from pathlib import Path
from build_deliverables import cell, notebook


def main():
    here = Path(__file__).resolve().parent
    notebook(here/'EmotiveAD_Colab.ipynb', [cell('''
# EmotiveAD V01 · Del video al video audiodescrito

Flujo completo: **subir video → extraer audio → diarización API → huecos sin habla y
escenas → fotogramas → GPT-4o: descripciones, prosodia y resumen → JSON revisables →
XTTS / Spanish-F5 / ambos → sincronización y ducking → previsualización y descarga**.

Conserva la combinación original pyannote.ai + GPT-4o; también puedes elegir diarización
OpenAI. Cada proveedor recibe el audio o los fotogramas necesarios y factura su API.
Guarda las claves en Secretos de Colab, nunca en el notebook. Las voces se generan en
la GPU de Colab. Sube **V01 Original** a Drive y activa GPU antes de empezar.

Los proyectos nuevos no necesitan ningún JSON del experimento anterior. Una carpeta
de proyecto contiene todas las rutas y estados; reejecutar reutiliza respuestas API
solo si coinciden sus entradas. Los cambios metodológicos respecto al original están
documentados en `reportes/INTEGRACION_COMPLETA.md`.
''', 'markdown'), cell('''
# @title 1. Montar Drive e instalar el entorno aislado
from google.colab import drive, files, userdata
drive.mount('/content/drive')
from pathlib import Path
import os, sys, subprocess, shutil, json, re
V01 = Path('/content/drive/MyDrive/EmotiveAD/V01 Original') # @param {type:"string"}
assert (V01/'run_complete.py').is_file(), 'Sube V01 Original completo y corrige V01.'
subprocess.run(['apt-get','-qq','update'], check=True)
subprocess.run(['apt-get','-qq','install','-y','ffmpeg'], check=True)
subprocess.run([sys.executable,'-m','pip','install','uv','ipywidgets'], check=True)
UV = shutil.which('uv')
PY = '/content/emotive-api/bin/python'
if not Path(PY).exists(): subprocess.run([UV,'venv','--python','3.11','/content/emotive-api'], check=True)
subprocess.run([UV,'pip','install','--python',PY,'-r',str(V01/'config'/'api.linux-py311.lock.txt')], check=True)
subprocess.run([UV,'pip','check','--python',PY], check=True)
os.environ['PYTHONPATH'] = str(V01)
def execute(*args):
    subprocess.run([PY,str(V01/'run_complete.py'),*map(str,args)], check=True)
'''), cell('''
# @title 2. Proyecto, proveedores y secretos
PROJECT_NAME = 'mi_video_01' # @param {type:"string"}
DIARIZATION = 'pyannote' # @param ['pyannote','openai']
OPTION = 3 # @param [1,2,3] {type:"raw"}
NARRATORS = ['Andrea','Sergio','Sebastian']
OPENAI_MODEL = 'gpt-4o-2024-08-06' # @param {type:"string"}
MIN_SECONDS = 2.0 # @param {type:"number"}
MAX_SECONDS = 15.0 # @param {type:"number"}
SPEECH_MARGIN = 0.2 # @param {type:"number"}
assert re.fullmatch(r'[A-Za-z0-9_-]{1,60}',PROJECT_NAME), 'Nombre: letras sin acentos, números, guion o guion bajo.'
OUT = V01/'proyectos'/PROJECT_NAME
OUT.mkdir(parents=True, exist_ok=True)
REFS = V01/'datos'/'Locutores'
assert REFS.is_dir(), 'Falta datos/Locutores con las referencias emocionales.'
os.environ['OPENAI_API_KEY'] = userdata.get('OPENAI_API_KEY')
os.environ['OPENAI_MODEL'] = OPENAI_MODEL
if DIARIZATION == 'pyannote': os.environ['PYANNOTE_API_KEY'] = userdata.get('PYANNOTE_API_KEY')
print('Proyecto:', OUT, '| Diarización:', DIARIZATION, '| Motor TTS:', OPTION)
'''), cell('''
# @title 3. Subir un video o indicar su ruta en Drive
VIDEO_IN_DRIVE = '' # @param {type:"string"}
if VIDEO_IN_DRIVE:
    VIDEO = Path(VIDEO_IN_DRIVE)
elif (OUT/'project_source.json').exists():
    VIDEO = Path(json.loads((OUT/'project_source.json').read_text())['video'])
    print('Se reutiliza el video de este proyecto. Usa otro PROJECT_NAME para otro video.')
else:
    uploaded = files.upload()
    assert len(uploaded)==1, 'Sube exactamente un video por proyecto.'
    name, content = next(iter(uploaded.items()))
    incoming = OUT/'upload'; incoming.mkdir(exist_ok=True)
    VIDEO = incoming/Path(name).name
    VIDEO.write_bytes(content)
assert VIDEO.is_file(), 'No se encuentra el video.'
print('Video de entrada:', VIDEO)
'''), cell('''
# @title 4. Diarización API, escenas, recortes por hablante e intervalos
execute('prepare','--video',VIDEO,'--output',OUT,'--diarization',DIARIZATION,
        '--minimum',MIN_SECONDS,'--maximum',MAX_SECONDS,'--margin',SPEECH_MARGIN)
from IPython.display import display, Video, HTML
display(Video(filename=str(VIDEO), embed=True, width=640))
CANDIDATES = json.loads((OUT/'candidates.json').read_text())
print(json.dumps(CANDIDATES,ensure_ascii=False,indent=2))
if not CANDIDATES: print('No hay huecos suficientes: revisa el video y los parámetros antes de continuar.')
'''), cell('''
# @title 5. Revisar intervalos (puedes editar CANDIDATES antes de ejecutar)
# Tiempos ABSOLUTOS respecto al video original. No deben invadir el habla detectada.
# Para descartar un intervalo: CANDIDATES = [s for s in CANDIDATES if s['id'] != 's002']
assert CANDIDATES, 'No hay intervalos seleccionados.'
(OUT/'candidates.json').write_text(json.dumps(CANDIDATES,ensure_ascii=False,indent=2),encoding='utf-8')
subprocess.run([PY,str(V01/'setup_envs.py'),'--engines','clip','--target','/content/emotive-engines'],check=True)
ENV = '/content/emotive-engines/env.json'
execute('analyze','--output',OUT,'--env',ENV)
PROJECTS = json.loads((OUT/'projects.json').read_text())
for s in PROJECTS[0]['segments']:
    print(s['id'],s['start'],s['end'],s['emotion'],'→',s['text'])
'''), cell('''
# @title 6. Revisar texto, emoción y tiempos en un editor JSON
import ipywidgets as widgets
PROJECTS = json.loads((OUT/'projects.json').read_text())
EDITOR = widgets.Textarea(value=json.dumps(PROJECTS,ensure_ascii=False,indent=2),
    layout=widgets.Layout(width='100%',height='450px'))
display(EDITOR)
print('Edita aquí lo necesario. La siguiente celda guarda y valida este JSON antes de sintetizar.')
'''), cell('''
# @title 7. Guardar revisión e instalar XTTS / Spanish-F5
PROJECTS = json.loads(EDITOR.value)
assert len(PROJECTS)==1 and PROJECTS[0]['segments'], 'Conserva un proyecto con segmentos.'
(OUT/'projects.json').write_text(json.dumps(PROJECTS,ensure_ascii=False,indent=2),encoding='utf-8')
ENGINES = {1:['xtts'],2:['spanish_f5'],3:['xtts','spanish_f5']}[OPTION]
# Lee https://huggingface.co/coqui/XTTS-v2/blob/main/LICENSE.txt
ACCEPT_XTTS_LICENSE = False # @param {type:"boolean"}
if 'xtts' in ENGINES and not ACCEPT_XTTS_LICENSE:
    raise ValueError('Lee CPML y marca ACCEPT_XTTS_LICENSE si la aceptas, o usa la opción 2.')
if ACCEPT_XTTS_LICENSE: os.environ['COQUI_TOS_AGREED']='1'
subprocess.run([PY,str(V01/'setup_envs.py'),'--engines',*ENGINES,'--target','/content/emotive-engines'],check=True)
ENV = '/content/emotive-engines/env.json'
'''), cell('''
# @title 8. Generar las voces y mezclar en el video original
DUCK_DB = -14 # @param {type:"number"}
MAX_SPEED = 1.25 # @param {type:"number"}
execute('render','--output',OUT,'--references',REFS,'--env',ENV,'--option',OPTION,
        '--narrators',*NARRATORS,'--duck-db',DUCK_DB,'--max-speed',MAX_SPEED)
report = json.loads((OUT/'mix_report.json').read_text())
for item in report['completed']:
    print(item['engine'],item['narrator'])
    display(Video(filename=item['video'],embed=True,width=640))
for item in report['needs_edit']: print('REQUIERE AJUSTE:',item)
# Si no cabe: acorta texto en el editor, ejecuta la celda 7 y esta celda.
# No vuelvas a ejecutar analyze: regeneraría el borrador desde los análisis API.
'''), cell('''
# @title 9. Evaluación acústica y gráficos de las salidas reales
REPORT = OUT/'evaluacion_raw'
subprocess.run([PY,str(V01/'evaluate.py'),'--root',str(V01/'datos'),
    '--manifest',str(OUT/'audio_manifest.json'),'--stage','raw','--output',str(REPORT)],check=True)
from IPython.display import Image
for image in sorted(REPORT.glob('*.png')): display(Image(filename=str(image)))
'''), cell('''
# @title 10. Descargar el proyecto y sus resultados
INCLUDE_SOURCE_MEDIA = False # @param {type:"boolean"}
import zipfile
archive = Path('/content')/(PROJECT_NAME+'_resultados.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for path in OUT.rglob('*'):
        if not path.is_file(): continue
        rel = path.relative_to(OUT)
        if not INCLUDE_SOURCE_MEDIA and rel.parts[0] in ['source','upload','speakers']: continue
        z.write(path,rel)
files.download(str(archive))
print('El proyecto completo permanece en Drive:',OUT)
'''), cell('''
## Archivos y reanudación

`diarization.json` conserva turnos por hablante; `candidates.json` conserva huecos
absolutos; `segments/sNNN/` contiene video, fotogramas y los tres JSON GPT originales;
`projects.json` es la entrada canónica revisable para ambos TTS. En `results/` se
separan motor, locutor, WAV original, WAV ajustado, voz sincronizada y video con ducking.

Los JSON globales se regeneran desde `projects.json` al renderizar. Si editas una
emoción, ambos motores buscan el WAV correspondiente del mismo locutor. Si un audio
no cabe, se conserva y se marca `needs_edit`; no se corta una palabra para hacerlo caber.
Repite la etapa fallida: los análisis API y WAV con entradas idénticas se reutilizan.

Los turnos de diarización son hablantes del video; Andrea/Sergio/Sebastian son los
locutores de audiodescripción. Son funciones distintas. Las etiquetas emocionales
no demuestran por sí solas que la voz generada transmita esa emoción.

`Reproducir_Corpus_Colab.ipynb` queda disponible únicamente para repetir el experimento
con los JSON históricos. Este notebook es la entrada principal desde video nuevo.
''','markdown')])


if __name__ == '__main__':
    main()
