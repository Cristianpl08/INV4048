"""Acoustic evidence, not a perceptual score of accessibility or emotion."""
from pathlib import Path
import re
import numpy as np
import pandas as pd
from .contracts import emotion, write_json

FEATURES = {
    'loudness': 'loudness_sma3_amean',
    'pitch_st': 'F0semitoneFrom27.5Hz_sma3nz_amean',
    'voiced_rate': 'VoicedSegmentsPerSec',
    'unvoiced_s': 'MeanUnvoicedSegmentLength',
}
LABELS = {'loudness': 'Sonoridad (sone)', 'pitch_st': 'F0 (semitonos, ref. 27.5 Hz)',
          'voiced_rate': 'Segmentos sonoros/s (proxy de ritmo)',
          'unvoiced_s': 'Tramo no sonoro medio (s)'}


def legacy_records(root):
    root = Path(root)
    records = []
    for narrator in ['Andrea', 'Sergio', 'Sebastian']:
        for p in sorted((root/'Locutores'/narrator).glob('*.wav')):
            records.append({'path': str(p.resolve()), 'engine': 'reference', 'narrator': narrator,
                'emotion': emotion(re.sub(r'^\d+\s*', '', p.stem)), 'video_id': '', 'stage': 'reference'})
    for folder, stage in [('2. Output AD', 'legacy_output'), ('3. AD Final', 'legacy_final')]:
        for p in sorted((root/'Prueba 2 VDMS (XTTS)'/folder).glob('*.wav')):
            match = re.match(r'(.+)_(Andrea|Sergio|Sebastian)_(.+)$', p.stem)
            if not match:
                raise ValueError(f'Nombre de audio no reconocido: {p.name}')
            video, narrator, emo = match.groups()
            records.append({'path': str(p.resolve()), 'engine': 'xtts', 'narrator': narrator,
                            'emotion': emotion(emo), 'video_id': video, 'stage': stage})
    return records


def extract(records, output):
    import opensmile
    import soundfile as sf
    smile = opensmile.Smile(feature_set=opensmile.FeatureSet.eGeMAPSv02,
                           feature_level=opensmile.FeatureLevel.Functionals)
    rows, errors, full_rows = [], [], []
    for record in records:
        try:
            values = smile.process_file(record['path']).iloc[0]
            row = {**record, **{k: float(values[v]) for k, v in FEATURES.items()},
                   'audio_duration_s': sf.info(record['path']).duration}
            rows.append(row)
            full_rows.append({**record, **values.to_dict()})
        except Exception as exc:
            errors.append({'path': record['path'], 'error': str(exc)})
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out/'extraction_errors.json', errors)
    df = pd.DataFrame(rows)
    df.to_csv(out/'acoustic_raw.csv', index=False)
    pd.DataFrame(full_rows).to_csv(out/'egemaps_full.csv', index=False)
    if df.empty:
        raise ValueError('No se extrajo ninguna medida acústica. Revisa extraction_errors.json.')
    return df


