"""Prepare existing AD for a paired TTS experiment, without API calls."""
import argparse
import re
from pathlib import Path
from emotivead.contracts import import_legacy, reference_for, write_json
from emotivead.media import probe


def narration_only(text):
    kept = []
    for line in text.splitlines():
        heading = re.sub(r'^[\s*#\-]+', '', line).replace('**', '')
        if re.match(r'(?i)(mecanismo de atenci[oó]n|emoci[oó]n complementaria|n[uú]mero total de caracteres|car[aá]cteres (por|de)|rango de caracteres|resumen\s*:)', heading):
            break
        kept.append(line.replace('**', ''))
    result = '\n'.join(kept).strip()
    if not result:
        raise ValueError('La limpieza dejó una AD vacía; revisa el resumen original.')
    return result


def prepare(input_dir, videos, references, output, narrators, clean=True):
    output = Path(output)
    projects = import_legacy(Path(input_dir), Path(videos), probe)
    audit = []
    for project in projects:
        segment = project['segments'][0]
        original = segment['text']
        segment['text'] = narration_only(original) if clean else original
        project['source'] = 'existing_ad_reviewed_copy'
        for narrator in narrators:
            reference_for(references, narrator, segment['emotion'])
        audit.append({'video_id': project['video_id'], 'original': original,
                      'narration': segment['text'], 'changed': original != segment['text'],
                      'emotion': segment['emotion'], 'duration_s': project['duration']})
    # Draft is deliberately separate: preparing again cannot overwrite human review.
    write_json(output/'projects_draft.json', projects)
    write_json(output/'text_preparation_audit.json', audit)
    write_json(output/'input_validation.json', {'n_videos': len(projects), 'narrators': narrators,
               'expected_audio_both': len(projects)*len(narrators)*2,
               'input_dir': str(Path(input_dir).resolve()), 'api_calls': 0})
    return projects


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--videos', type=Path, required=True)
    p.add_argument('--references', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--narrators', nargs='+', default=['Woman01','Man01','Man02'])
    p.add_argument('--keep-metadata', action='store_true')
    a = p.parse_args()
    projects = prepare(a.input, a.videos, a.references, a.output, a.narrators, not a.keep_metadata)
    print(f'{len(projects)} AD validadas; {len(projects)*len(a.narrators)*2} audios previstos con ambos motores.')
