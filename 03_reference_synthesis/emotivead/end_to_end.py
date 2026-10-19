"""Video -> diarization -> scene gaps -> GPT JSON -> shared TTS -> timed mix.

Every stage uses explicit paths and input fingerprints, never a Drive name search.
"""
import base64
import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path

from .contracts import EMOTIONS, digest, emotion, read_json, validate_segments, write_json
from .media import extract_audio, ffmpeg, probe, run


def cached(path, inputs, work):
    path = Path(path)
    signature = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    stamp = path.with_suffix('.cache.json')
    if path.exists() and stamp.exists():
        old = read_json(stamp)
        if old.get('signature') == signature and old.get('sha256') == digest(path):
            return read_json(path)
    value = work()
    write_json(path, value)
    write_json(stamp, {'signature': signature, 'sha256': digest(path), 'inputs': inputs})
    return value


def validate_speech(segments, duration):
    result = []
    for item in segments:
        start, end = float(item['start']), float(item['end'])
        if not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= duration + .1:
            raise ValueError('La diarización contiene tiempos inválidos; no se crearán huecos con ella.')
        result.append({**item, 'start': start, 'end': min(end, duration),
                       'speaker': str(item.get('speaker', 'unknown'))})
    return sorted(result, key=lambda s: s['start'])


def gaps(speech, duration, minimum=2., margin=.2, maximum=15., cuts=()):
    """Complement of union of speech: nested/overlapping speakers never create false gaps."""
    if not 0 < minimum <= maximum or margin < 0:
        raise ValueError('Duraciones de segmento o margen inválidos.')
    union = []
    for s in validate_speech(speech, duration):
        a, b = max(0, s['start']-margin), min(duration, s['end']+margin)
        if union and a <= union[-1][1]:
            union[-1][1] = max(union[-1][1], b)
        else:
            union.append([a, b])
    free, cursor = [], 0.
    for a, b in union + [[duration, duration]]:
        if a > cursor:
            free.append((cursor, a))
        cursor = max(cursor, b)
    output = []
    for a, b in free:
        boundaries = [a] + sorted(set(float(t) for t in cuts if a < t < b)) + [b]
        for left, right in zip(boundaries, boundaries[1:]):
            count = max(1, math.ceil((right-left)/maximum))
            step = (right-left)/count
            if step < minimum:
                continue
            for i in range(count):
                output.append({'id': f's{len(output)+1:03d}', 'start': left+i*step,
                               'end': left+(i+1)*step})
    if len(output) > 100:
        raise ValueError('Más de 100 segmentos: divide el video o aumenta la duración mínima.')
    return output


def diarize(audio, provider, output):
    if provider == 'openai':
        from openai import OpenAI
        if Path(audio).stat().st_size >= 24_000_000:
            raise ValueError('Audio demasiado grande para OpenAI; divide el video en proyectos menores.')
        with open(audio, 'rb') as f:
            result = OpenAI(timeout=600, max_retries=2).audio.transcriptions.create(
                model='gpt-4o-transcribe-diarize', file=f,
                response_format='diarized_json', chunking_strategy='auto')
        raw = result.model_dump()
        write_json(output/'diarization_api.json', raw)
        if 'segments' not in raw:
            raise ValueError('OpenAI no devolvió segmentos de diarización.')
        return raw['segments']
    if provider != 'pyannote':
        raise ValueError('Proveedor de diarización desconocido.')
    from pyannoteai.sdk import Client
    token = os.environ.get('PYANNOTE_API_KEY')
    if not token:
        raise ValueError('Falta PYANNOTE_API_KEY en los secretos de Colab.')
    client = Client(token)
    job_file = output/'pyannote_job.json'
    fingerprint = digest(audio)
    previous = read_json(job_file) if job_file.exists() else {}
    if previous.get('audio_sha256') == fingerprint:
        job_id = previous['job_id']
    else:
        job_id = client.diarize(client.upload(str(audio)))
        write_json(job_file, {'job_id': job_id, 'audio_sha256': fingerprint})
    deadline = time.monotonic()+3600
    while time.monotonic() < deadline:
        result = client.retrieve(job_id)
        if result['status'] == 'succeeded':
            write_json(output/'diarization_api.json', result)
            return result['output']['diarization']
        if result['status'] in ('failed', 'canceled', 'cancelled'):
            raise RuntimeError('pyannote falló. Revisa el trabajo guardado en pyannote_job.json.')
        time.sleep(5)
    raise TimeoutError('pyannote continúa pendiente; reejecuta para consultar el mismo trabajo.')


