"""Reproduce the main acoustic results of the paper from the released feature table.

No audio is needed: the script reads data/acoustic/features_egemaps_core.csv
(eGeMAPSv02 functionals of the 48 reference renditions and 60 synthesized outputs)
and recomputes the deviation (Delta), the specificity index (S), the model and
narrator tests, the reference-to-output Spearman correlations, and the a priori
high- vs. low-intensity tests on the reference corpus.

Usage:
    python reproduce_from_features.py [path/to/features_egemaps_core.csv]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare, spearmanr, wilcoxon

CSV = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data/acoustic/features_egemaps_core.csv"
DESC = {"T": "F0semitoneFrom27.5Hz_sma3nz_amean", "I": "loudness_sma3_amean",
        "R": "VoicedSegmentsPerSec", "D": "MeanUnvoicedSegmentLength"}
K = list(DESC)


def holm(p):
    p = np.asarray(p, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(p) - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj


d = pd.read_csv(CSV)
for k, c in DESC.items():  # pooled min-max over all 108 recordings -> [1, 5]
    d[k] = 1 + 4 * (d[c] - d[c].min()) / (d[c].max() - d[c].min())
ref = d[d.source == "reference"]
syn = d[d.source == "synthesized"].copy()
target = ref.groupby("category")[K].mean()  # 16 target profiles

# Deviation Delta and specificity S
syn["Delta"] = [np.abs(r[K].values - target.loc[r.category].values).mean() for _, r in syn.iterrows()]
syn["Delta_other"] = [np.mean([np.abs(r[K].values - target.loc[c].values).mean() for c in target.index if c != r.category])
                      for _, r in syn.iterrows()]
syn["S"] = syn.Delta_other - syn.Delta
for k in K:
    syn["d_" + k] = [abs(r[k] - target.loc[r.category, k]) for _, r in syn.iterrows()]

print("=== Deviation from target profiles (mean ± SD over 30 outputs) ===")
print(syn.groupby("engine")["Delta"].agg(["mean", "std"]).round(2))

vid = syn.groupby(["video_id", "engine"])[["Delta"] + ["d_" + k for k in K]].mean().unstack("engine")
cols = ["d_" + k for k in K] + ["Delta"]
p = [wilcoxon(vid[c]["xtts"], vid[c]["spanish_f5"]).pvalue for c in cols]
print("\n=== Model comparison (Wilcoxon on video means, n = 10; Holm across 5 tests) ===")
for c, pv, ph in zip(cols, p, holm(p)):
    print(f"{c:8s} XTTS {vid[c]['xtts'].mean():.2f}  F5 {vid[c]['spanish_f5'].mean():.2f}  p = {pv:.4f}  p_Holm = {ph:.3f}")

print("\n=== Specificity S vs. 0 (Wilcoxon signed-rank on video means, two-sided) ===")
sv = syn.groupby(["video_id", "engine"]).S.mean().unstack()
ps = [wilcoxon(sv[e]).pvalue for e in ["xtts", "spanish_f5"]]
for e, pv, ph in zip(["xtts", "spanish_f5"], ps, holm(ps)):
    print(f"{e:10s} outputs with S > 0: {(syn[syn.engine == e].S > 0).sum()}/30  p_Holm = {ph:.4f}")

print("\n=== Narrator reference (Friedman on video means, blocks = videos) ===")
nv = syn.groupby(["video_id", "narrator_id"]).Delta.mean().unstack()
print(f"Delta: chi2 = {friedmanchisquare(*[nv[c] for c in nv]).statistic:.2f}, p = {friedmanchisquare(*[nv[c] for c in nv]).pvalue:.3f}")

print("\n=== Reference-to-output tracking (Spearman, n = 30 per model; raw units) ===")
refkey = ref.set_index(["narrator_id", "category"])
for e in ["xtts", "spanish_f5"]:
    s = syn[syn.engine == e]
    rv = refkey.loc[list(zip(s.narrator_id, s.category))]
    print(f"{e:10s}", "  ".join(f"{k}: rho = {spearmanr(rv[DESC[k]].values, s[DESC[k]].values).correlation:+.2f}" for k in K))

print("\n=== A priori: high- vs. low-intensity renditions (24 pairs, one-sided Wilcoxon) ===")
r = ref.copy()
r["num"] = r.category.str[:2].astype(int)
r["pair"] = (r.num + 1) // 2
r["high"] = r.num % 2 == 0
hi = r[r.high].set_index(["narrator_id", "pair"])
lo = r[~r.high].set_index(["narrator_id", "pair"]).loc[hi.index]
for k, alt in [("T", "greater"), ("I", "greater"), ("R", "greater"), ("D", "less")]:
    diff = hi[DESC[k]].values - lo[DESC[k]].values
    n = (diff > 0).sum() if alt == "greater" else (diff < 0).sum()
    print(f"{k}: {n}/24 in predicted direction, median diff = {np.median(diff):+.3f}, p = {wilcoxon(diff, alternative=alt).pvalue:.4f}")
