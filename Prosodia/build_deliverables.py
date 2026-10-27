"""Rebuild notebook wrappers and sanitized historical copies without running originals."""
import hashlib
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def cell(text, kind='code'):
    value = {'cell_type':kind,'metadata':{},'source':text.strip().splitlines(keepends=True),
             'id':hashlib.sha256(text.encode()).hexdigest()[:12]}
    if kind=='code':value.update(execution_count=None,outputs=[])
    return value


def notebook(path, cells):
    value = {'nbformat':4,'nbformat_minor':5,'metadata':{
        'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
        'language_info':{'name':'python'}, 'colab':{'provenance':[]}},'cells':cells}
    path.write_text(json.dumps(value,ensure_ascii=False,indent=1),encoding='utf-8')


def main():
    inventory=[]
    originals=HERE/'originales_sanitizados'
    originals.mkdir(exist_ok=True)
    for source in ROOT.glob('*.ipynb'):
        data=json.loads(source.read_text(encoding='utf-8'))
        changes=0
        for c in data['cells']:
            text=''.join(c['source'])
            pattern=r'(?im)^(\s*)([A-Z_]*(?:API_KEY|API_TOKEN|CLIENT_ID|CLIENT_SECRET|REFRESH_TOKEN)[A-Z_]*)\s*=\s*([\'\"]).*?\3[^\n]*$'
            text,n=re.subn(pattern,lambda m:f'{m[1]}{m[2]} = os.environ.get("{m[2]}", "")  # credencial externa',text)
            changes+=n
            for pattern in [r'sk-proj-[A-Za-z0-9_-]+',r'sk_[A-Za-z0-9_-]{12,}',r'sk-[A-Za-z0-9_-]{20,}',
                            r'GOCSPX-[A-Za-z0-9_-]+',r'1//[A-Za-z0-9_-]+',r'\d+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com']:
                text,n=re.subn(pattern,'REDACTED_USE_ENV',text);changes+=n
            c['source']=text.splitlines(keepends=True)
            c['metadata']={}
            if c['cell_type']=='code':c['outputs']=[];c['execution_count']=None
        data['cells'].insert(0,cell('Copia histórica sanitizada. No ejecutar para el flujo nuevo: usa EmotiveAD_Colab.ipynb.\nSe eliminaron credenciales y salidas; el código histórico conserva sus incompatibilidades.','markdown'))
        data['cells'].insert(1,cell('import os'))
        data['metadata']={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}}
        (originals/source.name).write_text(json.dumps(data,ensure_ascii=False,indent=1),encoding='utf-8')
        inventory.append({'file':source.name,'sha256_original':hashlib.sha256(source.read_bytes()).hexdigest(),
                          'cells_original':len(data['cells'])-2,'redactions':changes})
    (HERE/'reportes'/'notebook_inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    # A self-contained V01 dataset, preserving originals outside V01 untouched.
    for name in ['Locutores','Prueba 2 VDMS (XTTS)','videos prueba mp4']:
        shutil.copytree(ROOT/name,HERE/'datos'/name,dirs_exist_ok=True)
    for name in ['sn-article (6).tex','Universal_Access_Prosodic_Springer.pdf']:
        shutil.copy2(ROOT/name,originals/name)

    setup = '''
from google.colab import drive
drive.mount('/content/drive')
from pathlib import Path
import os, sys, subprocess, json, shutil
# Sube la carpeta V01 Original completa a Drive; edita SOLO esta ruta.
V01 = Path('/content/drive/MyDrive/EmotiveAD/V01 Original') # @param {type:"string"}
DATA = V01 / 'datos'
OUT = V01 / 'outputs'
assert (V01/'emotivead').is_dir(), 'No se encuentra V01 Original; corrige V01.'
assert (DATA/'Locutores').is_dir(), 'Faltan los datos. Sube V01 Original/datos completo.'
subprocess.run([sys.executable,'-m','pip','install','uv'],check=True)
UV = shutil.which('uv')
subprocess.run([UV,'venv','--python','3.11','/content/emotive-core'],check=True)
PY = '/content/emotive-core/bin/python'
subprocess.run([UV,'pip','install','--python',PY,'-r',str(V01/'requirements.txt')],check=True)
subprocess.run([UV,'pip','check','--python',PY],check=True)
os.environ['PYTHONPATH'] = str(V01)
print('Entorno aislado listo; no se sustituyó NumPy ni CUDA del kernel de Colab.')
'''
    notebook(HERE/'Reproducir_Corpus_Colab.ipynb',[
        cell('''# EmotiveAD · V01 estable para Colab
Ejecuta de arriba abajo con GPU (Entorno de ejecución → Cambiar tipo → GPU).
Entrada: `datos/Locutores`, `datos/videos prueba mp4` y JSON existentes en `datos/Prueba 2 VDMS (XTTS)/1. Input`.
No se llaman APIs pagadas para reutilizar tus JSON. El pipeline histórico de creación de JSON queda archivado;
para nuevas descripciones automáticas usa V02 (Qwen local).

**Opciones:** 1 XTTS, 2 Spanish-F5, 3 ambos (60 audios para 10 videos × 3 locutores).
Se usan los mismos textos y referencias para cada motor. Los pesos se descargan en la primera ejecución.
Este notebook se validó estructuralmente; la inferencia GPU debe verificarse en tu sesión de Colab.
''','markdown'),cell(setup),
        cell('''
# @title Configuración experimental
OPTION = 3 # @param [1,2,3] {type:"raw"}
NARRATORS = ['Andrea','Sergio','Sebastian']
MIX = True # @param {type:"boolean"}
ENGINES = {1:['xtts'],2:['spanish_f5'],3:['xtts','spanish_f5']}[OPTION]
# XTTS usa CPML. Lee https://huggingface.co/coqui/XTTS-v2/blob/main/LICENSE.txt
ACCEPT_XTTS_LICENSE = False # @param {type:"boolean"}
if 'xtts' in ENGINES and not ACCEPT_XTTS_LICENSE:
    raise ValueError('Para XTTS, lee la licencia y marca ACCEPT_XTTS_LICENSE si la aceptas; o elige otro motor.')
if ACCEPT_XTTS_LICENSE: os.environ['COQUI_TOS_AGREED']='1'
subprocess.run([PY,str(V01/'setup_envs.py'),'--engines',*ENGINES,'--target','/content/emotive-engines'],check=True)
ENV = '/content/emotive-engines/env.json'
'''),
        cell('''
# Validación de entradas sin sintetizar: revisar projects.json antes de continuar.
subprocess.run([PY,str(V01/'run_pipeline.py'),'--root',str(DATA),'--output',str(OUT),
                '--option',str(OPTION),'--prepare-only'],check=True)
projects=json.loads((OUT/'projects.json').read_text())
for p in projects:
    s=p['segments'][0]
    print(p['video_id'], round(p['duration'],2), s['emotion'], s['text'])
'''),
        cell('''
# Síntesis y mezcla. Puede tardar; cada motor se descarga y carga de forma secuencial.
cmd=[PY,str(V01/'run_pipeline.py'),'--root',str(DATA),'--output',str(OUT),
     '--option',str(OPTION),'--env',ENV,'--narrators',*NARRATORS]
if MIX: cmd.append('--mix')
subprocess.run(cmd,check=True)
print('Revisa mix_report.json por video: needs_edit indica que una voz no cabe.')
'''),
        cell('''
# Evaluación sobre WAV RAW, antes de atempo, ducking o normalización de escucha.
REPORT = OUT/'evaluacion_raw'
subprocess.run([PY,str(V01/'evaluate.py'),'--root',str(DATA),'--manifest',str(OUT/'audio_manifest.json'),
                '--stage','raw','--output',str(REPORT)],check=True)
from IPython.display import display, Image
display(Image(filename=str(REPORT/'01_dispersion_referencia.png')))
display(Image(filename=str(REPORT/'03_distribuciones.png')))
'''),
        cell('''
# Empaquetar únicamente resultados nuevos (no las voces de referencia ni credenciales).
from google.colab import files
archive=shutil.make_archive('/content/EmotiveAD_resultados','zip',OUT)
files.download(archive)
'''),cell('''## Comprobación final
Escucha las tres voces, verifica el texto y revisa `failures.json`, `mix_report.json` y `extraction_errors.json`.
Los audios y manifiestos permanecen en Drive si se desconecta Colab. Reejecutar comprueba hashes antes de reutilizar síntesis.
Spanish-F5 puede transcribir la referencia localmente si no hay `.txt` junto al WAV. Para reproducibilidad,
añade su transcripción exacta y revisada; no uses como referencia el texto que quieres generar.

La transferencia emocional no está garantizada por la etiqueta de emoción. El condicionamiento usa
la grabación emocional del locutor; confirma el resultado con escucha y evaluación perceptual.
''','markdown')])
    notebook(HERE/'Graficas_Paper_Colab.ipynb',[
        cell('# Evaluación acústica y figuras para el paper\nRecalcula eGeMAPSv02 sobre los WAV entregados, sin confundir las dos etapas XTTS con dos modelos.','markdown'),
        cell(setup),cell('''
REPORT=V01/'reportes'/'acustica_recalculada'
subprocess.run([PY,str(V01/'evaluate.py'),'--root',str(DATA),'--output',str(REPORT)],check=True)
from IPython.display import display, Image
for p in sorted(REPORT.glob('*.png')): display(Image(filename=str(p)))
print((REPORT/'INTERPRETACION.md').read_text())
'''),cell('''
from google.colab import files
files.download(shutil.make_archive('/content/EmotiveAD_figuras','zip',REPORT))
''')])
    from build_complete_notebook import main as build_complete
    build_complete()
    from build_existing_ad_notebook import main as build_existing
    build_existing()
    print('Carpetas de datos, copias sanitizadas y dos notebooks preparados.')


if __name__=='__main__':main()
