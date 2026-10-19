from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path


def ffmpeg():
    exe = os.environ.get('FFMPEG_BIN') or shutil.which('ffmpeg')
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args, timeout=900):
    result = subprocess.run([str(a) for a in args], capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace')[-5000:])
    return result


def probe(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    exe = os.environ.get('FFPROBE_BIN') or shutil.which('ffprobe')
    if exe:
        data = json.loads(run([exe, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path]).stdout)
        return {'duration': float(data['format']['duration']),
                'has_audio': any(s['codec_type'] == 'audio' for s in data['streams']),
                'has_video': any(s['codec_type'] == 'video' for s in data['streams'])}
    result = subprocess.run([ffmpeg(), '-hide_banner', '-i', str(path)], capture_output=True)
    text = result.stderr.decode('utf-8', errors='replace')
    match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', text)
    if not match:
        raise ValueError('No se pudo leer la duración del archivo multimedia.')
    h, m, s = map(float, match.groups())
    return {'duration': h * 3600 + m * 60 + s, 'has_audio': 'Audio:' in text, 'has_video': 'Video:' in text}


def extract_audio(video, output, duration, has_audio=True, sr=24000):
    if has_audio:
        args = ['-i', video, '-vn']
    else:
        args = ['-f', 'lavfi', '-i', f'anullsrc=r={sr}:cl=stereo']
    run([ffmpeg(), '-y', '-v', 'error', *args, '-t', duration, '-ar', sr, '-ac', 2, '-c:a', 'pcm_s16le', output])


def frames(video, start, end, folder, count=4):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(count):
        t = start + (end - start) * (i + .5) / count
        p = folder / f'frame_{i:02d}.jpg'
        run([ffmpeg(), '-y', '-v', 'error', '-ss', t, '-i', video, '-frames:v', 1,
             '-vf', 'scale=768:-2', p])
        if not p.exists():
            raise RuntimeError(f'No se pudo extraer el fotograma en {t:.2f} s.')
        paths.append(p)
    return paths


def silence_candidates(video, minimum=.8, threshold=-35):
    info = probe(video)
    if not info['has_audio']:
        return [{'start': 0.0, 'end': info['duration']}]
    result = run([ffmpeg(), '-hide_banner', '-i', video, '-vn', '-af',
                  f'silencedetect=noise={threshold}dB:d={minimum}', '-f', 'null', '-'])
    text = result.stderr.decode('utf-8', errors='replace')
    found, start = [], None
    for match in re.finditer(r'silence_(start|end):\s*([\d.]+)', text):
        kind, t = match.group(1), float(match.group(2))
        if kind == 'start':
            start = t
        elif start is not None:
            found.append({'start': start, 'end': min(t, info['duration'])})
            start = None
    if start is not None:
        found.append({'start': start, 'end': info['duration']})
    return found


def compose(video, segments, audio_paths, out_dir, duck_db=-14, max_speed=1.25, sr=24000):
    """Keep raw synthesis intact; fit only playback copies. Refuse truncation."""
    import numpy as np
    import soundfile as sf
    from .contracts import validate_segments
    if not math.isfinite(duck_db) or not -40 <= duck_db <= 0:
        raise ValueError('Ducking debe estar entre -40 y 0 dB.')
    if not math.isfinite(max_speed) or not 1 <= max_speed <= 2:
        raise ValueError('Velocidad máxima debe estar entre 1 y 2.')
    info = probe(video)
    segments = validate_segments(segments, info['duration'])
    if len(segments) != len(audio_paths):
        raise ValueError('Falta audio para uno o más segmentos.')
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base_path = out / 'original.wav'
    extract_audio(video, base_path, info['duration'], info['has_audio'], sr)
    base, _ = sf.read(base_path, always_2d=True)
    n = round(info['duration'] * sr)
    base = np.pad(base[:n], ((0, max(0, n-len(base))), (0, 0)))
    narration = np.zeros((n, 2))
    gain = np.ones(n)
    timeline = []
    for seg, raw in zip(segments, audio_paths):
        raw_info = sf.info(raw)
        window = seg['end'] - seg['start']
        speed = max(1.0, raw_info.duration / window)
        if speed > max_speed + .001:
            raise ValueError(f"{seg['id']}: voz de {raw_info.duration:.2f}s para {window:.2f}s. Acorta el texto o amplía el intervalo; no se recorta la voz.")
        fitted = out / (seg['id'] + '_fitted.wav')
        run([ffmpeg(), '-y', '-v', 'error', '-i', raw, '-af', f'atempo={speed:.8f}',
             '-ar', sr, '-ac', 2, fitted])
        a, _ = sf.read(fitted, always_2d=True)
        allowed = round(window * sr)
        # ffmpeg's time stretching can overshoot by a small analysis window.
        if len(a) > allowed:
            speed *= len(a) / allowed * 1.005
            if speed > max_speed + .001:
                raise ValueError(f"{seg['id']}: el ajuste temporal supera la velocidad máxima.")
            run([ffmpeg(), '-y', '-v', 'error', '-i', raw, '-af', f'atempo={speed:.8f}', '-ar', sr, '-ac', 2, fitted])
            a, _ = sf.read(fitted, always_2d=True)
        begin, end = round(seg['start'] * sr), round(seg['start'] * sr) + len(a)
        if len(a) > allowed or end > n:
            raise ValueError('La voz sigue excediendo el intervalo; revisa el texto.')
        narration[begin:end] += a
        level = 10 ** (duck_db / 20)
        gain[begin:end] = np.minimum(gain[begin:end], level)
        attack, release = min(begin, round(.08*sr)), min(n-end, round(.2*sr))
        if attack:
            gain[begin-attack:begin] = np.minimum(gain[begin-attack:begin], np.linspace(1, level, attack))
        if release:
            gain[end:end+release] = np.minimum(gain[end:end+release], np.linspace(level, 1, release))
        timeline.append({**seg, 'raw_duration': raw_info.duration, 'speed': speed,
                         'actual_end': end/sr, 'raw_file': Path(raw).name})
    mix = base * gain[:, None] + narration
    peak = float(np.abs(mix).max(initial=0))
    scale = min(1.0, .98 / peak) if peak else 1.0
    sf.write(out/'ad_timed.wav', narration * min(1., .98/max(.98, float(np.abs(narration).max()))), sr)
    sf.write(out/'mix.wav', mix * scale, sr)
    run([ffmpeg(), '-y', '-v', 'error', '-i', video, '-i', out/'mix.wav',
         '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
         '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-t', info['duration'],
         '-movflags', '+faststart', out/'video_ad.mp4'])
    from .contracts import write_json
    write_json(out/'timeline.json', {'segments': timeline, 'duck_db': duck_db,
               'mix_peak_gain': scale, 'sample_rate': sr, 'duration': info['duration']})
    return {'video': str(out/'video_ad.mp4'), 'mix': str(out/'mix.wav'), 'ad': str(out/'ad_timed.wav')}
