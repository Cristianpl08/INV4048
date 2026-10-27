"""Dedicated Colab entry point: existing AD -> XTTS + Spanish-F5 -> figures."""
from pathlib import Path
from build_deliverables import cell, notebook


def main():
    notebook(Path(__file__).parent/'AD_Existente_XTTS_SpanishF5_Colab.ipynb', [
        cell('''# AD existentes · XTTS + Spanish-F5 + gráficas

Este notebook utiliza las AD de `datos/Prueba 2 VDMS (XTTS)/1. Input`.
**No vuelve a diarizar, analizar imágenes ni llamar a APIs. No necesita claves.**
Lee `main_summary` y `complementary_emotion`, verifica los videos y referencias,
permite revisar el texto, genera ambos motores y calcula los gráficos comparativos.

**10 videos × 3 locutores × 2 motores = 60 audios nuevos y 30 pares.**
Los audios XTTS históricos no se mezclan con la nueva comparación. Se comparan WAV raw,
antes de ajustes de velocidad o ducking. La mezcla de video es opcional.

Sube la carpeta **V01 Original** a `Mi unidad/EmotiveAD/V01 Original` en Drive:
incluye `emotivead`, `config`, los scripts `.py`, los JSON de entrada,
`datos/Locutores` y `datos/videos prueba mp4`. No subas `.engines`, entornos virtuales
ni credenciales. Activa GPU en Colab y ejecuta las celdas en orden.
''','markdown'), cell('''
# @title 1. Drive, rutas e instalación del núcleo
from google.colab import drive, files
drive.mount('/content/drive')
from pathlib import Path
import os, sys, json, subprocess, shutil
V01 = Path('/content/drive/MyDrive/EmotiveAD/V01 Original') # @param {type:"string"}
DATA = V01/'datos'
INPUT = DATA/'Prueba 2 VDMS (XTTS)'/'1. Input'
VIDEOS = DATA/'videos prueba mp4'
REFS = DATA/'Locutores'
OUT = V01/'resultados_AD_existentes'
for path in [V01/'prepare_existing_ad.py', V01/'run_pipeline.py', INPUT, VIDEOS, REFS]:
    assert path.exists(), f'No se encuentra {path}. Sube la carpeta completa o corrige V01.'
subprocess.run(['apt-get','-qq','update'],check=True)
subprocess.run(['apt-get','-qq','install','-y','ffmpeg'],check=True)
subprocess.run([sys.executable,'-m','pip','install','uv','ipywidgets'],check=True)
UV = shutil.which('uv'); PY = '/content/emotive-core/bin/python'
if not Path(PY).exists(): subprocess.run([UV,'venv','--python','3.11','/content/emotive-core'],check=True)
subprocess.run([UV,'pip','install','--python',PY,'-r',str(V01/'requirements.txt')],check=True)
os.environ['PYTHONPATH'] = str(V01)
print('Entradas:',INPUT,'\\nResultados:',OUT)
'''), cell('''
# @title 2. Validar las AD existentes y las voces de referencia
NARRATORS = ['Andrea','Sergio','Sebastian']
subprocess.run([PY,str(V01/'prepare_existing_ad.py'),'--input',str(INPUT),'--videos',str(VIDEOS),
    '--references',str(REFS),'--output',str(OUT),'--narrators',*NARRATORS],check=True)
audit = json.loads((OUT/'text_preparation_audit.json').read_text())
for row in audit:
    print(row['video_id'], '|',row['emotion'],'|',round(row['duration_s'],2),'s')
    print(row['narration'])
    if row['changed']: print('  Se retiraron marcas o notas de análisis; original conservado en el registro.')
print('AD:',len(audit),'| Audios esperados:',len(audit)*len(NARRATORS)*2)
'''), cell('''
# @title 3. Revisar las AD (recupera tu revisión si ya existe)
import ipywidgets as widgets
from IPython.display import display, Audio, Video, Image
REVIEWED = OUT/'projects_reviewed.json'
draft = REVIEWED if REVIEWED.exists() else OUT/'projects_draft.json'
editor = widgets.Textarea(value=draft.read_text(encoding='utf-8'),
    layout=widgets.Layout(width='100%',height='450px'))
display(editor)
print('Puedes corregir text y emotion. Ambos motores utilizarán exactamente esta misma revisión.')
'''), cell('''
# @title 4. Guardar y validar la revisión antes de instalar los motores
PROJECTS = json.loads(editor.value)
expected_ids = {p['video_id'] for p in json.loads((OUT/'projects_draft.json').read_text())}
assert len(PROJECTS)==len(expected_ids) and {p['video_id'] for p in PROJECTS}==expected_ids, 'Conserva los videos de entrada y sus identificadores.'
REVIEWED.write_text(json.dumps(PROJECTS,ensure_ascii=False,indent=2),encoding='utf-8')
check = """
import sys
from pathlib import Path
from emotivead.contracts import read_json, validate_segments, reference_for
from emotivead.media import probe
projects=read_json(sys.argv[1]); original={p['video_id']:p for p in read_json(sys.argv[3])}
for p in projects:
    assert p['video']==original[p['video_id']]['video'], 'Conserva la ruta del video.'
    p['segments']=validate_segments(p['segments'],probe(p['video'])['duration'])
    for s in p['segments']:
        for narrator in sys.argv[4:]: reference_for(Path(sys.argv[2]),narrator,s['emotion'])
print('Textos, emociones, tiempos, videos y referencias validados.')
"""
subprocess.run([PY,'-c',check,str(REVIEWED),str(REFS),str(OUT/'projects_draft.json'),*NARRATORS],check=True)
EXPECTED = sum(len(p['segments']) for p in PROJECTS)*len(NARRATORS)*2
print('Se generarán',EXPECTED,'audios raw.')
'''), cell('''
# @title 5. Instalar XTTS y Spanish-F5 en entornos independientes
# Lee la licencia: https://huggingface.co/coqui/XTTS-v2/blob/main/LICENSE.txt
ACCEPT_XTTS_LICENSE = False # @param {type:"boolean"}
if not ACCEPT_XTTS_LICENSE: raise ValueError('Lee la licencia CPML de XTTS y marca la casilla si aceptas sus condiciones.')
os.environ['COQUI_TOS_AGREED']='1'
subprocess.run([PY,str(V01/'setup_envs.py'),'--engines','xtts','spanish_f5',
    '--target','/content/emotive-engines'],check=True)
ENV = '/content/emotive-engines/env.json'
envs = json.loads(Path(ENV).read_text())
for engine in ['xtts','spanish_f5']:
    subprocess.run([envs['EMOTIVE_'+engine.upper()+'_PYTHON'],'-c',
        'import torch; assert torch.cuda.is_available(), "Activa GPU en Colab"; print(torch.cuda.get_device_name())'],check=True)
'''), cell('''
# @title 6. Generar las AD con los dos motores
GENERATE_MIXED_VIDEO = False # @param {type:"boolean"}
cmd=[PY,str(V01/'run_pipeline.py'),'--root',str(DATA),'--output',str(OUT),
    '--projects',str(REVIEWED),'--option','3','--env',ENV,'--narrators',*NARRATORS]
if GENERATE_MIXED_VIDEO: cmd.append('--mix')
subprocess.run(cmd,check=True)
records=json.loads((OUT/'audio_manifest.json').read_text())
assert len(records)==EXPECTED, 'Faltan audios. Revisa failures.json y los logs antes de evaluar.'
for engine in ['xtts','spanish_f5']:
    print(engine,sum(r['engine']==engine for r in records),'audios')
print('Si Colab se interrumpe, monta Drive, recupera la revisión, instala entornos y repite esta celda. Se comprueban hashes antes de reutilizar WAV.')
'''), cell('''
# @title 7. Escuchar un video en los dos motores y los tres locutores
VIDEO_ID = PROJECTS[0]['video_id'] # Cambia por el identificador que quieras comparar.
for record in records:
    if record['video_id']==VIDEO_ID:
        print(record['engine'],record['narrator'],record['emotion'])
        display(Audio(filename=record['path']))
if GENERATE_MIXED_VIDEO:
    report=json.loads((OUT/VIDEO_ID/'mix_report.json').read_text())
    for item in report['completed']:
        print(item['engine'],item['narrator']); display(Video(filename=item['video'],embed=True,width=640))
    for item in report['needs_edit']: print('La voz no cabe en el clip:',item)
'''), cell('''
# @title 8. Calcular medidas acústicas y gráficas comparativas
REPORT = OUT/'graficas_comparacion_raw'
subprocess.run([PY,str(V01/'evaluate.py'),'--root',str(DATA),'--manifest',str(OUT/'audio_manifest.json'),
    '--stage','raw','--output',str(REPORT)],check=True)
errors=json.loads((REPORT/'extraction_errors.json').read_text())
assert not errors, f'Falló la extracción de {len(errors)} audios: revisa extraction_errors.json.'
comparison=json.loads((REPORT/'model_comparison_status.json').read_text())
assert comparison['status']=='available' and comparison['n_pairs']==EXPECTED//2 and comparison['unmatched']==0, comparison
print('Pares comparados:',comparison['n_pairs'])
for figure in sorted(REPORT.glob('*.png')): display(Image(filename=str(figure)))
print((REPORT/'INTERPRETACION.md').read_text())
'''), cell('''
# @title 9. Descargar resultados, tablas y figuras
archive=shutil.make_archive('/content/AD_XTTS_SpanishF5_resultados','zip',OUT)
files.download(archive)
print('Resultados conservados en Drive:',OUT)
'''), cell('''
## Qué se obtiene

- WAV originales por video, motor y locutor, con registro de texto, referencia y versiones.
- Dispersión referencia/síntesis y tono/sonoridad; distribuciones con puntos individuales;
  correlaciones; perfiles emocionales y comparación emparejada XTTS–Spanish-F5.
- PNG, SVG y PDF; medidas eGeMAPS, tablas descriptivas y error con bootstrap por video.
- `text_preparation_audit.json`: texto original y texto preparado. No se modifican tus JSON fuente.

La comparación acústica no equivale a una evaluación perceptual de emoción o accesibilidad.
Los 10 videos son la unidad de muestreo; los tres locutores no son 30 videos independientes.
Los resúmenes largos pueden exceder el clip: esto no impide analizar el WAV raw; la mezcla
opcional avisa en lugar de cortar palabras. F5 transcribe localmente la referencia si
no existe un `.txt` homónimo; una transcripción exacta revisada mejora reproducibilidad.

La estructura y la preparación de las 10 entradas se validaron localmente. La generación
GPU real y la sesión de Colab deben ejecutarse para obtener resultados de ambos modelos.
''','markdown')])


if __name__ == '__main__': main()
