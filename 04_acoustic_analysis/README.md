# 04 · Acoustic evaluation

| Script | Input | What it does |
|---|---|---|
| `reproduce_from_features.py` | `data/acoustic/features_egemaps_core.csv` | Recomputes every acoustic number of the paper without audio |
| `revision_analysis.py` | WAV files + `audio_manifest.json` | Extracts eGeMAPSv02 (OpenSMILE 2.6), runs all tests and writes tables and figures |
| `fig_redesign.py` | `features_long.csv` from `revision_analysis.py` | Radar figures (emotions, narrators, videos) and semantic benchmark figure |

## Measures

- **Descriptors (eGeMAPSv02, Functionals).** Pitch T `F0semitoneFrom27.5Hz_sma3nz_amean`,
  loudness I `loudness_sma3_amean`, tempo R `VoicedSegmentsPerSec` and pause duration D
  `MeanUnvoicedSegmentLength`.
- **Normalization.** Min–max to [1, 5] over the pooled 108 recordings (48 reference renditions
  and 60 synthesized outputs). A *z*-score within source is computed as a gain-invariant
  sensitivity check.
- **Deviation Δ.** Mean absolute difference between an output and the target profile of its
  intended emotion variant, i.e., the mean of the three narrators' renditions.
- **Specificity S.** Mean deviation from the other 15 target profiles minus Δ. S > 0 means the
  output is closer to its intended variant than to the others.
- **Statistics.**
  - Video as the unit of analysis (n = 10).
  - Wilcoxon signed-rank test for model differences and for S against zero.
  - Friedman test for narrator references.
  - Spearman correlation for reference-to-output tracking.
  - Holm correction across the four descriptors and Δ.
  - One-sided Wilcoxon tests for the a priori high- vs. low-intensity predictions (24 pairs).

```bash
pip install pandas numpy scipy statsmodels matplotlib opensmile
python reproduce_from_features.py
python revision_analysis.py --manifest ../03_reference_synthesis/outputs/audio_manifest.json \
       --references <root>/Locutores --narrators Woman01 Man01 Man02 --output results
```

Figures use DM Sans (`fonts/`, SIL Open Font License) and are saved as PNG, PDF and SVG.
