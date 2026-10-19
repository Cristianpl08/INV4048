from __future__ import annotations

import hashlib
import json
import math
import re
import time
import unicodedata
from pathlib import Path

EMOTIONS = ['Serenidad', 'Éxtasis', 'Aceptación', 'Admiración', 'Aprensión',
            'Terror', 'Distracción', 'Asombro', 'Pensamiento profundo', 'Duelo',
            'Aburrimiento', 'Aversión', 'Molestia', 'Furia', 'Interés', 'Vigilancia']


def key(text):
    text = unicodedata.normalize('NFKD', str(text))
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in text if not unicodedata.combining(c)).lower())


def emotion(text):
    matches = [e for e in EMOTIONS if key(e) == key(text)]
    if not matches:
        raise ValueError(f'Emoción no reconocida: {text!r}. Selecciona una de las 16 emociones.')
    return matches[0]


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    # Windows readers can briefly hold the destination open during status polling.
    for attempt in range(20):
        try:
            tmp.replace(path)
            break
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.025)


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_segments(segments, duration):
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Duración de video inválida.')
    if not isinstance(segments, list) or not 1 <= len(segments) <= 100:
        raise ValueError('Debes seleccionar entre 1 y 100 segmentos.')
    result, ids, last_end = [], set(), 0.0
    for i, s in enumerate(sorted(segments, key=lambda v: float(v['start']))):
        start, end = float(s['start']), float(s['end'])
        if not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= duration + .001:
            raise ValueError(f'Intervalo fuera del video: {start}–{end}; duración {duration}.')
        if start < last_end - .0001:
            raise ValueError('Los intervalos de audiodescripción no pueden solaparse.')
        sid = str(s.get('id', f's{i+1:03d}'))
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', sid) or sid in ids:
            raise ValueError('Cada segmento requiere un identificador único y seguro.')
        text = str(s.get('text', '')).strip()
        if not text or len(text) > 2000:
            raise ValueError('Cada segmento necesita texto de 1 a 2000 caracteres.')
        result.append({**s, 'id': sid, 'start': start, 'end': end, 'text': text,
                       'emotion': emotion(s.get('emotion', 'Serenidad'))})
        ids.add(sid)
        last_end = end
    return result


def reference_for(root, narrator, target_emotion):
    folder = Path(root) / narrator
    wanted = key(emotion(target_emotion))
    matches = [p for p in folder.glob('*.wav') if key(re.sub(r'^\d+\s*', '', p.stem)) == wanted]
    if len(matches) != 1:
        raise ValueError(f'Se esperaba una referencia para {narrator}/{target_emotion}; hay {len(matches)}.')
    return matches[0].resolve()


def import_legacy(input_dir, video_dir, probe):
    projects = []
    for folder in sorted(Path(input_dir).iterdir()):
        if not folder.is_dir():
            continue
        summary = read_json(folder / 'video_summary.json')
        prosody = read_json(folder / 'prosody_analysis.json')
        video = Path(video_dir) / (folder.name + '.mp4')
        info = probe(video)
        # The supplied summaries refer to whole clips; frame descriptions are not timed AD segments.
        text = summary['main_summary'].strip()
        projects.append({'schema_version': 1, 'video_id': folder.name, 'video': str(video.resolve()),
                         'duration': info['duration'], 'source': 'legacy_json',
                         'segments': validate_segments([{'id': 's001', 'start': 0,
                             'end': info['duration'], 'text': text,
                             'emotion': prosody['complementary_emotion'], 'prosody': prosody}], info['duration'])})
    if not projects:
        raise ValueError('No se encontraron proyectos de entrada.')
    return projects
