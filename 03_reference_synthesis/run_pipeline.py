import argparse
import os
from pathlib import Path
from emotivead.contracts import import_legacy, read_json, write_json
from emotivead.media import probe
from emotivead.pipeline import ENGINES, mix_project, synthesize


def main():
    p = argparse.ArgumentParser(description='EmotiveAD: mismo texto y referencias, distintos motores.')
    p.add_argument('--root', type=Path, required=True, help='Carpeta con Locutores, videos prueba mp4 y Prueba 2 VDMS (XTTS)')
    p.add_argument('--output', type=Path, default=Path('outputs'))
    p.add_argument('--option', type=int, choices=[1,2,3,4], default=3)
    p.add_argument('--env', type=Path)
    p.add_argument('--projects', type=Path, help='JSON de proyectos revisados; sustituye la importación histórica')
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--mix', action='store_true')
    p.add_argument('--narrators', nargs='+', default=['Woman01','Man01','Man02'])
    a = p.parse_args()
    if a.env:
        os.environ.update(read_json(a.env))
    projects = read_json(a.projects) if a.projects else import_legacy(a.root/'Prueba 2 VDMS (XTTS)'/'1. Input', a.root/'videos prueba mp4', probe)
    a.output.mkdir(parents=True, exist_ok=True)
    write_json(a.output/'projects.json', projects)
    count = sum(len(p['segments']) for p in projects)*len(a.narrators)*len(ENGINES[a.option])
    print(f'{len(projects)} videos; {count} audios previstos.')
    if a.prepare_only:
        return
    all_records, errors = [], []
    for project in projects:
        try:
            out = a.output/project['video_id']
            records = synthesize(project, a.narrators, ENGINES[a.option], a.root/'Locutores', out, progress=print)
            all_records.extend(records)
            if a.mix:
                mix_project(project, records, out, progress=print)
        except Exception as exc:
            errors.append({'video_id': project['video_id'], 'error': str(exc)})
            print(f"ERROR {project['video_id']}: {exc}")
    write_json(a.output/'audio_manifest.json', all_records)
    write_json(a.output/'failures.json', errors)
    if errors:
        raise SystemExit('Hay fallos; consulta failures.json. Puedes reanudar sin repetir audios verificados.')


if __name__ == '__main__':
    main()
