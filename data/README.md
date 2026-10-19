# Data

| File | Contents |
|---|---|
| `videos.csv` | The ten MSVD clips (YouTube ID, start and end in seconds) with the primary emotion, emotion variant and intensity assigned by GPT-4o |
| `semantic/<video_id>/` | Output of `01_semantic_description` for each clip. It contains `audiodescriptions.json` (frame-level descriptions with attention dimensions), `prosody_analysis.json` (emotion variant and prosodic instructions), `video_summary.json` (AD script, character count and allowed range) and `keyframes/` (thumbnails of the selected frames) |
| `descriptions/ad_texts.csv` | Spanish AD script synthesized for each video (identical for both models and all narrators) |
| `acoustic/features_egemaps_core.csv` | eGeMAPSv02 descriptors of the 108 recordings: 48 reference renditions (`source = reference`) and 60 synthesized outputs (`source = synthesized`) |
| `acoustic/features_egemaps_88.csv` | Full set of 88 eGeMAPSv02 functionals for the same recordings |
| `acoustic/deviations.csv` | Per-output deviation (Δ, per descriptor and overall) and specificity S |
| `acoustic/tests_*.csv` | Model, narrator, specificity and reference-tracking tests |
| `acoustic/reference_icc.csv` | Inter-narrator agreement, ICC(2,k), per descriptor |
| `acoustic/sensitivity_normalization.csv` | Results under the gain-invariant normalization |
| `acoustic/descriptives_category.csv`, `reference_category_profiles.csv` | Descriptives per emotion variant and the 16 target profiles |

Narrators are identified only by pseudonyms (Woman01, Man01, Man02). Audio is not distributed
(see the main README). Emotion-variant labels are given in Spanish
(e.g., `02_extasis` = Joy/Ecstasy, high intensity); odd numbers are low-intensity variants and
even numbers are high-intensity variants of the same primary emotion.

License: CC BY 4.0.
