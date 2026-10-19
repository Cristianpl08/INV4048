# 03 · Reference-conditioned speech synthesis

Synthesizes each AD script with two zero-shot voice-cloning models, conditioned on the narrator
rendition of the emotion variant assigned to the video:

| Model | Package / checkpoint | Environment |
|---|---|---|
| XTTS v2 | `coqui-tts==0.27.2` | `config/xtts.linux-py311.lock.txt` |
| Spanish-F5 | `f5-tts==1.1.10`, checkpoint `jpgallegoar/F5-Spanish` (`model_1200000.safetensors`, `F5TTS_Base`) | `config/spanish_f5.linux-py311.lock.txt` |

Both models receive identical text for each video. All outputs in the paper were generated on
an NVIDIA T4 GPU (Google Colab) with seed 42, and were analyzed before any speed adjustment or
mixing: 10 videos × 3 narrators × 2 models = **60 outputs**.

## Expected input layout

```text
<root>/
  Locutores/Woman01/02 extasis.wav        # one rendition per emotion variant (16 per narrator)
  Locutores/Man01/...
  Locutores/Man02/...
  videos prueba mp4/<video_id>.mp4
  Prueba 2 VDMS (XTTS)/1. Input/<video_id>/{video_summary,prosody_analysis}.json   # output of 01
```

## Usage

```bash
python -m pip install uv
python setup_envs.py --engines xtts spanish_f5 --target .engines   # isolated Python 3.11 envs
python prepare_existing_ad.py --input "<root>/Prueba 2 VDMS (XTTS)/1. Input" \
       --videos "<root>/videos prueba mp4" --references "<root>/Locutores" --output outputs
python run_pipeline.py --root <root> --output outputs --projects outputs/projects_draft.json \
       --option 3 --env .engines/env.json          # 1 = XTTS, 2 = Spanish-F5, 3 = both
```

`prepare_existing_ad.py` strips analysis notes from the GPT-4o output so that only narration text
is synthesized, and writes an audit file. `run_pipeline.py` writes `audio_manifest.json`, which is
the input of `04_acoustic_analysis/revision_analysis.py`. The same workflow runs on Colab with
`notebooks/XTTS_SpanishF5_Colab.ipynb`.

Using XTTS v2 implies accepting the Coqui Public Model License.