def prepare(video, output, provider='pyannote', minimum=2., margin=.2, maximum=15.):
    video, output = Path(video).resolve(), Path(output).resolve()
    info = probe(video)
    if not info['has_video'] or not 0 < info['duration'] <= 600:
        raise ValueError('Usa un video de hasta 10 minutos por proyecto.')
    output.mkdir(parents=True, exist_ok=True)
    identity = {'video_sha256': digest(video), 'provider': provider, 'version': 1}
    if (output/'source.json').exists() and read_json(output/'source.json') != identity:
        raise ValueError('Esta carpeta pertenece a otro video/proveedor. Usa un nombre de proyecto nuevo.')
    write_json(output/'source.json', identity)
    target = output/'source'/('video'+video.suffix.lower())
    target.parent.mkdir(exist_ok=True)
    if target != video and (not target.exists() or digest(target) != identity['video_sha256']):
        shutil.copy2(video, target)
    audio = output/'source'/'audio.wav'
    if not audio.exists():
        run([ffmpeg(), '-y', '-v', 'error', '-i', target, '-vn', '-ar', 16000,
             '-ac', 1, '-c:a', 'pcm_s16le', audio]) if info['has_audio'] else extract_audio(
                 target, audio, info['duration'], False, 16000)
    speech = cached(output/'diarization.json', identity,
                    lambda: validate_speech(diarize(audio, provider, output), info['duration']) if info['has_audio'] else [])
    speech = validate_speech(speech, info['duration'])
    from scenedetect import detect, ContentDetector
    scenes = cached(output/'scenes.json', {**identity, 'threshold': 27}, lambda: [
        {'start': a.get_seconds(), 'end': b.get_seconds()}
        for a, b in detect(str(target), ContentDetector(threshold=27))])
    candidates = gaps(speech, info['duration'], minimum, margin, maximum,
                      [s['start'] for s in scenes])
    write_json(output/'candidates.json', candidates)
    write_json(output/'Main_video.json', candidates)
    write_json(output/'project_source.json', {'video': str(target), 'video_id': output.name,
               'duration': info['duration'], 'diarization_provider': provider})
    # Speaker clips are indexed by neutral IDs, not arbitrary API labels in filenames.
    speakers = output/'speakers'; speakers.mkdir(exist_ok=True)
    index = []
    for i, s in enumerate(speech):
        path = speakers/f'turn_{i+1:04d}.wav'
        if not path.exists():
            run([ffmpeg(), '-y', '-v', 'error', '-ss', s['start'], '-i', audio,
                 '-t', s['end']-s['start'], path])
        index.append({**s, 'path': str(path)})
    write_json(speakers/'index.json', index)
    return candidates


def object_schema(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def chat(prompt, schema, images=()):
    from openai import OpenAI
    content = [{'type': 'text', 'text': prompt}] + [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,'+
            base64.b64encode(Path(p).read_bytes()).decode()}} for p in images]
    response = OpenAI(timeout=180, max_retries=2).chat.completions.create(
        model=os.environ.get('OPENAI_MODEL', 'gpt-4o-2024-08-06'), temperature=0,
        messages=[{'role': 'user', 'content': content}], max_tokens=1800,
        response_format={'type': 'json_schema', 'json_schema': {'name': 'emotivead', 'strict': True, 'schema': schema}})
    choice = response.choices[0]
    if choice.finish_reason != 'stop' or choice.message.refusal:
        raise ValueError('GPT rechazó la solicitud o devolvió una respuesta incompleta.')
    return json.loads(choice.message.content)


