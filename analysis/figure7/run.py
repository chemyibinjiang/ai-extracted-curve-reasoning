"""Reproduce Figure 7 from prepared observations without a template gate for PCA."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def validate_inputs():
    for row in json.loads((HERE/'input_manifest.json').read_text()):
        path = HERE/row['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError(f'Frozen input changed: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['replay', 'refit', 'cv', 'figures', 'validate', 'complete-window'])
    parser.add_argument('--output', type=Path, default=HERE.parents[1]/'build/figure7')
    args = parser.parse_args()
    validate_inputs()
    if args.mode == 'validate':
        print('All frozen input and reference hashes verified.')
        return
    out = args.output.resolve()
    if out == HERE or HERE in out.parents:
        raise ValueError('Write outputs outside the versioned Figure 7 module')
    result = out/'08_PARTIAL_PCA_CANDIDATE'
    result.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, FIGURE7_OUTPUT=str(out))

    def run(name, *options):
        subprocess.run([sys.executable, str(HERE/'lib'/name), *options], env=env, check=True)

    if args.mode == 'complete-window':
        run('complete_window.py')
        return

    if args.mode != 'figures':
        for name in ['01_build_cohort.py', '04_template_coverage.py', '05_template_shapes.py', 'composition.py', 'verify_matches.py']:
            run(name)
        if args.mode != 'cv':
            for name in ['SELECTED.json', 'CV_ERRORS.csv', 'CV_SUMMARY.csv']:
                shutil.copy2(HERE/'reference'/name, result/name)
        # Replay still refits the selected final model; only tuning is reused.
        run('17_partial_population.py', *([] if args.mode == 'cv' else ['--reuse-cv']))
        run('19_partial_diagnostics.py')
        run('20_observed_growth.py')
        run('verify_reference.py')
    run('18_partial_figures.py')
    print(f'Results: {out}')


if __name__ == '__main__':
    main()
