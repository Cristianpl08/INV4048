"""Timeline of speaker turns and AD-insertable silent intervals (data/*.json)."""
import json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).parent
for f in (HERE.parent / "04_acoustic_analysis/fonts").glob("DMSans*.ttf"):
    fm.fontManager.addfont(str(f))
FAMILY = next((f.name for f in fm.fontManager.ttflist if f.name.startswith("DM Sans")), "sans-serif")
plt.rcParams.update({"font.family": FAMILY, "font.size": 10, "svg.fonttype": "none"})
INK, INK2, GRID = "#111111", "#555555", "#cfcfcf"
SPK = ["#1F5E99", "#F07A1A", "#2A9D8F", "#7A5195", "#8C8C8C"]

dia = json.loads((HERE / "data/diarization.json").read_text())
sil = json.loads((HERE / "data/silent_segments_with_scenes.json").read_text())
speakers = sorted({d["speaker"] for d in dia})
lanes = speakers + ["AD intervals"]
end = max([d["end"] for d in dia] + [s["end"] for s in sil])

fig, ax = plt.subplots(figsize=(13, 0.55 * len(lanes) + 1.6))
fig.subplots_adjust(left=0.13, right=0.98, top=0.82, bottom=0.30)
for i, s in enumerate(speakers):
    y = len(lanes) - 1 - i
    for d in (d for d in dia if d["speaker"] == s):
        ax.barh(y, d["end"] - d["start"], left=d["start"], height=0.55, color=SPK[i % len(SPK)], lw=0)
for s in sil:
    ax.barh(0, s["end"] - s["start"], left=s["start"], height=0.55, color="#d9d9d9", edgecolor=INK2, lw=0.6)
ax.set_yticks(range(len(lanes)), lanes[::-1], color=INK)
ax.set_xlim(0, end); ax.set_xlabel("Time (s)", color=INK2)
for sp in ax.spines.values(): sp.set_visible(False)
ax.tick_params(length=0, colors=INK2); ax.grid(axis="x", color=GRID, ls=(0, (1.5, 2.5)), lw=0.6); ax.set_axisbelow(True)
ax.set_title("Speaker turns (pyannoteAI) and speech-free intervals available for AD", color=INK, fontweight="bold", loc="left", pad=12)
W, H = fig.get_size_inches(); b = ax.get_position()
fig.patches.append(FancyBboxPatch((b.x0 - 1.45 / W, b.y0 - 0.62 / H), b.width + 1.6 / W, b.height + 1.05 / H,
                   boxstyle="round,pad=0,rounding_size=0.02", transform=fig.transFigure, facecolor="#f8f8f8",
                   edgecolor="#e7e7e7", lw=0.9, zorder=-10, mutation_aspect=W / H))
out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "docs/figures/diarization_timeline.png"
fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.15)
print(out)
