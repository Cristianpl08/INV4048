# 01 · Semantic description and emotion assignment

`describe_and_assign.py` implements stages 1–3 of the framework for each video clip:

1. **Keyframe selection (CLIP ViT-B/32).** One frame out of every 15 is sampled, CLIP image
   embeddings are compared, and the most diverse frames are kept: half of the sampled frames,
   with a minimum of 3 and a maximum of 30.
2. **Frame descriptions (GPT-4o, `max_tokens = 1000`).** The prompt asks the model to describe
   the seven attention dimensions: actions, special effects, environment and atmosphere, facial
   expressions, interactions, characters and body language.
3. **Emotion assignment (GPT-4o, `max_tokens = 3000`).** The model selects one of the 16 emotion
   variants (8 primary emotions × high/low intensity) and returns its prosodic instructions
   (`prosody_analysis.json`).
4. **Global AD script (GPT-4o, `max_tokens = 1500`).** The length is bounded by a
   characters-per-second range specific to the selected variant and proportional to clip
   duration (`video_summary.json`).

## Usage

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...            # never commit keys
python describe_and_assign.py process_all <videos_folder> <output_folder>
```

Each video produces `audiodescriptions.json` (frame level), `prosody_analysis.json` (selected
emotion variant) and `video_summary.json` (global script). The texts used in the paper are in
[`../data/descriptions/ad_texts.csv`](../data/descriptions/ad_texts.csv).
