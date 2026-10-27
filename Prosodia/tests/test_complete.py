import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import soundfile as sf
from emotivead import end_to_end as flow
from emotivead.contracts import read_json, write_json
from emotivead.media import ffmpeg, frames, probe, run
from emotivead.keyframes_worker import select_indices
import run_complete


class Complete(unittest.TestCase):
    def test_openai_diarization_contract(self):
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); audio = out/'audio.wav'; audio.write_bytes(b'fixture')
            client = MagicMock()
            client.audio.transcriptions.create.return_value.model_dump.return_value = {
                'segments': [{'start': 0, 'end': 1, 'speaker': 'A', 'text': 'Hola'}]}
            with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=lambda **kwargs: client)}):
                result = flow.diarize(audio, 'openai', out)
            kwargs = client.audio.transcriptions.create.call_args.kwargs
            self.assertEqual(kwargs['model'], 'gpt-4o-transcribe-diarize')
            self.assertEqual(kwargs['response_format'], 'diarized_json')
            self.assertEqual(kwargs['chunking_strategy'], 'auto')
            self.assertEqual(result[0]['speaker'], 'A')

    def test_nested_speakers_never_create_a_false_gap(self):
        speech = [{'start': 1, 'end': 8}, {'start': 2, 'end': 3}, {'start': 4, 'end': 5}]
        result = flow.gaps(speech, 10, minimum=.5, margin=0)
        self.assertEqual([(s['start'], s['end']) for s in result], [(0, 1), (8, 10)])

    def test_no_speech_and_scene_boundaries(self):
        result = flow.gaps([], 12, minimum=2, maximum=5, cuts=[4])
        self.assertEqual([(s['start'], s['end']) for s in result], [(0, 4), (4, 8), (8, 12)])
        self.assertEqual(flow.gaps([{'start': 0, 'end': 12}], 12), [])

    def test_clip_identical_images_have_stable_ranking(self):
        self.assertEqual(select_indices(np.ones((8, 4))), [0, 1, 2, 3, 4])

    def test_cache_invalidates_on_input_or_output_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'stage.json'; calls = []
            def work(): calls.append(1); return {'ok': len(calls)}
            flow.cached(p, {'x': 1}, work); flow.cached(p, {'x': 1}, work)
            self.assertEqual(len(calls), 1)
            flow.cached(p, {'x': 2}, work)
            write_json(p, {'edited': True}); flow.cached(p, {'x': 2}, work)
            self.assertEqual(len(calls), 3)

    def test_uploaded_video_to_two_timed_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); video = root/'arbitrary name.mp4'; out = root/'project_01'
            run([ffmpeg(), '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=25:d=6',
                 '-f', 'lavfi', '-i', 'sine=frequency=300:duration=6', '-c:v', 'libx264', '-c:a', 'aac', video])
            detector = SimpleNamespace(detect=lambda *a: [], ContentDetector=lambda **k: None)
            with patch.dict(sys.modules, {'scenedetect': detector}), patch.object(flow, 'diarize', return_value=[
                    {'start': 0, 'end': 1, 'speaker': 'A'}, {'start': 4, 'end': 6, 'speaker': 'B'}]) as diarizer:
                candidates = flow.prepare(video, out)
                flow.prepare(video, out)
                self.assertEqual(diarizer.call_count, 1)
            self.assertAlmostEqual(candidates[0]['start'], 1.2)
            self.assertAlmostEqual(candidates[0]['end'], 3.8)
            def keyframes(source, segments, directory):
                return {s['id']: frames(source['video'], s['start'], s['end'], directory/'frames', 2) for s in segments}
            answers = [{'descriptions': ['Un fondo azul.', 'Un fondo azul.']},
                       {'main_emotion': 'Calma', 'complementary_emotion': 'Serenidad', 'intensity': 'baja',
                        'tone': 'suave', 'duration': 'breve', 'rhythm': 'pausado', 'rationale': 'Escena estática.'},
                       {'main_summary': 'Un fondo azul.'}]
            with patch.object(flow, 'select_keyframes', side_effect=keyframes), patch.object(flow, 'chat', side_effect=answers) as gpt:
                project = flow.analyze(out)
                flow.analyze(out)
                self.assertEqual(gpt.call_count, 3)
            refs = root/'Locutores'/'Andrea'; refs.mkdir(parents=True)
            sf.write(refs/'Serenidad.wav', np.ones(2400)*.1, 24000)
            def synth(project, narrators, engines, references, output, progress):
                records = []
                for engine in engines:
                    path = output/engine/'Andrea'/'raw'/'s001.wav'; path.parent.mkdir(parents=True)
                    sf.write(path, .1*np.sin(np.arange(12000)*2*np.pi*220/24000), 24000)
                    records.append({'engine': engine, 'narrator': 'Andrea', 'segment_id': 's001', 'path': str(path)})
                return records
            with patch.object(sys, 'argv', ['run_complete.py', 'render', '--output', str(out), '--references', str(refs.parent),
                                          '--option', '3', '--narrators', 'Andrea']), patch.object(run_complete, 'synthesize', side_effect=synth):
                run_complete.main()
            report = read_json(out/'mix_report.json')
            self.assertEqual(len(report['completed']), 2)
            self.assertEqual(report['needs_edit'], [])
            for item in report['completed']:
                self.assertAlmostEqual(probe(item['video'])['duration'], 6, delta=.15)
                audio, sr = sf.read(item['ad'])
                self.assertTrue(np.allclose(audio[:int(1.19*sr)], 0))
                self.assertGreater(np.max(np.abs(audio[int(1.2*sr):int(1.7*sr)])), .05)
            # JSON produced by GPT and JSON consumed by render resolve to the same scene IDs.
            self.assertEqual(read_json(out/'audiodescriptions.json')[0]['id'], project['segments'][0]['id'])
            self.assertTrue((out/'segments'/'s001'/'video_summary.json').exists())


if __name__ == '__main__': unittest.main()
