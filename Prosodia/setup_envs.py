"""Isolated Python 3.11 environments for Colab/Linux/Windows. Requires uv on PATH."""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

PACKAGES = {
    'clip': ['torch==2.5.1', 'torchvision==0.20.1', 'transformers==4.44.2', 'numpy==1.26.4', 'Pillow>=10,<12', 'opencv-python-headless==4.10.0.84'],
    'xtts': ['torch==2.5.1', 'torchaudio==2.5.1', 'coqui-tts==0.27.2', 'transformers==4.55.4', 'numpy==1.26.4'],
    'spanish_f5': ['f5-tts==1.1.10', 'datasets==3.3.2', 'transformers==4.44.2', 'torch==2.5.1', 'torchaudio==2.5.1', 'numpy==1.26.4'],
    'chatterbox': ['chatterbox-tts==0.1.7'],
    'qwen3': ['qwen-tts==0.1.1'],
}


def setup(engines, target):
    uv = shutil.which('uv')
    if not uv:
        raise RuntimeError('Instala uv: python -m pip install uv')
    settings = {}
    target = Path(target).resolve()
    if (target/'env.json').exists():
        settings.update(json.loads((target/'env.json').read_text(encoding='utf-8')))
    for engine in engines:
        env = target/engine
        if not (env/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')).exists():
            subprocess.run([uv, 'venv', '--python', '3.11', str(env)], check=True)
        py = env/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        lock = Path(__file__).parent/'config'/(engine+'.linux-py311.lock.txt')
        specs = ['-r', str(lock)] if os.name != 'nt' and lock.exists() else PACKAGES[engine]
        subprocess.run([uv, 'pip', 'install', '--python', str(py), *specs], check=True)
        subprocess.run([uv, 'pip', 'check', '--python', str(py)], check=True)
        smoke = {'clip': 'from transformers import CLIPModel, CLIPProcessor; import cv2',
                 'xtts': 'from TTS.api import TTS', 'spanish_f5': 'from f5_tts.api import F5TTS',
                 'chatterbox': 'from chatterbox.mtl_tts import ChatterboxMultilingualTTS',
                 'qwen3': 'from qwen_tts import Qwen3TTSModel'}[engine]
        subprocess.run([str(py), '-c', smoke], check=True)
        frozen = subprocess.check_output([uv, 'pip', 'freeze', '--python', str(py)], text=True)
        (target/(engine+'.freeze.txt')).write_text(frozen, encoding='utf-8')
        settings['EMOTIVE_'+engine.upper()+'_PYTHON'] = str(py)
    (target/'env.json').write_text(json.dumps(settings, indent=2), encoding='utf-8')
    return settings


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--engines', nargs='+', choices=list(PACKAGES), default=['xtts', 'spanish_f5'])
    p.add_argument('--target', default='.engines')
    a = p.parse_args()
    print(json.dumps(setup(a.engines, a.target), indent=2))
