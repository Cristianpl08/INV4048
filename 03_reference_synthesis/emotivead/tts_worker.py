"""Executed in a dedicated environment per model; JSON file in, WAV + manifest out."""
import argparse
import importlib.metadata
import json
import os
import platform
import random
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('request')
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding='utf-8'))
    os.environ['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')
    import numpy as np
    import torch
    import soundfile as sf
    seed = int(request.get('seed', 42))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    engine = request['engine']
    metadata = {'engine': engine, 'device': device, 'seed': seed, 'python': platform.python_version()}
    if engine == 'xtts':
        if os.environ.get('COQUI_TOS_AGREED') != '1':
            raise RuntimeError('Lee la licencia CPML de XTTS y configura COQUI_TOS_AGREED=1 si aceptas sus condiciones.')
        from TTS.api import TTS
        model = TTS('tts_models/multilingual/multi-dataset/xtts_v2').to(device)
        metadata['model'] = 'coqui/XTTS-v2'
    elif engine == 'spanish_f5':
        from huggingface_hub import hf_hub_download
        from f5_tts.api import F5TTS
        repo = 'jpgallegoar/F5-Spanish'
        # This is the original Base checkpoint, not the different v1 architecture.
        revision = request.get('f5_revision', 'main')
        checkpoint = hf_hub_download(repo, 'model_1200000.safetensors', revision=revision)
        vocab = hf_hub_download(repo, 'vocab.txt', revision=revision)
        model = F5TTS(model='F5TTS_Base', ckpt_file=checkpoint, vocab_file=vocab, device=device)
        metadata.update(model=repo, checkpoint=checkpoint, vocab=vocab)
    elif engine == 'chatterbox':
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)
        metadata['model'] = 'ResembleAI/Chatterbox-Multilingual-TTS'
    elif engine == 'qwen3':
        from qwen_tts import Qwen3TTSModel
        model_id = 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'
        model = Qwen3TTSModel.from_pretrained(model_id, device_map='cuda:0' if device=='cuda' else 'cpu',
                    dtype=torch.bfloat16 if device=='cuda' else torch.float32, attn_implementation='sdpa')
        metadata['model'] = model_id
    else:
        raise ValueError(f'Motor desconocido: {engine}')
    metadata['packages'] = {d.metadata['Name']: d.version for d in importlib.metadata.distributions()}
    for job in request['jobs']:
        out = Path(job['output'])
        out.parent.mkdir(parents=True, exist_ok=True)
        torch.manual_seed(seed)
        if engine == 'xtts':
            model.tts_to_file(text=job['text'], speaker_wav=job['reference'], language='es', file_path=str(out))
        elif engine == 'spanish_f5':
            # Empty reference transcription invokes the upstream local ASR, never invented text.
            model.infer(ref_file=job['reference'], ref_text=job.get('reference_text', ''),
                        gen_text=job['text'], file_wave=str(out), seed=seed, remove_silence=False)
        elif engine == 'chatterbox':
            wav = model.generate(job['text'], language_id='es', audio_prompt_path=job.get('reference'),
                                 exaggeration=float(job.get('exaggeration', .5)), cfg_weight=.5)
            sf.write(out, wav.detach().cpu().squeeze().numpy(), model.sr)
        else:
            speaker = job['speaker']
            supported = model.get_supported_speakers()
            if speaker.lower() not in [s.lower() for s in supported]:
                raise ValueError(f'Voz Qwen no admitida: {speaker}')
            wavs, sr = model.generate_custom_voice(text=job['text'], language='Spanish', speaker=speaker,
                        instruct=job.get('instruct', ''), max_new_tokens=2048)
            sf.write(out, wavs[0], sr)
        data, sr = sf.read(out)
        if not len(data) or not np.isfinite(data).all() or np.abs(data).max() < 1e-5:
            raise RuntimeError(f'Audio vacío, inválido o silencioso: {out}')
        out.with_suffix('.provenance.json').write_text(json.dumps({**metadata, 'job': job,
                  'duration': len(data)/sr, 'sample_rate': sr}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