def analyze(output):
    output = Path(output).resolve()
    source = read_json(output/'project_source.json')
    selected = read_json(output/'candidates.json')
    if not selected:
        write_json(output/'projects.json', [])
        raise ValueError('No hay huecos suficientes sin diálogo. Revisa candidates.json; no se superpondrá narración automáticamente.')
    checked = validate_segments([{**s, 'text': 'pendiente', 'emotion': 'Serenidad'} for s in selected], source['duration'])
    speech = validate_speech(read_json(output/'diarization.json'), source['duration'])
    if any(s['start'] < t['end'] and s['end'] > t['start'] for s in checked for t in speech):
        raise ValueError('Un intervalo seleccionado invade diálogo. Corrige candidates.json antes de llamar a GPT.')
    frame_map = select_keyframes(source, checked, output)
    project_segments = []
    for s in checked:
        folder = output/'segments'/s['id']; folder.mkdir(parents=True, exist_ok=True)
        fingerprint = {'source': read_json(output/'source.json'), 'start': s['start'], 'end': s['end'],
                       'model': os.environ.get('OPENAI_MODEL', 'gpt-4o-2024-08-06'), 'prompt_version': 1}
        images = frame_map[s['id']]
        fingerprint['keyframes'] = [digest(p) for p in images]
        clip = folder/'video.mp4'
        run([ffmpeg(), '-y', '-v', 'error', '-ss', s['start'], '-i', source['video'],
             '-t', s['end']-s['start'], '-c:v', 'libx264', '-c:a', 'aac', clip])
        descriptions = cached(folder/'audiodescriptions.json', fingerprint, lambda: chat(
            'Redacta en español una descripción factual por cada fotograma en orden. '
            'No inventes nombres, diálogos ni intenciones. No incluyas comentarios sobre esta tarea.',
            object_schema({'descriptions': {'type': 'array', 'items': {'type': 'string'}}}), images))
        prosody = cached(folder/'prosody_analysis.json', {**fingerprint, 'descriptions': descriptions}, lambda: chat(
            'Propón la prosodia de una audiodescripción accesible en español para estas escenas. '
            'La emoción complementaria indica cómo narrar, no diagnostica a las personas. '
            'Devuelve intensidad, tono, duración, ritmo y justificación. Escenas: '+json.dumps(descriptions, ensure_ascii=False),
            object_schema({**{k: {'type': 'string'} for k in ['main_emotion', 'intensity', 'tone', 'duration', 'rhythm', 'rationale']},
                           'complementary_emotion': {'type': 'string', 'enum': EMOTIONS}}), images))
        budget = max(2, int((s['end']-s['start'])*1.8))
        summary = cached(folder/'video_summary.json', {**fingerprint, 'descriptions': descriptions, 'prosody': prosody}, lambda: chat(
            f'Redacta UNA audiodescripción natural en español de máximo {budget} palabras para '
            f"{s['end']-s['start']:.2f} segundos. Texto listo para locución, sin Markdown ni etiquetas. "
            'Prioriza la acción visible esencial y no inventes información. Descripciones: '+json.dumps(descriptions, ensure_ascii=False)+
            '\nProsodia sugerida: '+json.dumps(prosody, ensure_ascii=False), object_schema({'main_summary': {'type': 'string'}})))
        project_segments.append({**s, 'text': summary['main_summary'], 'emotion': emotion(prosody['complementary_emotion']),
                                 'prosody': prosody, 'analysis': prosody})
    project = {'schema_version': 1, **source, 'segments': validate_segments(project_segments, source['duration']),
               'source': 'end_to_end_apis', 'review_status': 'draft'}
    write_json(output/'projects.json', [project])
    sync_exports(output, [project])
    return project


def select_keyframes(source, segments, output):
    from .pipeline import interpreter
    request = {'video': source['video'], 'segments': segments, 'output': str(output/'segments')}
    signature = {'video_sha256': digest(source['video']), 'segments': segments, 'version': 1}
    stamp = output/'keyframes_cache.json'
    valid = False
    if stamp.exists():
        old = read_json(stamp)
        valid = old.get('inputs') == signature and all(
            Path(p).exists() and digest(p) == h for p, h in old.get('files', {}).items()) and bool(old.get('files'))
    if not valid:
        write_json(output/'keyframes_request.json', request)
        with (output/'keyframes.log').open('w', encoding='utf-8') as log:
            result = subprocess.run([interpreter('clip'), str(Path(__file__).with_name('keyframes_worker.py')),
                                     str(output/'keyframes_request.json')], stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        if result.returncode: raise RuntimeError('CLIP falló: consulta keyframes.log.')
    mapping, hashes = {}, {}
    for seg in segments:
        folder = output/'segments'/seg['id']/'keyframes'
        index = folder/'keyframes.json'
        mapping[seg['id']] = [folder/item['filename'] for item in read_json(index)]
        if not mapping[seg['id']]: raise ValueError('CLIP no devolvió fotogramas.')
        for p in [index, *mapping[seg['id']]]: hashes[str(p)] = digest(p)
    write_json(stamp, {'inputs': signature, 'files': hashes})
    return mapping


def sync_exports(output, projects):
    """Regenerate interchange JSON from the canonical, possibly human-edited project."""
    if len(projects) != 1:
        raise ValueError('El flujo de carga utiliza un video por proyecto.')
    project = projects[0]
    source = read_json(Path(output)/'project_source.json')
    if Path(project['video']).resolve() != Path(source['video']).resolve() or project['video_id'] != source['video_id']:
        raise ValueError('Edita segmentos, texto y emociones; conserva video y video_id del proyecto original.')
    project['duration'] = source['duration']
    project['segments'] = validate_segments(project['segments'], probe(project['video'])['duration'])
    output = Path(output)
    write_json(output/'Main_video.json', [{k: s[k] for k in ('id', 'start', 'end')} for s in project['segments']])
    write_json(output/'audiodescriptions.json', project['segments'])
    write_json(output/'video_summary.json', {'main_summary': ' '.join(s['text'] for s in project['segments']),
               'segments': [{'id': s['id'], 'main_summary': s['text']} for s in project['segments']]})
    write_json(output/'prosody_analysis.json', {'segments': [
        {**s.get('prosody', {}), 'id': s['id'], 'start': s['start'], 'end': s['end'],
         'complementary_emotion': s['emotion']} for s in project['segments']]})
    return projects
