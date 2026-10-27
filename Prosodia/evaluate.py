import argparse
from pathlib import Path
from emotivead.contracts import read_json
from emotivead.evaluation import extract, legacy_records, plots

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('reportes/acustica'))
    p.add_argument('--manifest', type=Path)
    p.add_argument('--stage', default='legacy_final')
    a = p.parse_args()
    records = legacy_records(a.root)
    if a.manifest:
        records = [r for r in records if r['engine']=='reference'] + read_json(a.manifest)
    df = extract(records, a.output)
    print(plots(df, a.output, a.stage))
