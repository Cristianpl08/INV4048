"""Redesigned figures (same card style, DM Sans):
  fig_radar_videos_models   one radar per video: XTTS v2 vs Spanish-F5 (mean of 3 narrators) + target profile
  fig_radar_emotions        8 primary emotions: high vs low intensity (reference corpus, mean of narrators)
  fig_benchmark_metrics     CIDEr / BLEURT / ROUGE by description model (small multiples)
Usage: python fig_redesign.py <features_long.csv> <out_dir>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import revision_analysis as ra  # noqa: E402

LONG, OUT = Path(sys.argv[1]), Path(sys.argv[2])
(OUT / "figures").mkdir(parents=True, exist_ok=True)
plt = ra._style()

COLS = {"T": "F0semitoneFrom27.5Hz_sma3nz_amean", "I": "loudness_sma3_amean",
        "R": "VoicedSegmentsPerSec", "D": "MeanUnvoicedSegmentLength"}
d = pd.read_csv(LONG)
for k, c in COLS.items():  # pooled min-max to [1,5] over all 108 recordings (as in the paper)
    d[f"n_{k}"] = 1 + 4 * (d[c] - d[c].min()) / (d[c].max() - d[c].min())
NC = [f"n_{k}" for k in "TIRD"]
d["base"] = d.category.map(ra.cat_key)
ref = d[d.source == "reference"]
syn = d[d.source == "synthesized"]
target = ref.groupby("base")[NC].mean()

XTTS_COL, F5_COL = ra.MODEL_COL
SUB = "#6b6b6b"


def panel_grid(nrow, ncol, w=3.4, h=3.9, bottom_in=0.75, top_in=1.05):
    Wt, Ht = ncol * w, nrow * h + bottom_in
    fig, axes = plt.subplots(nrow, ncol, figsize=(Wt, Ht), subplot_kw=dict(projection="polar"))
    fig.subplots_adjust(left=0.62 / Wt, right=1 - 0.62 / Wt, bottom=(bottom_in + 0.45) / Ht,
                        top=1 - top_in / Ht, wspace=1.24 / (w - 1.24), hspace=(top_in + 0.45) / (h - top_in - 0.45))
    return fig, np.ravel(axes)


def titled(ax, title, subtitle=None):
    ax.text(0.5, 1.36 if subtitle else 1.22, title, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=14, fontweight="bold", color=ra.INK)
    if subtitle:
        ax.text(0.5, 1.22, subtitle, transform=ax.transAxes, ha="center", va="bottom", fontsize=12.5, color=SUB)


# ---------------------------------------------------------------- 1) one radar per video, both models
vids = sorted(syn.video_id.unique())
fig, axes = panel_grid(2, 5, w=3.4, h=4.35, top_in=1.45)
for ax, v in zip(axes, vids):
    g = syn[syn.video_id == v]
    cat = g.base.iloc[0]
    mx = g[g.engine == "xtts"][NC].mean().values
    mf = g[g.engine == "spanish_f5"][NC].mean().values
    ra._radar(ax, [(mx, XTTS_COL, 0.16, 1.3, "-"), (mf, F5_COL, 0.16, 1.3, "-"),
                   (target.loc[cat].values, ra.INK, 0.0, 1.2, (0, (3, 2)))])
    vid = "_".join(v.split("_")[:-2]) if v.count("_") >= 2 else v  # drop the clip time range
    titled(ax, vid, ra.cat_label(cat).split("/")[-1])
ra._cards(fig, axes, pad=(0.5, 0.5, 0.42, 1.22))
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
fig.legend(handles=[Patch(facecolor=XTTS_COL, label="XTTS v2"), Patch(facecolor=F5_COL, label="Spanish-F5"),
                    Line2D([], [], color=ra.INK, lw=1.4, ls=(0, (3, 2)), label="Target profile")],
           loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.012), fontsize=13, handlelength=1.6,
           handleheight=1.1, columnspacing=1.6, handletextpad=0.5)
ra._save(fig, OUT, "fig_radar_videos_models")

# ---------------------------------------------------------------- 2) 8 primary emotions, high vs low
fig, axes = panel_grid(2, 4, w=3.4, h=4.0, top_in=1.15)
for ax, (name, hi, lo) in zip(axes, ra.PRIMARY):
    ra._radar(ax, [(target.loc[hi].values, ra.HI_COL, 0.30, 1.3, "-"),
                   (target.loc[lo].values, ra.LO_COL, 0.26, 1.3, "-")])
    titled(ax, name)
ra._cards(fig, axes, pad=(0.5, 0.5, 0.42, 0.95))
ra._legend_bottom(fig, [("High intensity", ra.HI_COL, "patch"), ("Low intensity", ra.LO_COL, "patch")],
                  y=0.012, fontsize=13)
ra._save(fig, OUT, "fig_radar_emotions")

# ---------------------------------------------------------------- 3) description-model benchmark
models = ["Our model", "VideoChat-Flash", "Tarsier", "Video-LLaVA", "ShareGPT4Video",
          "VideoMAE-GPT2", "VideoLLaMA2", "SpaceTimeGPT"]
scores = {"CIDEr": [0.775, 0.679, 0.626, 0.738, 0.421, 0.278, 0.378, 0.270],
          "BLEURT": [0.389, 0.120, 0.073, -0.094, -0.097, -0.085, -0.293, -0.244],
          "ROUGE": [0.368, 0.334, 0.267, 0.225, 0.216, 0.221, 0.253, 0.137]}
pd.DataFrame(scores, index=models).to_csv(OUT / "benchmark_metrics.csv")
fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), sharey=True)
fig.subplots_adjust(left=0.145, right=0.985, bottom=0.12, top=0.86, wspace=0.16)
y = np.arange(len(models))[::-1]
for ax, (metric, vals) in zip(axes, scores.items()):
    vals = np.array(vals)
    cols = [XTTS_COL if m == "Our model" else "#bfc5cc" for m in models]
    ax.barh(y, vals, height=0.62, color=cols, zorder=2)
    ax.axvline(0, color=ra.INK2, lw=0.8, zorder=3)
    lo, hi = min(0, vals.min()), vals.max()
    span = hi - lo
    ax.set_xlim(lo - (0.24 * span if lo < 0 else 0), hi + 0.22 * span)
    for yi, v, m in zip(y, vals, models):
        ax.text(v + (0.025 * span if v >= 0 else -0.025 * span), yi, f"{v:.3f}", va="center",
                ha="left" if v >= 0 else "right", fontsize=9,
                color=ra.INK, fontweight="bold" if m == "Our model" else "normal")
    ax.set_title(metric, fontsize=13)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="x", labelsize=8.5)
    from matplotlib.ticker import MaxNLocator
    ax.xaxis.set_major_locator(MaxNLocator(4))
axes[0].set_yticks(y, models, fontsize=10.5)
for lab in axes[0].get_yticklabels():
    if lab.get_text() == "Our model":
        lab.set_fontweight("bold")
ra._cards(fig, axes[:1], pad=(1.72, 0.12, 0.38, 0.45))
ra._cards(fig, axes[1:], pad=(0.12, 0.12, 0.38, 0.45))
ra._save(fig, OUT, "fig_benchmark_metrics")
print("done")

# ---------------------------------------------------------------- 4) 16 categories per narrator (replaces EmocionesLocutores)
GRID16 = [["extasis", "admiracion", "terror", "asombro"],
          ["serenidad", "aceptacion", "aprension", "distraccion"],
          ["duelo", "aversion", "furia", "vigilancia"],
          ["pensamiento_profundo", "aburrimiento", "molestia", "interes"]]
ROWLAB = ["HIGH INTENSITY", "LOW INTENSITY", "HIGH INTENSITY", "LOW INTENSITY"]
NARS = ["Woman01", "Man01", "Man02"]
fig, axes = panel_grid(4, 4, w=3.4, h=3.95, top_in=1.15)
fig.subplots_adjust(left=fig.subplotpars.left + 0.35 / fig.get_size_inches()[0])
axes = axes.reshape(4, 4)
for i, row in enumerate(GRID16):
    for j, cat in enumerate(row):
        ax = axes[i, j]
        series = []
        for k, n in enumerate(NARS):
            v = ref[(ref.base == cat) & (ref.narrator_id == n)][NC].values[0]
            series.append((v, ra.NAR_COL[k], 0.12, 1.2, "-"))
        series.append((target.loc[cat].values, "#8a8a8a", 0.0, 1.3, (0, (3, 2))))
        ra._radar(ax, series)
        titled(ax, ra.cat_label(cat).split("/")[-1])
    b = axes[i, 0].get_position()
    fig.text(0.012, (b.y0 + b.y1) / 2, ROWLAB[i], rotation=90, ha="left", va="center",
             fontsize=12.5, color=SUB, fontweight="medium")
ra._cards(fig, axes, pad=(0.5, 0.5, 0.42, 0.95))
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
fig.legend(handles=[Patch(facecolor=ra.NAR_COL[k], label=n) for k, n in enumerate(NARS)] +
           [Line2D([], [], color="#8a8a8a", lw=1.4, ls=(0, (3, 2)), label="Mean (target profile)")],
           loc="lower center", ncol=4, bbox_to_anchor=(0.5, 0.006), fontsize=13, handlelength=1.6,
           handleheight=1.1, columnspacing=1.6, handletextpad=0.5)
ra._save(fig, OUT, "fig_radar_narrators")
print("done 16")
