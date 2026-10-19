# 02 · Reverse diarization and silence detection

> **Framework component, not evaluated in the paper.** The ten MSVD clips used in the experiment
> have no audio track, so this stage was not applied (§3.2). It is released because it defines
> where AD can be inserted in videos with dialogue.

`src/diarize_silence.py` (author: C. Plazas):

1. Extracts the audio track of a video (MoviePy).
2. Sends it to pyannoteAI for speaker diarization.
3. Rebuilds one audio track per speaker.
4. Detects speech-free intervals between turns and merges intervals closer than 2 s.
5. Splits silent intervals at visual scene changes (PySceneDetect, `ContentDetector`).

```bash
pip install -r requirements.txt
cp .env.example .env                 # add PYANNOTE_API_TOKEN
python src/diarize_silence.py
```

`data/` contains example outputs (`diarization.json`, `silent_segments_joined.json`,
`silent_segments_with_scenes.json`), and `notebooks/diarization_pipeline.ipynb` runs the
same steps interactively.
