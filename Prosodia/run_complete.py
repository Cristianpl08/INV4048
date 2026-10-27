"""Single entry point used by the upload-to-final-video Colab notebook."""
import argparse
import os
import re
from pathlib import Path
from emotivead.contracts import read_json, reference_for, write_json
from emotivead.end_to_end import analyze, prepare, sync_exports, validate_speech
from emotivead.pipeline import ENGINES, mix_project, synthesize


def main():
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['prepare', 'analyze', 'render', 'all'])
    p.add_argument('--video', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--diarization', choices=['pyannote', 'openai'], default='pyannote')
    p.add_argument('--minimum', type=float, default=2.)
    p.add_argument('--margin', type=float, default=.2)
    p.add_argument('--maximum', type=float, default=15.)
    p.add_argument('--references', type=Path)
    p.add_argument('--env', type=Path)
    p.add_argument('--option', type=int, choices=[1, 2, 3], default=3)
    p.add_argument('--narrators', nargs='+', default=['Andrea', 'Sergio', 'Sebastian'])
    p.add_argument('--duck-db', type=float, default=-14)
    p.add_argument('--max-speed', type=float, default=1.25)
    a = p.parse_args()
    out = a.output.resolve()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', out.name):
        p.error('El nombre del proyecto debe usar letras sin acentos, números, guion o guion bajo.')
    if a.env:
        os.environ.update(read_json(a.env))
    stage = a.stage
    try:
        if a.stage in ['prepare', 'all']:
            stage = 'prepare'
            if not a.video:
                p.error('--video es obligatorio para preparar el proyecto.')
            print('Extrayendo audio, diarizando y detectando escenas…', flush=True)
            candidates = prepare(a.video, out, a.diarization, a.minimum, a.margin, a.maximum)
            print(f'{len(candidates)} intervalos candidatos guardados en candidates.json', flush=True)
        if a.stage in ['analyze', 'all']:
            stage = 'analyze'
            print('GPT: descripciones de fotogramas → prosodia → resumen de cada segmento…', flush=True)
            analyze(out)
        if a.stage in ['render', 'all']:
            stage = 'render'
            if not a.references or not a.references.is_dir():
                raise ValueError('Indica --references con la carpeta Locutores.')
            projects = sync_exports(out, read_json(out/'projects.json'))
            project = projects[0]
            speech = validate_speech(read_json(out/'diarization.json'), project['duration'])
            if any(s['start'] < t['end'] and s['end'] > t['start'] for s in project['segments'] for t in speech):
                raise ValueError('Los segmentos revisados invaden diálogo; corrige sus tiempos.')
            for name in a.narrators:
                for s in project['segments']:
                    reference_for(a.references, name, s['emotion'])
            records = synthesize(project, a.narrators, ENGINES[a.option], a.references, out/'results', progress=print)
            write_json(out/'audio_manifest.json', records)
            report = mix_project(project, records, out/'results', a.duck_db, a.max_speed, print)
            write_json(out/'mix_report.json', report)
            if report['needs_edit']:
                write_json(out/'run_status.json', {'state': 'needs_edit', 'stage': stage, 'report': 'mix_report.json'})
                print('Hay voces que no caben: conserva los WAV, acorta el texto en projects.json y repite render.')
                return
        write_json(out/'run_status.json', {'state': 'completed', 'stage': stage})
    except Exception as exc:
        # Do not persist provider error objects, headers or credentials.
        write_json(out/'run_status.json', {'state': 'failed', 'stage': stage, 'error_type': type(exc).__name__})
        raise


if __name__ == '__main__':
    main()
