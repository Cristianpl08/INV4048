from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path
from .contracts import digest, read_json, reference_for, validate_segments, write_json
from .media import compose, probe

ENGINES = {1: ['xtts'], 2: ['spanish_f5'], 3: ['xtts', 'spanish_f5'], 4: ['chatterbox']}


def interpreter(engine):
    name = 'EMOTIVE_' + engine.upper() + '_PYTHON'
    value = os.environ.get(name)
    if not value or not Path(value).is_file():
        raise RuntimeError(f'Falta el entorno de {engine}. Ejecuta setup_envs.py o define {name}.')
    return value


def synthesize(project, narrators, engines, references, output, seed=42, progress=lambda s: None):
    from . import __version__
    info = probe(project['video'])
    segments = validate_segments(project['segments'], info['duration'])
    if not narrators or not engines:
        raise ValueError('Selecciona al menos un locutor y un motor.')
    if any(e not in {'xtts', 'spanish_f5', 'chatterbox'} for e in engines):
        raise ValueError('Motor no admitido.')
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    write_json(root/'project.json', project)
    records = []
    for engine in engines:
        jobs = []
        for narrator in narrators:
            if narrator not in {'Woman01', 'Man01', 'Man02'}:
                raise ValueError('Locutor no reconocido.')
            for seg in segments:
                ref = reference_for(references, narrator, seg['emotion'])
                out = root/engine/narrator/'raw'/(seg['id']+'.wav')
                transcript = ref.with_suffix('.txt')
                job = {'text': seg['text'], 'reference': str(ref),
                       'reference_text': transcript.read_text(encoding='utf-8').strip() if transcript.exists() else '',
                       'reference_sha256': digest(ref), 'output': str(out),
                       'emotion': seg['emotion'], 'segment_id': seg['id'], 'narrator': narrator,
                       'video_id': project['video_id'], 'engine': engine, 'seed': seed, 'pipeline_version': __version__}
                # Resume only a verified exact-input match, never just an existing filename.
                cached = out.with_suffix('.provenance.json')
                valid = False
                if out.exists() and cached.exists():
                    old = read_json(cached)
                    valid = old.get('job') == job and old.get('audio_sha256') == digest(out)
                if not valid:
                    jobs.append(job)
                records.append({**job, 'path': str(out), 'stage': 'raw'})
        if jobs:
            progress(f'Generando {len(jobs)} audios con {engine}…')
            request = root/f'request_{engine}.json'
            write_json(request, {'engine': engine, 'seed': seed, 'jobs': jobs})
            # A whole model batch in one process; GPU memory is released between engines.
            log = root/f'{engine}.log'
            with log.open('w', encoding='utf-8') as handle:
                result = subprocess.run([interpreter(engine), str(Path(__file__).with_name('tts_worker.py')), str(request)],
                                        stdout=handle, stderr=subprocess.STDOUT, timeout=14400)
            if result.returncode:
                raise RuntimeError(f'Falló {engine}. Consulta {log.name}; no se marca como generación válida.')
            for job in jobs:
                out = Path(job['output'])
                provenance = read_json(out.with_suffix('.provenance.json'))
                provenance['audio_sha256'] = digest(out)
                write_json(out.with_suffix('.provenance.json'), provenance)
    write_json(root/'audio_manifest.json', records)
    return records


def mix_project(project, records, output, duck_db=-14, max_speed=1.25, progress=lambda s: None):
    results, failures = [], []
    for engine, narrator in sorted({(r['engine'], r['narrator']) for r in records}):
        selected = {r['segment_id']: r['path'] for r in records if (r['engine'], r['narrator']) == (engine, narrator)}
        progress(f'Mezclando {engine} · {narrator}…')
        try:
            paths = compose(project['video'], project['segments'],
                            [selected[s['id']] for s in sorted(project['segments'], key=lambda s: s['start'])],
                            Path(output)/engine/narrator/'final', duck_db, max_speed)
            results.append({'engine': engine, 'narrator': narrator, **paths})
        except ValueError as exc:
            failures.append({'engine': engine, 'narrator': narrator, 'error': str(exc)})
    report = {'completed': results, 'needs_edit': failures}
    write_json(Path(output)/'mix_report.json', report)
    return report