def plots(df, output, stage='legacy_final'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from scipy.stats import spearmanr
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    features = list(FEATURES)
    ref = df[df.engine == 'reference'].copy()
    gen = df[(df.engine != 'reference') & (df.stage == stage)].copy()
    if gen.empty:
        raise ValueError(f'No hay datos de la etapa {stage}.')
    if ref.duplicated(['narrator', 'emotion']).any():
        raise ValueError('Referencias duplicadas: define una referencia por locutor/emoción.')
    joined = gen.merge(ref[['narrator', 'emotion', *features]], on=['narrator', 'emotion'],
                       how='left', suffixes=('', '_ref'), validate='many_to_one')
    joined.to_csv(out/'paired_reference.csv', index=False)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'figure.facecolor': '#ffffff'})
    palette = ['#247b91', '#de7a42', '#7564a5', '#418352']

    def save(fig, name):
        fig.tight_layout()
        for ext in ['png', 'svg', 'pdf']:
            fig.savefig(out/(name+'.'+ext), dpi=220, bbox_inches='tight')
        plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    for ax, feat in zip(axes.flat, features):
        for color, (narrator, group) in zip(palette, joined.groupby('narrator')):
            ax.scatter(group[feat+'_ref'], group[feat], c=color, label=narrator, s=45, alpha=.8)
        data = joined[[feat, feat+'_ref']].to_numpy()
        finite = data[np.isfinite(data)]
        if len(finite):
            low, high = finite.min(), finite.max()
            ax.plot([low, high], [low, high], '--', color='#999999', lw=1)
        ax.set(xlabel='Referencia · '+LABELS[feat], ylabel='Generado · '+LABELS[feat])
        ax.grid(alpha=.15)
    axes.flat[0].legend()
    fig.suptitle(f'Referencia vs. síntesis · {stage} · {len(gen)} audios', y=1.015)
    save(fig, '01_dispersion_referencia')

    fig, ax = plt.subplots(figsize=(9, 6))
    for color, (narrator, group) in zip(palette, gen.groupby('narrator')):
        ax.scatter(group.pitch_st, group.loudness, c=color, label=narrator, s=55)
    ax.set(xlabel=LABELS['pitch_st'], ylabel=LABELS['loudness'], title='Espacio acústico · cada punto es una AD')
    ax.legend(); ax.grid(alpha=.15)
    save(fig, '02_dispersion_tono_sonoridad')

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    groups = list(gen.groupby(['engine', 'narrator']))
    rng = np.random.default_rng(42)
    for ax, feat in zip(axes.flat, features):
        vals = [g[feat].dropna().values for _, g in groups]
        ax.boxplot(vals, tick_labels=[f'{k[0]}\n{k[1]}' for k, _ in groups], patch_artist=True,
                   boxprops={'facecolor': '#d8e8ed'}, showfliers=False)
        for i, v in enumerate(vals):
            ax.scatter(rng.normal(i+1, .035, len(v)), v, s=20, c=palette[i % len(palette)], alpha=.7)
        ax.set_ylabel(LABELS[feat]); ax.grid(axis='y', alpha=.15)
    save(fig, '03_distribuciones')

    corr = gen[features].corr(method='spearman')
    corr.to_csv(out/'spearman_descriptivo.csv')
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(corr, vmin=-1, vmax=1, cmap='RdBu_r')
    ax.set_xticks(range(4), features); ax.set_yticks(range(4), features)
    for i in range(4):
        for j in range(4): ax.text(j, i, f'{corr.iloc[i,j]:.2f}', ha='center', va='center')
    ax.set_title('Correlación de Spearman · descriptiva, sin prueba causal')
    fig.colorbar(im, ax=ax)
    save(fig, '04_correlaciones')

    # Shared scaling fitted ONLY on the reference corpus, not separately per model.
    calibration = {}
    normalized = gen.copy()
    for feat in features:
        mean, std = float(ref[feat].mean()), float(ref[feat].std(ddof=1))
        calibration[feat] = {'reference_mean': mean, 'reference_std': std}
        normalized[feat] = (gen[feat]-mean)/std if std > 0 else np.nan
    write_json(out/'reference_calibration.json', calibration)
    normalized.to_csv(out/'reference_zscores.csv', index=False)
    grouped = normalized.groupby(['engine', 'emotion'])[features].mean()
    fig, ax = plt.subplots(figsize=(10, max(4, len(grouped)*.6)))
    im = ax.imshow(grouped, cmap='RdBu_r', vmin=-3, vmax=3, aspect='auto')
    ax.set_xticks(range(4), features)
    ax.set_yticks(range(len(grouped)), [f'{a} · {b}' for a,b in grouped.index])
    ax.set_title('Perfil por emoción · z respecto al corpus de referencia')
    fig.colorbar(im, ax=ax, label='z (escala de color limitada a ±3)')
    save(fig, '05_perfiles_emocionales')

    # Cluster bootstrap by video: three narrators do not become three independent videos.
    summary = []
    for engine, group in joined.groupby('engine'):
        for feat in features:
            error = group.assign(error=(group[feat]-group[feat+'_ref']).abs()).groupby('video_id').error.mean().dropna()
            if len(error):
                draws = rng.choice(error.values, size=(2000, len(error)), replace=True).mean(axis=1)
                summary.append({'engine': engine, 'feature': feat, 'mae': float(error.mean()),
                                'ci_low': float(np.quantile(draws,.025)), 'ci_high': float(np.quantile(draws,.975)),
                                'n_videos': len(error), 'n_audio': len(group), 'bootstrap_unit': 'video'})
    pd.DataFrame(summary).to_csv(out/'reference_error_bootstrap.csv', index=False)
    gen.groupby(['engine','emotion','narrator'])[features].agg(['count','mean','std']).to_csv(out/'descriptive_summary.csv')

    comparison = {'status': 'pending', 'reason': 'Faltan dos motores en la misma etapa.'}
    models = sorted(gen.engine.unique())
    if len(models) == 2:
        keys = ['video_id', 'narrator', 'emotion']
        if 'text' in gen.columns:
            keys.append('text')
        left, right = [gen[gen.engine == m] for m in models]
        if left.duplicated(keys).any() or right.duplicated(keys).any():
            comparison = {'status': 'blocked', 'reason': 'Duplicados en claves de comparación; separar segmentos/repeticiones.'}
        else:
            pairs = left.merge(right, on=keys, suffixes=('_a','_b'), validate='one_to_one')
            pairs.to_csv(out/'model_pairs.csv', index=False)
            fig, axes = plt.subplots(2,2,figsize=(11,8))
            for ax, feat in zip(axes.flat, features):
                for _, row in pairs.iterrows():
                    ax.plot([0,1], [row[feat+'_a'],row[feat+'_b']], 'o-', alpha=.45, color=palette[0])
                ax.set_xticks([0,1], models); ax.set_ylabel(LABELS[feat]); ax.grid(alpha=.15)
            save(fig, '06_comparacion_modelos_pareada')
            comparison = {'status': 'available', 'models': models, 'n_pairs': len(pairs),
                          'unmatched': len(left)+len(right)-2*len(pairs)}
    write_json(out/'model_comparison_status.json', comparison)
    (out/'INTERPRETACION.md').write_text(
        '# Lectura de las figuras\n\n'
        f'Etapa: {stage}. Audios: {len(gen)}. Videos: {gen.video_id.nunique()}.\n\n'
        'Dispersión: cercanía a la diagonal indica similitud acústica, no emoción percibida. '
        'Los boxplots conservan cada observación. Las correlaciones son descriptivas. '
        'El bootstrap re-muestrea videos (2000 réplicas, semilla 42), promediando locutores dentro del video. '
        'Con 10 videos y emociones desbalanceadas la incertidumbre es considerable.\n\n'
        'VoicedSegmentsPerSec NO mide palabras/s; MeanUnvoicedSegmentLength NO es duración de la AD '
        'ni exclusivamente pausas lingüísticas. La sonoridad eGeMAPS no está en dB. '
        'Para evaluar transferencia emocional se necesitan pruebas perceptuales; para accesibilidad, usuarios BLV. '
        'No juntar Output AD y AD Final como observaciones independientes. '
        'Los valores normalizados históricos no se comparan con estas nuevas escalas.\n', encoding='utf-8')
    return comparison
