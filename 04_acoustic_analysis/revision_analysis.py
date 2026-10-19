#!/usr/bin/env python3
"""Statistical analysis requested by the reviewers (comments 1, 3 and 5).

Reads the audio manifest produced by run_pipeline.py and the narrator reference
recordings, extracts eGeMAPSv02 Functionals with openSMILE, builds a common
normalized space, computes alignment / specificity scores and runs the
statistical tests described in the revised Section 4.6.

Unit of analysis: the VIDEO (n = 10). The three narrator references and the two
models are repeated measures within each video, so they are never treated as
independent observations.

Outputs (in --output):
  features_long.csv             raw eGeMAPS features for references and synth outputs
  reference_category_map.csv    detected categories x narrators (check this first)
  deviations.csv                per-output deviations (normalized, z, raw units)
  descriptives_*.csv            mean, SD, median, 95% bootstrap CI
  tests_*.csv                   statistic, p, p_Holm, effect size, CI
  reference_icc.csv             inter-narrator consistency per feature
  mixed_model.txt               sensitivity analysis
  tables/*.tex                  LaTeX tables with the numbers filled in
  figures/*.pdf|png             dispersion figures that replace/complement radars
  RESULTADOS_MANUSCRITO.md      auto-written result sentences for the paper
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------
CORE = {
    "T": "F0semitoneFrom27.5Hz_sma3nz_amean",
    "I": "loudness_sma3_amean",
    "R": "VoicedSegmentsPerSec",
    "D": "MeanUnvoicedSegmentLength",
}
CORE_LABEL = {"T": "F0 (T)", "I": "Loudness (I)", "R": "Tempo (R)", "D": "Pause (D)"}
CORE_UNIT = {"T": "st", "I": "sone", "R": "seg/s", "D": "s"}
# Extra descriptors for comment 3 (contour / range / alternative rate proxy)
EXTRA = {
    "F0_sd": "F0semitoneFrom27.5Hz_sma3nz_stddevNorm",
    "F0_range": "F0semitoneFrom27.5Hz_sma3nz_pctlrange0-2",
    "Loud_sd": "loudness_sma3_stddevNorm",
    "LoudPeaks": "loudnessPeaksPerSec",
    "Unvoiced_sd": "StddevUnvoicedSegmentLength",
}
KEYS = list(CORE)
AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}

COL_MODEL = {"xtts": "#2a78d6", "spanish_f5": "#eb6834"}
COL_NAR = ["#2a78d6", "#eb6834", "#1baf7a"]
MARK_NAR = ["o", "s", "^"]
MODEL_LABEL = {"xtts": "XTTS v2", "spanish_f5": "Spanish-F5"}


CAT_EN = {"serenidad": "Joy/Serenity", "extasis": "Joy/Ecstasy", "aceptacion": "Trust/Acceptance",
          "admiracion": "Trust/Admiration", "aprension": "Fear/Apprehension", "terror": "Fear/Terror",
          "distraccion": "Surprise/Distraction", "asombro": "Surprise/Amazement",
          "pensamiento_profundo": "Sadness/Pensiveness", "duelo": "Sadness/Grief",
          "aburrimiento": "Disgust/Boredom", "aversion": "Disgust/Loathing", "molestia": "Anger/Annoyance",
          "furia": "Anger/Rage", "interes": "Anticipation/Interest", "vigilancia": "Anticipation/Vigilance"}


def cat_key(c: str) -> str:
    key = re.sub(r"^\d+_", "", str(c))
    if key in CAT_EN:
        return key
    for k in CAT_EN:  # e.g. "alegria_extasis" -> "extasis"
        if key.endswith(k):
            return k
    return key


def cat_label(c: str) -> str:
    key = cat_key(c)
    return CAT_EN.get(key, key.replace("_", " ").title())


def norm_txt(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def category_key(path: Path, narrator: str) -> str:
    key = norm_txt(path.stem)
    key = re.sub(rf"(^|_){re.escape(norm_txt(narrator))}(_|$)", "_", key).strip("_")
    return key


def extract(paths: list[Path]) -> pd.DataFrame:
    import opensmile

    smile = opensmile.Smile(
        feature_set=opensmile.FeatureSet.eGeMAPSv02,
        feature_level=opensmile.FeatureLevel.Functionals,
    )
    rows = []
    for p in paths:
        f = smile.process_file(str(p)).reset_index(drop=True).iloc[0]
        rows.append(f)
    out = pd.DataFrame(rows).reset_index(drop=True)
    out.insert(0, "path", [str(p) for p in paths])
    return out


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------
def holm(p: list[float]) -> list[float]:
    p = np.asarray(p, float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj.tolist()


def boot_ci(x, func=np.median, n=10000, seed=7):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 3 or np.ptp(x) == 0:
        return (np.nan, np.nan)
    for method in ("BCa", "percentile"):
        try:
            r = stats.bootstrap((x,), func, n_resamples=n, method=method,
                                random_state=np.random.default_rng(seed))
            lo, hi = r.confidence_interval
            if np.isfinite(lo) and np.isfinite(hi):
                return (float(lo), float(hi))
        except Exception:
            continue
    return (np.nan, np.nan)


def rank_biserial(diff) -> float:
    d = np.asarray(diff, float)
    d = d[d != 0]
    if len(d) == 0:
        return 0.0
    r = stats.rankdata(np.abs(d))
    return float((r[d > 0].sum() - r[d < 0].sum()) / r.sum())


def wilcoxon(a, b=None):
    d = np.asarray(a, float) - (0 if b is None else np.asarray(b, float))
    if np.allclose(d, 0):
        return dict(stat=np.nan, p=1.0, r_rb=0.0, med_diff=0.0, ci_lo=np.nan, ci_hi=np.nan, n=len(d))
    res = stats.wilcoxon(d, zero_method="wilcox", method="auto")
    lo, hi = boot_ci(d)
    return dict(stat=float(res.statistic), p=float(res.pvalue), r_rb=rank_biserial(d),
                med_diff=float(np.median(d)), ci_lo=lo, ci_hi=hi, n=len(d))


def _boot_rho(a, b, n=5000, seed=7):
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(a), len(a))
        if np.ptp(a[i]) > 0 and np.ptp(b[i]) > 0:
            vals.append(stats.spearmanr(a[i], b[i])[0])
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))) if vals else (np.nan, np.nan)


def describe(x) -> dict:
    x = np.asarray(x, float)
    lo, hi = boot_ci(x)
    return dict(n=len(x), mean=np.mean(x), sd=np.std(x, ddof=1) if len(x) > 1 else np.nan,
                median=np.median(x), ci_lo=lo, ci_hi=hi, min=np.min(x), max=np.max(x))


def icc2(mat: np.ndarray) -> tuple[float, float]:
    """Two-way random, absolute agreement. Rows = targets (categories), cols = raters."""
    n, k = mat.shape
    grand = mat.mean()
    ssr = k * ((mat.mean(1) - grand) ** 2).sum()
    ssc = n * ((mat.mean(0) - grand) ** 2).sum()
    sse = ((mat - grand) ** 2).sum() - ssr - ssc
    msr, msc, mse = ssr / (n - 1), ssc / (k - 1), sse / ((n - 1) * (k - 1))
    icc21 = (msr - mse) / (msr + (k - 1) * mse + k * (msc - mse) / n)
    icc2k = (msr - mse) / (msr + (msc - mse) / n)
    return float(icc21), float(icc2k)


def icc_boot(mat, n=5000, seed=7):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        idx = rng.integers(0, mat.shape[0], mat.shape[0])
        try:
            vals.append(icc2(mat[idx])[1])
        except Exception:
            pass
    vals = np.array(vals)
    vals = vals[np.isfinite(vals)]
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))) if len(vals) else (np.nan, np.nan)


def fmt(x, d=2):
    return "--" if x is None or not np.isfinite(x) else f"{x:.{d}f}"


def peq(p):
    s = fmt_p(p)
    return s if s.startswith("<") else "=" + s


def fmt_p(p):
    if p is None or not np.isfinite(p):
        return "--"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def build_reference_table(refs: Path, narrators: list[str]) -> pd.DataFrame:
    rows = []
    for p in sorted(refs.rglob("*")):
        if p.suffix.lower() not in AUDIO_EXT:
            continue
        parts = [norm_txt(x) for x in p.relative_to(refs).parts]
        nar = next((n for n in narrators if norm_txt(n) in parts or norm_txt(n) in norm_txt(p.stem)), None)
        if nar is None:
            continue
        rows.append(dict(narrator=nar, category=category_key(p, nar), path=str(p.resolve())))
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit(f"No reference audio found under {refs}")
    dup = df.duplicated(["narrator", "category"], keep=False)
    if dup.any():
        print("WARNING duplicated narrator/category references (keeping first):")
        print(df[dup].to_string())
        df = df.drop_duplicates(["narrator", "category"])
    return df


def resolve_reference(rec, refs, ref_df, lookup):
    if rec.get("reference"):
        p = Path(rec["reference"])
        if p.exists():
            return str(p.resolve())
    if lookup is not None:
        try:
            return str(Path(lookup(refs, rec["narrator"], rec["emotion"])).resolve())
        except Exception:
            pass
    sub = ref_df[ref_df.narrator == rec["narrator"]]
    emo = norm_txt(rec["emotion"])
    hit = sub[sub.category.apply(lambda c: c == emo or emo in c or c in emo)]
    if len(hit) == 1:
        return hit.path.iloc[0]
    raise RuntimeError(f"Cannot resolve reference for {rec['narrator']} / {rec['emotion']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", nargs="+", required=True, help="one or more audio_manifest.json")
    ap.add_argument("--references", required=True)
    ap.add_argument("--narrators", nargs="+", required=True)
    ap.add_argument("--pseudonyms", nargs="+", default=[], help="folder=pseudonym pairs, e.g. NarratorA=Woman01 (optional when folders already use pseudonyms)")
    ap.add_argument("--output", required=True)
    ap.add_argument("--engines", nargs="+", default=None, help="restrict to these engines (e.g. xtts spanish_f5)")
    ap.add_argument("--features-csv", default=None, help="reuse previously extracted features")
    args = ap.parse_args()

    out = Path(args.output)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    refs = Path(args.references)
    pseudo = dict(x.split("=", 1) for x in args.pseudonyms)
    alias = lambda n: pseudo.get(n, n)

    try:
        from emotivead.contracts import reference_for as lookup
    except Exception:
        lookup = None
        print("emotivead.contracts.reference_for not importable; using filename matching.")

    # ---- references -------------------------------------------------------
    ref_df = build_reference_table(refs, args.narrators)
    cmap = ref_df.pivot_table(index="category", columns="narrator", values="path", aggfunc="count").fillna(0).astype(int)
    cmap.to_csv(out / "reference_category_map.csv")
    complete = cmap.index[(cmap[args.narrators] == 1).all(axis=1)].tolist() if set(args.narrators) <= set(cmap.columns) else []
    print(f"Reference recordings: {len(ref_df)} | complete categories (all narrators): {len(complete)}")
    if len(complete) != 16:
        print("WARNING: expected 16 complete categories. Check reference_category_map.csv")

    # ---- synth manifest ---------------------------------------------------
    recs = []
    for mf in args.manifest:
        recs += json.loads(Path(mf).read_text(encoding="utf-8"))
    if args.engines:
        recs = [r for r in recs if r["engine"] in args.engines]
    seen = set()
    for r in recs:
        key = (r["engine"], r["video_id"], r["narrator"])
        if key in seen:
            sys.exit(f"Duplicated output in manifests: {key}")
        seen.add(key)
    syn = pd.DataFrame(recs)
    need = {"engine", "narrator", "emotion", "path", "video_id"}
    if not need <= set(syn.columns):
        sys.exit(f"Manifest is missing fields: {need - set(syn.columns)}")
    syn["reference"] = [resolve_reference(r, refs, ref_df, lookup) for r in recs]
    path2cat = dict(zip(ref_df.path, ref_df.category))
    syn["category"] = syn.reference.map(path2cat)
    if syn.category.isna().any():
        bad = syn[syn.category.isna()][["narrator", "emotion", "reference"]]
        sys.exit("Conditioning references not found among reference recordings:\n" + bad.to_string())
    syn["path"] = syn.path.apply(lambda p: str(Path(p).resolve()))

    # ---- features ---------------------------------------------------------
    feat_cols = list(CORE.values()) + list(EXTRA.values())
    if args.features_csv and Path(args.features_csv).exists():
        allf = pd.read_csv(args.features_csv)
    else:
        print("Extracting eGeMAPSv02 functionals ...")
        allf = extract([Path(p) for p in list(ref_df.path) + list(syn.path)])
    allf.to_csv(out / "features_raw_egemaps.csv", index=False)
    f = allf.set_index("path")[feat_cols]

    R = ref_df.join(f, on="path").assign(source="reference")
    S = syn.join(f, on="path").assign(source="synthesized")
    long = pd.concat([R, S], ignore_index=True, sort=False)
    long["narrator_id"] = long.narrator.map(alias)
    long.to_csv(out / "features_long.csv", index=False)

    # ---- normalization (pooled 48 + 60) ------------------------------------
    raw = long[list(CORE.values())].astype(float)
    mn, mx = raw.min(), raw.max()
    long[[f"n_{k}" for k in KEYS]] = (1 + 4 * (raw - mn) / (mx - mn)).values
    long[[f"z_{k}" for k in KEYS]] = ((raw - raw.mean()) / raw.std(ddof=1)).values
    long[[f"r_{k}" for k in KEYS]] = raw.values
    R = long[long.source == "reference"]
    S = long[long.source == "synthesized"].copy()

    # targets = mean over narrators per category, in each space
    def targets(prefix):
        return R[R.category.isin(complete)].groupby("category")[[f"{prefix}_{k}" for k in KEYS]].mean()

    tgt = {p: targets(p) for p in ("n", "z", "r")}
    ref_by = R.set_index(["narrator", "category"])

    rows = []
    for _, s in S.iterrows():
        row = dict(engine=s.engine, narrator=s.narrator, narrator_id=s.narrator_id,
                   video_id=s.video_id, category=s.category, path=s.path)
        for p in ("n", "z", "r"):
            v = np.array([s[f"{p}_{k}"] for k in KEYS], float)
            t = tgt[p].loc[s.category].values
            d = np.abs(v - t)
            for k, dk in zip(KEYS, d):
                row[f"{p}_d_{k}"] = dk
            if p != "r":  # raw units are not comparable across features -> no mean
                row[f"{p}_D"] = d.mean()
                own = ref_by.loc[(s.narrator, s.category), [f"{p}_{k}" for k in KEYS]].values.astype(float)
                row[f"{p}_Dnar"] = np.abs(v - own).mean()
                others = tgt[p].drop(index=s.category)
                row[f"{p}_Dother"] = np.abs(others.values - v).mean(axis=1).mean()
                row[f"{p}_S"] = row[f"{p}_Dother"] - row[f"{p}_D"]
        rows.append(row)
    dev = pd.DataFrame(rows)
    dev.to_csv(out / "deviations.csv", index=False)

    engines = [e for e in ("xtts", "spanish_f5") if e in dev.engine.unique()] or sorted(dev.engine.unique())
    nar_ids = [alias(n) for n in args.narrators]
    measures = [f"n_d_{k}" for k in KEYS] + ["n_D", "n_Dnar"]
    mlabel = {**{f"n_d_{k}": CORE_LABEL[k] for k in KEYS}, "n_D": "Overall D", "n_Dnar": "D_nar (own reference)"}

    # ---- video-level aggregation ------------------------------------------
    vid_model = dev.groupby(["video_id", "engine"])[measures + ["z_D", "n_S", "z_S"]].mean().reset_index()
    vid_nar = dev.groupby(["video_id", "narrator_id"])[measures].mean().reset_index()

    # ---- descriptives -----------------------------------------------------
    desc = []
    for e in engines:
        for m in measures + ["n_S"]:
            desc.append(dict(group="model", level=e, measure=m, **describe(dev.loc[dev.engine == e, m])))
    for n in nar_ids:
        for m in measures:
            desc.append(dict(group="narrator", level=n, measure=m, **describe(dev.loc[dev.narrator_id == n, m])))
    desc = pd.DataFrame(desc)
    desc.to_csv(out / "descriptives_model_narrator.csv", index=False)

    cat_rows = []
    for c, g in dev.groupby("category"):
        for e in engines:
            ge = g[g.engine == e]
            vids = ge.video_id.nunique()
            per_vid = ge.groupby("video_id").n_D.mean()
            lo, hi = boot_ci(per_vid) if vids >= 3 else (np.nan, np.nan)
            cat_rows.append(dict(category=c, engine=e, n_videos=vids, n_outputs=len(ge),
                                 mean=ge.n_D.mean(), sd=ge.n_D.std(ddof=1), median=ge.n_D.median(),
                                 min=ge.n_D.min(), max=ge.n_D.max(), ci_lo=lo, ci_hi=hi,
                                 S_mean=ge.n_S.mean()))
    cat_df = pd.DataFrame(cat_rows).sort_values(["n_videos", "category"], ascending=[False, True])
    cat_df.insert(1, "label", cat_df.category.map(cat_label))
    cat_df.to_csv(out / "descriptives_category.csv", index=False)

    # ---- tests: model (paired at video level) ------------------------------
    tests_model = []
    if len(engines) == 2:
        a, b = engines
        wide = vid_model.pivot(index="video_id", columns="engine")
        for m in measures:
            r = wilcoxon(wide[(m, a)], wide[(m, b)])
            tests_model.append(dict(measure=m, label=mlabel[m],
                                    mean_a=wide[(m, a)].mean(), mean_b=wide[(m, b)].mean(), **r))
        tm = pd.DataFrame(tests_model)
        core_mask = tm.measure.isin([f"n_d_{k}" for k in KEYS] + ["n_D"])
        tm.loc[core_mask, "p_holm"] = holm(tm.loc[core_mask, "p"].tolist())
        tm.loc[~core_mask, "p_holm"] = tm.loc[~core_mask, "p"]
        # sensitivity: same test on z-score space
        rz = wilcoxon(wide[("z_D", a)], wide[("z_D", b)])
        tm = pd.concat([tm, pd.DataFrame([dict(measure="z_D", label="Overall D (z-score space)",
                                               mean_a=wide[("z_D", a)].mean(), mean_b=wide[("z_D", b)].mean(),
                                               p_holm=rz["p"], **rz)])], ignore_index=True)
        tm.attrs = {"a": a, "b": b}
        tm.to_csv(out / "tests_model.csv", index=False)
    else:
        tm = pd.DataFrame()

    # ---- tests: narrator (Friedman, blocks = videos) ----------------------
    tn = []
    widen = vid_nar.pivot(index="video_id", columns="narrator_id")
    for m in measures:
        X = widen[m][nar_ids].dropna()
        chi, p = stats.friedmanchisquare(*[X[c] for c in nar_ids])
        W = chi / (len(X) * (len(nar_ids) - 1))
        tn.append(dict(measure=m, label=mlabel[m], chi2=chi, p=p, kendall_W=W, n_blocks=len(X),
                       **{f"mean_{c}": X[c].mean() for c in nar_ids}))
    tn = pd.DataFrame(tn)
    core_mask = tn.measure.isin([f"n_d_{k}" for k in KEYS] + ["n_D"])
    tn.loc[core_mask, "p_holm"] = holm(tn.loc[core_mask, "p"].tolist())
    tn.loc[~core_mask, "p_holm"] = tn.loc[~core_mask, "p"]
    tn.to_csv(out / "tests_narrator.csv", index=False)

    post = []
    X = widen["n_D"][nar_ids]
    for i in range(len(nar_ids)):
        for j in range(i + 1, len(nar_ids)):
            r = wilcoxon(X[nar_ids[i]], X[nar_ids[j]])
            post.append(dict(pair=f"{nar_ids[i]} vs {nar_ids[j]}", **r))
    post = pd.DataFrame(post)
    post["p_holm"] = holm(post.p.tolist())
    post.to_csv(out / "tests_narrator_posthoc.csv", index=False)

    # ---- tests: specificity (S > 0) ---------------------------------------
    spec = []
    for e in engines:
        v = vid_model.loc[vid_model.engine == e, "n_S"]
        r = wilcoxon(v)
        spec.append(dict(engine=e, n_outputs_pos=int((dev.loc[dev.engine == e, "n_S"] > 0).sum()),
                         n_outputs=int((dev.engine == e).sum()), **r))
    spec = pd.DataFrame(spec)
    spec["p_holm"] = holm(spec.p.tolist())
    spec.to_csv(out / "tests_specificity.csv", index=False)

    # ---- reference corpus: ICC + narrator profiles -------------------------
    icc_rows = []
    for k in KEYS + list(EXTRA):
        col = CORE.get(k, EXTRA.get(k))
        mat = R[R.category.isin(complete)].pivot(index="category", columns="narrator", values=col)[args.narrators].values.astype(float)
        if mat.shape[0] < 3 or np.isnan(mat).any():
            continue
        i1, ik = icc2(mat)
        lo, hi = icc_boot(mat)
        icc_rows.append(dict(feature=k, column=col, icc2_1=i1, icc2_k=ik, ci_lo=lo, ci_hi=hi, n_categories=mat.shape[0]))
    icc_df = pd.DataFrame(icc_rows)
    icc_df.to_csv(out / "reference_icc.csv", index=False)

    nar_prof = R.groupby("narrator_id")[[f"n_{k}" for k in KEYS]].agg(["mean", "std"])
    nar_prof.to_csv(out / "reference_narrator_profiles.csv")
    cat_prof = R[R.category.isin(complete)].groupby("category")[[f"r_{k}" for k in KEYS] + [f"n_{k}" for k in KEYS]].agg(["mean", "std"])
    cat_prof.to_csv(out / "reference_category_profiles.csv")

    # does each feature vary across the 16 categories? (Friedman, blocks = narrators)
    var_rows = []
    for k in KEYS:
        mat = R[R.category.isin(complete)].pivot(index="narrator", columns="category", values=CORE[k])
        chi, p = stats.friedmanchisquare(*[mat[c] for c in mat.columns])
        var_rows.append(dict(feature=k, chi2=chi, df=mat.shape[1] - 1, p=p,
                             kendall_W=chi / (mat.shape[0] * (mat.shape[1] - 1))))
    var_df = pd.DataFrame(var_rows)
    var_df["p_holm"] = holm(var_df.p.tolist())
    var_df.to_csv(out / "tests_reference_category_variation.csv", index=False)

    # ---- reference -> output tracking (does each output follow ITS conditioning recording?) ----
    track_feats = {**{k: CORE[k] for k in KEYS}, "F0_sd": EXTRA["F0_sd"], "F0_range": EXTRA["F0_range"]}
    Rk = R.set_index(["narrator", "category"])
    trk = []
    pairs = {}
    for e in engines:
        Se = S[S.engine == e]
        for k, col in track_feats.items():
            ref = np.array([Rk.loc[(a_, b_), col] for a_, b_ in zip(Se.narrator, Se.category)], float)
            syn = Se[col].values.astype(float)
            pairs[(e, k)] = (ref, syn, Se.narrator.values)
            rho, prho = stats.spearmanr(ref, syn)
            rlo, rhi = _boot_rho(ref, syn)
            d = syn - ref
            w = stats.wilcoxon(d) if not np.allclose(d, 0) else None
            trk.append(dict(engine=e, feature=k, column=col, ref_mean=ref.mean(), ref_sd=ref.std(ddof=1),
                            syn_mean=syn.mean(), syn_sd=syn.std(ddof=1), sd_ratio=syn.std(ddof=1) / ref.std(ddof=1),
                            rho=rho, rho_ci_lo=rlo, rho_ci_hi=rhi, p_rho=prho,
                            median_bias=float(np.median(d)), p_bias=(w.pvalue if w else 1.0), n=len(d)))
    trk = pd.DataFrame(trk)
    for e in engines:  # Holm within each model
        m = trk.engine == e
        trk.loc[m, "p_rho_holm"] = holm(trk.loc[m, "p_rho"].tolist())
        trk.loc[m, "p_bias_holm"] = holm(trk.loc[m, "p_bias"].tolist())
    # does tracking differ between models? (Fisher z on Spearman rho, descriptive)
    if len(engines) == 2:
        for k in track_feats:
            r1 = trk[(trk.engine == engines[0]) & (trk.feature == k)].iloc[0]
            r2 = trk[(trk.engine == engines[1]) & (trk.feature == k)].iloc[0]
            z = (np.arctanh(np.clip(r1.rho, -0.999, 0.999)) - np.arctanh(np.clip(r2.rho, -0.999, 0.999))) / np.sqrt(1 / (r1.n - 3) + 1 / (r2.n - 3))
            trk.loc[trk.feature == k, "p_rho_diff"] = 2 * stats.norm.sf(abs(z))
    trk.to_csv(out / "tests_reference_tracking.csv", index=False)

    # sensitivity: remove output-level gain differences (z-score within source AND model) and drop loudness
    long["src_key"] = long.source + "|" + long.engine.fillna("ref").astype(str)
    for col in [CORE[k] for k in KEYS]:
        long[f"zs_{col}"] = long.groupby("src_key")[col].transform(lambda x: (x - x.mean()) / x.std(ddof=1))
    Rz = long[long.source == "reference"]
    Sz = long[long.source == "synthesized"]
    tz = Rz[Rz.category.isin(complete)].groupby("category")[[f"zs_{CORE[k]}" for k in KEYS]].mean()
    sens = []
    for _, s_ in Sz.iterrows():
        v = np.array([s_[f"zs_{CORE[k]}"] for k in KEYS], float)
        dd = np.abs(v - tz.loc[s_.category].values)
        oth = np.abs(tz.drop(index=s_.category).values - v).mean(axis=1).mean()
        sens.append(dict(path=s_.path, zs_D=dd.mean(), zs_D_noI=np.delete(dd, KEYS.index("I")).mean(), zs_S=oth - dd.mean()))
    sens = pd.DataFrame(sens)
    dev = dev.merge(sens, on="path", how="left")
    dev["n_D_noI"] = dev[[f"n_d_{k}" for k in KEYS if k != "I"]].mean(axis=1)
    dev.to_csv(out / "deviations.csv", index=False)
    sens_rows = []
    for e in engines:
        de = dev[dev.engine == e]
        for m, lab in [("n_D", "Overall D (pooled min-max)"), ("n_D_noI", "D without loudness"),
                       ("zs_D", "D, z-score within source (gain-invariant)"), ("zs_D_noI", "z within source, without loudness")]:
            vm = de.groupby("video_id")[m].mean()
            sens_rows.append(dict(engine=e, measure=m, label=lab, **describe(de[m]), video_level_median=vm.median()))
        for m, lab in [("n_S", "Specificity S (pooled min-max)"), ("zs_S", "Specificity S (z within source)")]:
            vm = de.groupby("video_id")[m].mean()
            r = wilcoxon(vm)
            sens_rows.append(dict(engine=e, measure=m, label=lab, **describe(de[m]), video_level_median=vm.median(),
                                  n_pos=int((de[m] > 0).sum()), p_wilcoxon=r["p"], r_rb=r["r_rb"]))
    sens_df = pd.DataFrame(sens_rows)
    if len(engines) == 2:  # paired model comparison under each normalization
        for m in ["n_D_noI", "zs_D", "zs_D_noI"]:
            w_ = dev.groupby(["video_id", "engine"])[m].mean().unstack()[engines]
            r = wilcoxon(w_[engines[0]], w_[engines[1]])
            sens_df.loc[sens_df.measure == m, "p_model_diff"] = r["p"]
            sens_df.loc[sens_df.measure == m, "r_rb_model"] = r["r_rb"]
    sens_df.to_csv(out / "sensitivity_normalization.csv", index=False)

    # ---- mixed model (sensitivity) ----------------------------------------
    try:
        import statsmodels.formula.api as smf
        forms = (["n_D ~ C(engine) * C(narrator_id)", "n_D ~ C(engine) + C(narrator_id)"]
                 if dev.engine.nunique() > 1 else ["n_D ~ C(narrator_id)"])
        mm_ok, last = False, None
        for formula in forms:
            for method in ("lbfgs", "powell", "nm"):
                try:
                    fit = smf.mixedlm(formula, dev, groups=dev["video_id"]).fit(reml=True, method=method)
                    (out / "mixed_model.txt").write_text(f"Formula: {formula} + (1|video); optimizer: {method}\n\n" + str(fit.summary()))
                    mm_ok = True
                    break
                except Exception as exc:
                    last = exc
            if mm_ok:
                break
        if not mm_ok:
            raise last
    except Exception as exc:
        (out / "mixed_model.txt").write_text(f"Mixed model failed: {exc}")
        mm_ok = False

    # ---- design table ------------------------------------------------------
    design = dev.groupby(["engine", "narrator_id"]).size().unstack(fill_value=0)
    design.to_csv(out / "design_counts.csv")

    write_tables(out, desc, tm, tn, cat_df, icc_df, spec, engines, nar_ids, mlabel, dev)
    write_tracking_table(out, trk, sens_df)
    tracking_figure(out, pairs, S, nar_ids, args.narrators, alias)
    make_figures(out, dev, vid_model, vid_nar, R, complete, engines, nar_ids)
    radar_figures(out, long, complete, nar_ids, args.narrators, alias)
    write_report(out, tm, tn, post, spec, icc_df, var_df, cat_df, nar_prof, engines, nar_ids, dev, complete, mm_ok)
    append_tracking_report(out, trk, sens_df)
    print("Done:", out)


# ---------------------------------------------------------------------------
# LaTeX tables
# ---------------------------------------------------------------------------
def cell(d):
    return f"{fmt(d['mean'])} $\\pm$ {fmt(d['sd'])}; {fmt(d['median'])} [{fmt(d['ci_lo'])}, {fmt(d['ci_hi'])}]"


def write_tables(out, desc, tm, tn, cat_df, icc_df, spec, engines, nar_ids, mlabel, dev):
    T = out / "tables"
    ms = [f"n_d_{k}" for k in KEYS] + ["n_D", "n_Dnar"]

    if len(tm):
        a, b = engines
        lines = [r"\begin{table*}[htbp]", r"\centering",
                 r"\caption{Deviation from reference-derived target profiles by synthesis model and feature (pooled normalized scale [1,5]; lower is better). Values are mean $\pm$ SD and median [95\%% bootstrap CI] over $n=%d$ outputs per model. Tests: Wilcoxon signed-rank on video-level means ($n=%d$ videos), Holm-corrected across the four features and the overall score; $r_{rb}$: matched-pairs rank-biserial correlation (positive values indicate larger deviation for %s).}" % (
                     (dev.engine == a).sum(), dev.video_id.nunique(), MODEL_LABEL.get(a, a)),
                 r"\label{tab:alignment_model}", r"\small",
                 r"\begin{tabular}{lcccc}", r"\toprule",
                 f"Feature & {MODEL_LABEL.get(a, a)} & {MODEL_LABEL.get(b, b)} & $p_{{\\mathrm{{Holm}}}}$ & $r_{{rb}}$ \\\\", r"\midrule"]
        for m in ms:
            da = desc[(desc.group == "model") & (desc.level == a) & (desc.measure == m)].iloc[0]
            db = desc[(desc.group == "model") & (desc.level == b) & (desc.measure == m)].iloc[0]
            t = tm[tm.measure == m].iloc[0]
            lab = mlabel[m].replace("D_nar (own reference)", r"$D^{\mathrm{nar}}$").replace("Overall D", r"Overall $D$")
            if m == "n_D":
                lines.append(r"\midrule")
            lines.append(f"{lab} & {cell(da)} & {cell(db)} & {fmt_p(t.p_holm)} & {fmt(t.r_rb)} \\\\")
        lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
        (T / "tab_alignment_model.tex").write_text("\n".join(lines))

    head = " & ".join(nar_ids)
    lines = [r"\begin{table*}[htbp]", r"\centering",
             r"\caption{Deviation by narrator reference and feature (mean $\pm$ SD over %d outputs per narrator). Tests: Friedman on video-level means (%d blocks), Holm-corrected; $W$: Kendall's coefficient of concordance.}" % (
                 len(dev) // len(nar_ids), dev.video_id.nunique()),
             r"\label{tab:alignment_narrator}", r"\small",
             r"\begin{tabular}{l" + "c" * len(nar_ids) + "cc}", r"\toprule",
             f"Feature & {head} & $\\chi^2_F(2)$ / $p_{{\\mathrm{{Holm}}}}$ & $W$ \\\\", r"\midrule"]
    for m in ms:
        t = tn[tn.measure == m].iloc[0]
        vals = []
        for n in nar_ids:
            d = desc[(desc.group == "narrator") & (desc.level == n) & (desc.measure == m)].iloc[0]
            vals.append(f"{fmt(d['mean'])} $\\pm$ {fmt(d['sd'])}")
        lab = mlabel[m].replace("D_nar (own reference)", r"$D^{\mathrm{nar}}$").replace("Overall D", r"Overall $D$")
        lines.append(f"{lab} & {' & '.join(vals)} & {fmt(t.chi2)} / {fmt_p(t.p_holm)} & {fmt(t.kendall_W)} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    (T / "tab_alignment_narrator.tex").write_text("\n".join(lines))

    lines = [r"\begin{table}[htbp]", r"\centering",
             r"\caption{Overall deviation $D$ by intended category (descriptive only). Values are median [min, max] over outputs; $n$ = videos (outputs).}",
             r"\label{tab:alignment_category}", r"\small",
             r"\begin{tabular}{lc" + "c" * len(engines) + "}", r"\toprule",
             "Category & $n$ & " + " & ".join(MODEL_LABEL.get(e, e) for e in engines) + r" \\", r"\midrule"]
    for c, g in cat_df.groupby("category", sort=False):
        nv, no = int(g.n_videos.iloc[0]), int(g.n_outputs.sum())
        vals = [f"{fmt(r['median'])} [{fmt(r['min'])}, {fmt(r['max'])}]" for _, r in g.set_index("engine").loc[engines].reset_index().iterrows()]
        lines.append(f"{cat_label(c)} & {nv} ({no}) & {' & '.join(vals)} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (T / "tab_alignment_category.tex").write_text("\n".join(lines))

    lines = [r"\begin{table}[htbp]", r"\centering",
             r"\caption{Inter-narrator consistency of the reference category profiles (ICC(2,$k$), two-way random, absolute agreement; 95\% CI from 5{,}000 bootstrap resamples of categories).}",
             r"\label{tab:reference_icc}", r"\small",
             r"\begin{tabular}{lccc}", r"\toprule", r"Feature & ICC(2,1) & ICC(2,$k$) & 95\% CI \\", r"\midrule"]
    nice = {**CORE_LABEL, "F0_sd": "F0 variability", "F0_range": "F0 range", "Loud_sd": "Loudness variability",
            "LoudPeaks": "Loudness peaks/s", "Unvoiced_sd": "SD unvoiced length"}
    for _, r in icc_df.iterrows():
        lines.append(f"{nice.get(r.feature, r.feature)} & {fmt(r.icc2_1)} & {fmt(r.icc2_k)} & [{fmt(r.ci_lo)}, {fmt(r.ci_hi)}] \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (T / "tab_reference_icc.tex").write_text("\n".join(lines))

    lines = [r"\begin{table}[htbp]", r"\centering", r"\caption{Design of the synthesis experiment.}",
             r"\label{tab:design}", r"\small", r"\begin{tabular}{p{2.6cm}p{4.4cm}}", r"\toprule",
             r"Factor & Levels \\", r"\midrule",
             f"Synthesis model & {', '.join(MODEL_LABEL.get(e, e) for e in engines)} ({len(engines)}) \\\\",
             r"Conditioning & Reference audio only (no prompt-based condition) \\",
             f"Video & {dev.video_id.nunique()} MSVD clips \\\\",
             f"Narrator reference & {', '.join(nar_ids)} ({len(nar_ids)}) \\\\",
             f"Intended categories & {dev.category.nunique()} of 16 \\\\",
             r"Text & Identical across models and narrators for each video \\", r"\midrule",
             f"Total outputs & ${len(engines)} \\times {dev.video_id.nunique()} \\times {len(nar_ids)} = {len(dev)}$ \\\\",
             r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (T / "tab_design.tex").write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Figures — minimalist card style (DM Sans)
# ---------------------------------------------------------------------------
INK = "#111111"
INK2 = "#555555"
GRID = "#cfcfcf"
CARD = "#f8f8f8"
CARD_EDGE = "#e7e7e7"
NAR_COL = ["#F07A1A", "#1F5E99", "#2A9D8F"]       # Woman01, Man01, Man02 (validated, CVD-safe)
NAR_MARK = ["o", "s", "^"]
HI_COL, LO_COL = "#F07A1A", "#1F5E99"
MODEL_COL = ["#1F5E99", "#F07A1A"]  # XTTS v2, Spanish-F5
PRIMARY = [("Joy", "extasis", "serenidad"), ("Anticipation", "vigilancia", "interes"),
           ("Trust", "admiracion", "aceptacion"), ("Disgust", "aversion", "aburrimiento"),
           ("Anger", "furia", "molestia"), ("Fear", "terror", "aprension"),
           ("Surprise", "asombro", "distraccion"), ("Sadness", "duelo", "pensamiento_profundo")]


def _style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    import glob
    fonts = []
    for d in [Path(__file__).parent / "fonts", Path.home() / "fonts", Path("/content/fonts")]:
        fonts += glob.glob(str(d / "DMSans*.ttf"))
    for f in fonts:
        try:
            fm.fontManager.addfont(f)
        except Exception:
            pass
    fam = None
    for f in fm.fontManager.ttflist:
        if f.name.startswith("DM Sans"):
            fam = f.name
            break
    if fam is None:
        print("DM Sans not found (put DMSans-400/500/700.ttf in ./fonts); using default sans-serif.")
    plt.rcParams.update({
        "font.family": fam or "sans-serif", "svg.fonttype": "none", "font.size": 9, "text.color": INK,
        "axes.facecolor": "none", "figure.facecolor": "white", "savefig.facecolor": "white",
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False, "axes.spines.bottom": False,
        "axes.grid": True, "grid.color": GRID, "grid.linestyle": (0, (1.5, 2.5)), "grid.linewidth": 0.6,
        "xtick.color": INK2, "ytick.color": INK2, "xtick.major.size": 0, "ytick.major.size": 0,
        "xtick.major.pad": 4, "ytick.major.pad": 4, "legend.frameon": False,
        "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlepad": 12, "axes.titlecolor": INK,
    })
    return plt


def _cards(fig, axes, pad=(0.52, 0.14, 0.62, 0.40)):
    """Rounded light card behind each axes. pad = (left, right, bottom, top) in inches."""
    from matplotlib.patches import FancyBboxPatch
    W, H = fig.get_size_inches()
    fig.canvas.draw()
    for ax in np.ravel(axes):
        if not ax.get_visible():
            continue
        b = ax.get_position()
        l, r, bo, t = pad
        x0, y0 = b.x0 - l / W, b.y0 - bo / H
        w, h = b.width + (l + r) / W, b.height + (bo + t) / H
        fig.patches.append(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                                          transform=fig.transFigure, facecolor=CARD, edgecolor=CARD_EDGE,
                                          linewidth=0.9, zorder=-10, mutation_aspect=W / H))


def _legend_bottom(fig, items, y=0.01, fontsize=11):
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    handles = []
    for label, color, kind in items:
        if kind == "patch":
            handles.append(Patch(facecolor=color, edgecolor=color, label=label))
        else:
            handles.append(Line2D([], [], marker=kind, color=color, linestyle="none", markersize=8, label=label))
    fig.legend(handles=handles, loc="lower center", ncol=len(items), bbox_to_anchor=(0.5, y),
               fontsize=fontsize, handlelength=1.1, handleheight=1.1, columnspacing=1.6, handletextpad=0.5)


def _save(fig, out, name):
    for ext in ("pdf", "png", "svg"):
        fig.savefig(out / "figures" / f"{name}.{ext}", dpi=300)
    svg = out / "figures" / f"{name}.svg"
    # Editable text: use the standard family name so Illustrator/Inkscape/Figma find DM Sans.
    svg.write_text(svg.read_text(encoding="utf-8").replace("'DM Sans 9pt'", "'DM Sans', sans-serif"), encoding="utf-8")
    plt_close(fig)


def plt_close(fig):
    import matplotlib.pyplot as plt
    plt.close(fig)


def _radar(ax, series, rmax=5):
    """series: list of (values[T,I,R,D], color, fill_alpha, lw, ls)."""
    ang = np.array([np.pi / 2, 0.0, 3 * np.pi / 2, np.pi])  # T top, I right, R bottom, D left
    ax.set_theta_offset(0)
    ax.set_theta_direction(1)
    ax.set_thetalim(0, 2 * np.pi)
    ax.set_autoscale_on(False)
    ax.set_ylim(0, rmax)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["1", "2", "3", "4", "5"], fontsize=7.5, color=INK2)
    ax.set_rlabel_position(45)
    ax.set_xticks(ang)
    ax.set_xticklabels(["T", "I", "R", "D"], fontsize=10, color=INK)
    ax.tick_params(axis="x", pad=2)
    ax.grid(True, color=GRID, linestyle=(0, (1.5, 2.5)), linewidth=0.6)
    ax.spines["polar"].set_visible(False)
    ax.set_facecolor("#f1f1f1")
    for vals, col, a, lw, ls in series:
        v = np.r_[vals, vals[:1]]
        t = np.r_[ang, ang[:1]]
        if a > 0:
            ax.fill(t, v, color=col, alpha=a, linewidth=0, zorder=2)
        ax.plot(t, v, color=col, linewidth=lw, linestyle=ls, zorder=3)
    ax.set_thetalim(0, 2 * np.pi)
    ax.set_ylim(0, rmax)


def make_figures(out, dev, vid_model, vid_nar, R, complete, engines, nar_ids):
    plt = _style()
    ms = [f"n_d_{k}" for k in KEYS] + ["n_D"]
    titles = [CORE_LABEL[k] for k in KEYS] + ["Overall D"]
    rng = np.random.default_rng(3)

    # --- A: model comparison (only when two engines exist)
    if len(engines) >= 2:
        fig, axes = plt.subplots(1, 5, figsize=(13, 3.6))
        fig.subplots_adjust(left=0.06, right=0.99, bottom=0.30, top=0.80, wspace=0.55)
        for ax, m, t in zip(axes, ms, titles):
            wide = vid_model.pivot(index="video_id", columns="engine", values=m)[engines]
            for _, r in wide.iterrows():
                ax.plot([0, 1], r.values, color="#c9c9c9", lw=0.9, zorder=1)
            for i, e in enumerate(engines):
                pts = dev.loc[dev.engine == e, m]
                ax.scatter(i + rng.uniform(-0.1, 0.1, len(pts)), pts, s=12, color=MODEL_COL[i], alpha=0.45, lw=0, zorder=2)
                ax.plot([i - 0.2, i + 0.2], [wide[e].median()] * 2, color=MODEL_COL[i], lw=2.6, solid_capstyle="round", zorder=3)
            ax.set_xticks([0, 1], [MODEL_LABEL.get(e, e) for e in engines], rotation=90, fontsize=9)
            ax.set_xlim(-0.5, 1.5); ax.grid(axis="x", visible=False); ax.set_title(t)
        axes[0].set_ylabel("|deviation| (normalized)")
        _cards(fig, axes, pad=(0.55, 0.12, 0.95, 0.45))
        _save(fig, out, "fig_deviation_by_model")

    # --- B: deviation by narrator (vertical labels); split by model when there are two
    multi = len(engines) > 1
    fig, axes = plt.subplots(1, 5, figsize=(13.5 if multi else 12.5, 4.3 if multi else 3.7))
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.36 if multi else 0.27, top=0.84, wspace=0.55)
    offs = [-0.2, 0.2] if multi else [0.0]
    for ax, m, t in zip(axes, ms, titles):
        for i, n in enumerate(nar_ids):
            for ei, e in enumerate(engines if multi else [None]):
                sel = (dev.narrator_id == n) & ((dev.engine == e) if e else True)
                d = dev.loc[sel, m].values
                if not len(d):
                    continue
                col = MODEL_COL[ei] if multi else NAR_COL[i % 3]
                x = i + offs[ei]
                q1, q2, q3 = np.percentile(d, [25, 50, 75])
                hw = 0.12 if multi else 0.24
                ax.plot([x, x], [q1, q3], color=col, lw=6 if multi else 7, alpha=0.22, solid_capstyle="round", zorder=1)
                ax.scatter(x + rng.uniform(-hw / 2, hw / 2, len(d)), d, s=13 if multi else 16, color=col,
                           marker=NAR_MARK[i % 3], lw=0, alpha=0.85, zorder=2)
                ax.plot([x - hw, x + hw], [q2, q2], color=INK, lw=1.8, solid_capstyle="round", zorder=3)
        ax.set_xticks(range(len(nar_ids)), nar_ids, rotation=90, fontsize=9)
        ax.set_xlim(-0.6, len(nar_ids) - 0.4)
        ax.grid(axis="x", visible=False)
        ax.set_title(t)
    axes[0].set_ylabel("|deviation| (normalized)")
    _cards(fig, axes, pad=(0.55, 0.12, 0.85, 0.45))
    if multi:
        _legend_bottom(fig, [(MODEL_LABEL.get(e, e), MODEL_COL[ei], "patch") for ei, e in enumerate(engines)], y=0.0, fontsize=10.5)
    _save(fig, out, "fig_deviation_by_narrator")

    # --- C: specificity
    fig, ax = plt.subplots(figsize=(4.4, 4.5))
    fig.subplots_adjust(left=0.17, right=0.95, bottom=0.22, top=0.86)
    lim = [0, max(dev.n_D.max(), dev.n_Dother.max()) * 1.06]
    ax.fill_between(lim, lim, [lim[1]] * 2, color="#1F5E99", alpha=0.06, lw=0, zorder=0)
    ax.plot(lim, lim, color=INK2, lw=0.9, ls=(0, (4, 3)), zorder=1)
    items = []
    for i, e in enumerate(engines):
        g = dev[dev.engine == e]
        ax.scatter(g.n_D, g.n_Dother, s=26, color=(MODEL_COL[i] if len(engines) > 1 else NAR_COL[0]), marker=NAR_MARK[i], lw=0, alpha=0.9, zorder=2)
        items.append((MODEL_LABEL.get(e, e), (MODEL_COL[i] if len(engines) > 1 else NAR_COL[0]), NAR_MARK[i]))
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("D to intended profile"); ax.set_ylabel("Mean D to non-intended profiles")
    ax.text(lim[1] * 0.05, lim[1] * 0.93, "closer to intended\ncategory", fontsize=8, color=INK2, va="top")
    ax.set_title("Category specificity")
    _cards(fig, [ax], pad=(0.62, 0.15, 0.55, 0.45))
    _legend_bottom(fig, items, y=0.0, fontsize=10)
    _save(fig, out, "fig_specificity")

    # --- D: reference corpus, raw units
    RR = R[R.category.isin(complete)]
    order = RR.groupby("category")["r_T"].mean().sort_values().index.tolist()
    fig, axes = plt.subplots(1, 4, figsize=(13, 6.0), sharey=True)
    fig.subplots_adjust(left=0.15, right=0.99, bottom=0.21, top=0.90, wspace=0.12)
    y = np.arange(len(order))
    for ax, k in zip(axes, KEYS):
        g = RR.groupby("category")[f"r_{k}"]
        mu, sd = g.mean().loc[order], g.std(ddof=1).loc[order]
        ax.hlines(y, mu - sd, mu + sd, color="#d0d0d0", lw=4, zorder=1, capstyle="round")
        for i, n in enumerate(nar_ids):
            sub = RR[RR.narrator_id == n].set_index("category")[f"r_{k}"].loc[order]
            ax.scatter(sub, y, s=20, color=NAR_COL[i % 3], marker=NAR_MARK[i % 3], lw=0, zorder=2)
        ax.scatter(mu, y, s=60, marker="|", color=INK, lw=1.6, zorder=3)
        ax.set_title(f"{CORE_LABEL[k]}", fontsize=11)
        ax.set_xlabel(CORE_UNIT[k])
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(y, [cat_label(c) for c in order], fontsize=8.5)
    _cards(fig, axes, pad=(0.1, 0.1, 0.55, 0.42))
    _legend_bottom(fig, [(n, NAR_COL[i % 3], NAR_MARK[i % 3]) for i, n in enumerate(nar_ids)] +
                   [("Mean ± SD", INK, "|")], y=0.0, fontsize=10.5)
    _save(fig, out, "fig_reference_profiles")


def radar_figures(out, long, complete, nar_ids, narrators, alias):
    plt = _style()
    R = long[long.source == "reference"]
    S = long[long.source == "synthesized"]
    ncols = [f"n_{k}" for k in ["T", "I", "R", "D"]]
    base = cat_key
    prof = R[R.category.isin(complete)].groupby("category")[ncols].mean()
    prof.index = [base(c) for c in prof.index]

    def panel_grid(nrow, ncol, w=3.4, h=3.6, bottom_in=0.75):
        Wt, Ht = ncol * w, nrow * h + bottom_in
        fig, axes = plt.subplots(nrow, ncol, figsize=(Wt, Ht), subplot_kw=dict(projection="polar"))
        fig.subplots_adjust(left=0.62 / Wt, right=1 - 0.62 / Wt, bottom=(bottom_in + 0.45) / Ht,
                            top=1 - 0.80 / Ht, wspace=1.24 / (w - 1.24), hspace=1.25 / (h - 1.25))
        return fig, np.ravel(axes)

    # 1) reference corpus: high vs low intensity per primary emotion (mean of narrators)
    fig, axes = panel_grid(2, 4)
    for ax, (name, hi, lo) in zip(axes, PRIMARY):
        _radar(ax, [(prof.loc[hi].values, HI_COL, 0.35, 1.1, "-"), (prof.loc[lo].values, LO_COL, 0.30, 1.1, "-")])
        ax.set_title(name, fontsize=14, pad=16)
    _cards(fig, axes, pad=(0.5, 0.5, 0.42, 0.66))
    _legend_bottom(fig, [("High intensity", HI_COL, "patch"), ("Low intensity", LO_COL, "patch")], y=0.012, fontsize=13)
    _save(fig, out, "fig_radar_reference_emotions")

    # 2) per narrator, all 16 categories (replaces EmocionesLocutores)
    for i, n in enumerate(narrators):
        Rn = R[R.narrator == n].copy()
        Rn["base"] = Rn.category.map(base)
        Rn = Rn.set_index("base")[ncols]
        fig, axes = panel_grid(2, 4)
        for ax, (name, hi, lo) in zip(axes, PRIMARY):
            _radar(ax, [(prof.loc[hi].values, "#9a9a9a", 0, 0.9, (0, (3, 2))),
                        (Rn.loc[hi].values, HI_COL, 0.35, 1.1, "-"), (Rn.loc[lo].values, LO_COL, 0.30, 1.1, "-")])
            ax.set_title(name, fontsize=14, pad=16)
        _cards(fig, axes, pad=(0.5, 0.5, 0.42, 0.66))
        _legend_bottom(fig, [("High intensity", HI_COL, "patch"), ("Low intensity", LO_COL, "patch"),
                             ("Group mean (high)", "#9a9a9a", "patch")], y=0.012, fontsize=12)
        _save(fig, out, f"fig_radar_reference_{alias(n)}")

    # 3) per video: target profile vs the three XTTS outputs (replaces Modelos_Evaluacion)
    vids = sorted(S.video_id.unique())
    ncol = 5
    nrow = int(np.ceil(len(vids) / ncol))
    for eng in sorted(S.engine.unique()):
        Se = S[S.engine == eng]
        fig, axes = panel_grid(nrow, ncol, w=3.2, h=3.7)
        for ax, v in zip(axes, vids):
            g = Se[Se.video_id == v]
            cat = base(g.category.iloc[0])
            series = [(prof.loc[cat].values, INK, 0.0, 1.2, (0, (3, 2)))]
            for j, n in enumerate(narrators):
                gn = g[g.narrator == n]
                if len(gn):
                    series.append((gn[ncols].values[0], NAR_COL[j % 3], 0.10, 1.2, "-"))
            _radar(ax, series)
            ax.set_title(f"{cat_label(cat)}\n{v}", fontsize=9.5, pad=14, linespacing=1.4)
        for ax in axes[len(vids):]:
            ax.set_visible(False)
        _cards(fig, axes, pad=(0.45, 0.45, 0.42, 0.78))
        _legend_bottom(fig, [("Target profile", INK, "patch")] +
                       [(alias(n), NAR_COL[j % 3], "patch") for j, n in enumerate(narrators)], y=0.012, fontsize=12)
        _save(fig, out, f"fig_radar_videos_{eng}")


# ---------------------------------------------------------------------------
# Auto-written text
# ---------------------------------------------------------------------------
def write_report(out, tm, tn, post, spec, icc_df, var_df, cat_df, nar_prof, engines, nar_ids, dev, complete, mm_ok):
    L = []
    nv = dev.video_id.nunique()
    L.append("# Resultados para el manuscrito (generado automáticamente)\n")
    L.append(f"Salidas analizadas: {len(dev)} | videos: {nv} | categorías usadas: {dev.category.nunique()} | "
             f"categorías completas en el corpus de referencia: {len(complete)}\n")
    L.append("Revise cada frase antes de pegarla. La redacción cambia automáticamente según la significancia.\n")

    if len(tm):
        a, b = engines
        t = tm[tm.measure == "n_D"].iloc[0]
        sig = t.p_holm < 0.05
        better = MODEL_LABEL.get(a, a) if t.med_diff < 0 else MODEL_LABEL.get(b, b)
        da, db = dev[dev.engine == a].n_D, dev[dev.engine == b].n_D
        txt = (f"The overall deviation was {da.mean():.2f} $\\pm$ {da.std(ddof=1):.2f} for {MODEL_LABEL.get(a, a)} and "
               f"{db.mean():.2f} $\\pm$ {db.std(ddof=1):.2f} for {MODEL_LABEL.get(b, b)} (median paired difference at video level "
               f"{t.med_diff:.2f}, 95\\% CI [{fmt(t.ci_lo)}, {fmt(t.ci_hi)}]; Wilcoxon $T={t.stat:.1f}$, $p_{{\\mathrm{{Holm}}}}{peq(t.p_holm)}$, "
               f"$r_{{rb}}={t.r_rb:.2f}$, $n={int(t.n)}$ videos). ")
        txt += (f"{better} showed lower deviation." if sig else
                "Within this sample, the two models could not be distinguished in overall alignment.")
        feats = tm[tm.measure.isin([f"n_d_{k}" for k in KEYS])]
        sigf = feats[feats.p_holm < 0.05]
        if len(sigf):
            txt += " At the feature level, significant model differences were found for " + ", ".join(
                f"{r.label} ($p_{{\\mathrm{{Holm}}}}{peq(r.p_holm)}$, $r_{{rb}}={r.r_rb:.2f}$)" for _, r in sigf.iterrows()) + "."
        else:
            txt += " No feature-level difference between models survived Holm correction."
        z = tm[tm.measure == "z_D"].iloc[0]
        txt += (f" The z-score sensitivity analysis yielded {'the same' if (z.p < 0.05) == sig else 'a different'} conclusion "
                f"($p{peq(z.p)}$).")
        L.append("## Comparación entre modelos\n\n" + txt + "\n")

    t = tn[tn.measure == "n_D"].iloc[0]
    txt = (f"The narrator reference {'had' if t.p_holm < 0.05 else 'did not have'} a significant effect on overall deviation "
           f"(Friedman $\\chi^2(2)={t.chi2:.2f}$, $p_{{\\mathrm{{Holm}}}}{peq(t.p_holm)}$, Kendall's $W={t.kendall_W:.2f}$, {int(t.n_blocks)} videos).")
    if t.p_holm < 0.05:
        txt += " Post-hoc comparisons: " + "; ".join(f"{r.pair}: $p_{{\\mathrm{{Holm}}}}{peq(r.p_holm)}$" for _, r in post.iterrows()) + "."
    L.append("## Efecto del narrador\n\n" + txt + "\n")

    txt = []
    for _, r in spec.iterrows():
        txt.append(f"{r.n_outputs_pos} of {r.n_outputs} {MODEL_LABEL.get(r.engine, r.engine)} outputs were closer to their intended "
                   f"category profile than to the non-intended profiles (median video-level $S={r.med_diff:.2f}$, 95\\% CI "
                   f"[{fmt(r.ci_lo)}, {fmt(r.ci_hi)}], $p_{{\\mathrm{{Holm}}}}{peq(r.p_holm)}$)")
    L.append("## Especificidad de categoría\n\n" + "; ".join(txt) + ".\n")

    core_icc = icc_df[icc_df.feature.isin(KEYS)]
    if len(core_icc):
        parts = [f"{CORE_LABEL[r.feature]}: ICC(2,$k$)$={r.icc2_k:.2f}$ [{fmt(r.ci_lo)}, {fmt(r.ci_hi)}]" for _, r in core_icc.iterrows()]
        L.append("## Consistencia entre narradores (corpus de referencia)\n\nInter-narrator consistency across the "
                 f"{len(complete)} categories was " + "; ".join(parts) + ".\n")
        L.append("Guía de interpretación (Koo & Li, 2016): <0.50 pobre, 0.50–0.75 moderada, 0.75–0.90 buena, >0.90 excelente.\n")

    parts = [f"{CORE_LABEL[r.feature]} ($\\chi^2({int(r.df)})={r.chi2:.1f}$, $p_{{\\mathrm{{Holm}}}}{peq(r.p_holm)}$, $W={r.kendall_W:.2f}$)"
             for _, r in var_df.iterrows()]
    L.append("## ¿Varían los descriptores entre categorías en el corpus humano?\n\nFriedman across categories, narrators as blocks: "
             + "; ".join(parts) + ". Con solo 3 bloques la potencia es baja; reporte W como tamaño de efecto.\n")

    L.append("## Perfiles por narrador (reemplaza 4.06, 1.87, 3.68, 2.37, 3.52)\n")
    L.append("| Narrador | " + " | ".join(CORE_LABEL[k] for k in KEYS) + " |")
    L.append("|---|" + "---|" * len(KEYS))
    for n in nar_prof.index:
        L.append(f"| {n} | " + " | ".join(f"{nar_prof.loc[n, (f'n_{k}', 'mean')]:.2f} ± {nar_prof.loc[n, (f'n_{k}', 'std')]:.2f}" for k in KEYS) + " |")
    L.append("")
    L.append("## Categorías\n")
    L.append("Solo descriptivo. Categorías con 1 video: reportar rango, no IC.\n")
    cols = ["label", "engine", "n_videos", "n_outputs", "median", "min", "max", "S_mean"]
    try:
        L.append(cat_df[cols].round(3).to_markdown(index=False))
    except ImportError:
        L.append("```\n" + cat_df[cols].round(3).to_string(index=False) + "\n```")
    L.append(f"\n\nModelo mixto: {'ver mixed_model.txt' if mm_ok else 'no convergió; ver mixed_model.txt'}.\n")
    (out / "RESULTADOS_MANUSCRITO.md").write_text("\n".join(L), encoding="utf-8")


TRK_LABEL = {"T": "Mean F0", "I": "Mean loudness", "R": "Voiced segments/s", "D": "Mean unvoiced length",
             "F0_sd": "F0 variability (CV)", "F0_range": "F0 range (20--80 pct.)"}
TRK_UNIT = {"T": "st", "I": "sone", "R": "seg/s", "D": "s", "F0_sd": "", "F0_range": "st"}


def write_tracking_table(out, trk, sens_df):
    T = out / "tables"
    engines = list(dict.fromkeys(trk.engine))
    multi = len(engines) > 1
    lines = [r"\begin{table*}[htbp]", r"\centering",
             r"\caption{Reference-to-output tracking: each synthesized output compared with the narrator recording used as its conditioning input (raw eGeMAPSv02 units; $n=%d$ outputs per model). $\rho$: Spearman correlation with 95\%% bootstrap CI; bias: median (output $-$ reference), Wilcoxon signed-rank; SD ratio: output SD / reference SD. $p$ values Holm-corrected across descriptors within each model.%s}" % (
                 int(trk.n.iloc[0]), r" $p_{\Delta\rho}$: Fisher $z$ test for the difference in $\rho$ between models (uncorrected)." if multi else ""),
             r"\label{tab:tracking}", r"\small",
             r"\begin{tabular}{l" + ("l" if multi else "") + "cccccc" + ("c" if multi else "") + "}", r"\toprule",
             "Descriptor & " + ("Model & " if multi else "") + r"Reference & Output & $\rho$ [95\% CI] & $p_{\mathrm{Holm}}$ & Bias ($p_{\mathrm{Holm}}$) & SD ratio" + (r" & $p_{\Delta\rho}$" if multi else "") + r" \\", r"\midrule"]
    for k in dict.fromkeys(trk.feature):
        rows = trk[trk.feature == k]
        u = TRK_UNIT[k]
        lab = TRK_LABEL[k] + (f" ({u})" if u else "")
        for j, (_, r) in enumerate(rows.iterrows()):
            first = lab if j == 0 else ""
            cells = [first] + ([MODEL_LABEL.get(r.engine, r.engine)] if multi else []) + [
                f"{fmt(r.ref_mean)} $\\pm$ {fmt(r.ref_sd)}", f"{fmt(r.syn_mean)} $\\pm$ {fmt(r.syn_sd)}",
                f"{fmt(r.rho)} [{fmt(r.rho_ci_lo)}, {fmt(r.rho_ci_hi)}]", fmt_p(r.p_rho_holm),
                f"{fmt(r.median_bias, 3)} ({fmt_p(r.p_bias_holm)})", fmt(r.sd_ratio)]
            if multi:
                cells.append(fmt_p(r.get("p_rho_diff")) if j == 0 else "")
            lines.append(" & ".join(cells) + r" \\")
        if multi:
            lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    (T / "tab_reference_tracking.tex").write_text("\n".join(lines))

    engs = list(dict.fromkeys(sens_df.engine))
    multi = len(engs) > 1
    lines = [r"\begin{table*}[htbp]" if multi else r"\begin{table}[htbp]", r"\centering",
             r"\caption{Sensitivity of the alignment results to the normalization scheme (mean $\pm$ SD over outputs; median [95\%% bootstrap CI]). The gain-invariant variant $z$-scores each descriptor within source and model before computing deviations.%s}" % (
                 r" $p$: Wilcoxon signed-rank test between models on video-level means." if multi else ""),
             r"\label{tab:sensitivity}", r"\small",
             r"\begin{tabular}{p{4.2cm}" + "c" * len(engs) + ("c" if multi else "") + "}", r"\toprule",
             "Measure & " + " & ".join(MODEL_LABEL.get(e, e) for e in engs) + (r" & $p$" if multi else "") + r" \\", r"\midrule"]
    for m in dict.fromkeys(sens_df.measure):
        rows = sens_df[sens_df.measure == m].set_index("engine")
        vals = [f"{fmt(rows.loc[e, 'mean'])} $\\pm$ {fmt(rows.loc[e, 'sd'])}; {fmt(rows.loc[e, 'median'])} [{fmt(rows.loc[e, 'ci_lo'])}, {fmt(rows.loc[e, 'ci_hi'])}]" for e in engs]
        extra = [fmt_p(rows["p_model_diff"].iloc[0]) if "p_model_diff" in rows and pd.notna(rows["p_model_diff"].iloc[0]) else "--"] if multi else []
        lines.append(f"{rows.label.iloc[0]} & " + " & ".join(vals + extra) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}" if multi else r"\end{table}"]
    (T / "tab_sensitivity.tex").write_text("\n".join(lines))


def tracking_figure(out, pairs, S, nar_ids, narrators, alias):
    plt = _style()
    engines = list(dict.fromkeys(e for e, _ in pairs))
    keys = list(dict.fromkeys(k for _, k in pairs))
    multi = len(engines) > 1
    fig, axes = plt.subplots(2, 3, figsize=(11, 8.2))
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.14, top=0.93, wspace=0.42, hspace=0.62)
    for ax, k in zip(axes.ravel(), keys):
        allv = np.concatenate([np.r_[pairs[(e, k)][0], pairs[(e, k)][1]] for e in engines])
        lo, hi = allv.min(), allv.max(); pad = (hi - lo) * 0.07
        ax.plot([lo - pad, hi + pad], [lo - pad, hi + pad], color=INK2, lw=0.9, ls=(0, (4, 3)), zorder=1)
        txt = []
        for ei, e in enumerate(engines):
            ref, syn, nar = pairs[(e, k)]
            for i, n in enumerate(narrators):
                m = nar == n
                col = MODEL_COL[ei] if multi else NAR_COL[i % 3]
                ax.scatter(ref[m], syn[m], s=24, color=col, marker=NAR_MARK[i % 3], lw=0, alpha=0.85, zorder=2)
            rho = stats.spearmanr(ref, syn)[0]
            txt.append((MODEL_LABEL.get(e, e) + "  " if multi else "") + "$\\rho$ = " + f"{rho:.2f}")
        for j, t in enumerate(txt):
            ax.text(0.04, 0.95 - j * 0.085, t, transform=ax.transAxes, fontsize=9.5, zorder=5,
                    color=(MODEL_COL[j] if multi else INK), va="top",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor=CARD, edgecolor="none", alpha=0.85))
        ax.set_title(TRK_LABEL[k].replace("--", "–"), fontsize=11.5)
        ax.set_xlim(lo - pad, hi + pad); ax.set_ylim(lo - pad, hi + pad)
        u = TRK_UNIT[k]
        ax.set_xlabel("Reference" + (f" [{u}]" if u else ""))
        ax.set_ylabel("Output" + (f" [{u}]" if u else ""))
    _cards(fig, axes, pad=(0.68, 0.15, 0.55, 0.42))
    if multi:
        items = [(MODEL_LABEL.get(e, e), MODEL_COL[ei], "patch") for ei, e in enumerate(engines)] + \
                [(alias(n), "#777777", NAR_MARK[i % 3]) for i, n in enumerate(narrators)]
    else:
        items = [(alias(n), NAR_COL[i % 3], NAR_MARK[i % 3]) for i, n in enumerate(narrators)]
    _legend_bottom(fig, items, y=0.0, fontsize=11)
    _save(fig, out, "fig_reference_tracking")


def append_tracking_report(out, trk, sens_df):
    L = ["\n## Seguimiento referencia → salida (cada salida vs. SU grabación condicionante)\n"]
    for e in dict.fromkeys(trk.engine):
        L.append(f"**{MODEL_LABEL.get(e, e)}**")
        for _, r in trk[trk.engine == e].iterrows():
            diff = f"; diferencia entre modelos p {peq(r.p_rho_diff)}" if "p_rho_diff" in r and pd.notna(r.get("p_rho_diff")) else ""
            L.append(f"- {TRK_LABEL[r.feature]}: ρ = {r.rho:.2f} [{fmt(r.rho_ci_lo)}, {fmt(r.rho_ci_hi)}], p_Holm {peq(r.p_rho_holm)}; "
                     f"sesgo mediano = {r.median_bias:.3f} (p_Holm {peq(r.p_bias_holm)}); razón de DE = {r.sd_ratio:.2f}{diff}")
        L.append("")
    L.append("## Sensibilidad a la normalización\n")
    for e in dict.fromkeys(sens_df.engine):
        L.append(f"**{MODEL_LABEL.get(e, e)}**")
        for _, r in sens_df[sens_df.engine == e].iterrows():
            extra = f"; {int(r.n_pos)}/{int(r.n)} > 0, Wilcoxon p {peq(r.p_wilcoxon)}" if pd.notna(r.get("n_pos")) else ""
            md = f"; modelos p {peq(r.p_model_diff)}" if pd.notna(r.get("p_model_diff")) else ""
            L.append(f"- {r.label}: {r['mean']:.2f} ± {r.sd:.2f}; mediana {r['median']:.2f} [{fmt(r.ci_lo)}, {fmt(r.ci_hi)}]{extra}{md}")
        L.append("")
    with open(out / "RESULTADOS_MANUSCRITO.md", "a", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
