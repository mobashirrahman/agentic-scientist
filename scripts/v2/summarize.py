"""Collect completed experimental evidence without ranking confirmation against development."""
import json
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.data import ROOT

root=ROOT/'submissions/v2';runs=[];confirmations=[]
for path in sorted(root.glob('*/fit_*/summary.json')):
    experiment=path.parent/'experiment.json'
    if not experiment.exists():continue
    record=json.loads(experiment.read_text());summary=json.loads(path.read_text())
    entry=dict(experiment=path.parent.parent.name,run=path.parent.name,fit_seed=record['fit_seed'],
       prediction_seed=record['prediction_seed'],task=record['experiment']['task'],
       scoring_seeds=summary['seeds'],candidates=summary['candidates'],report=str(path.relative_to(ROOT)))
    (confirmations if entry['experiment'].startswith('confirmation_') else runs).append(entry)
comparisons=sum(len(r['scoring_seeds'])*len(r['candidates']) for r in runs)
status_path=root/'fleet_status.json'
observed=json.loads(status_path.read_text()) if status_path.exists() else []
live=[r['handle']['job'] for r in observed if r.get('status',{}).get('state')=='running' and r['status'].get('process_live') and r['status'].get('same_process')]
failed=[r['handle']['job'] for r in observed if r.get('status',{}).get('state')=='failed']
result=dict(completed_development_runs=len(runs),development_metric_evaluations=comparisons,
            completed_confirmation_runs=len(confirmations),observed_live_workers=live,failed_workers=failed,
            runs=runs,confirmations=confirmations)
(root/'results_summary.json').write_text(json.dumps(result,indent=2)+'\n')
text=['# Second-submission development: current evidence','',
      'All results below are local development comparisons with the first-submission model family on the same split. They are not official score forecasts.',
      '',f'Completed development runs: **{len(runs)}**; paired-model metric evaluations: **{comparisons}**.','',
      '| Experiment | Candidate | Fit/sample runs | Mean paired change | Range across run means |','|---|---|---:|---:|---:|']
grouped={}
for run in runs:
    for candidate,r in run['candidates'].items():
        if candidate=='first':continue
        key=(run['experiment'],candidate)
        grouped.setdefault(key,[]).append(r['paired_mean'])
for (experiment,candidate),values in sorted(grouped.items()):
    text.append(f'| {experiment} | {candidate} | {len(values)} | {np.mean(values):+.2f} | {min(values):+.2f} … {max(values):+.2f} |')
text+=['','## Frozen confirmation','',
 '| Experiment | Run | Candidate | Scoring draws | Mean paired change | Smallest draw gain |',
 '|---|---|---|---:|---:|---:|']
for run in confirmations:
    for candidate,r in run['candidates'].items():
        if candidate=='first':continue
        text.append(f"| {run['experiment']} | {run['run']} | {candidate} | {len(run['scoring_seeds'])} | {r['paired_mean']:+.2f} | {min(r['differences']):+.2f} |")
text+=['','## Interpretation','',
 '- T1 latent transport is the strongest replicated lead so far; its parameters were frozen separately before confirmation.',
 '- Ten-epoch T1 count decoders improved locally; fifty-epoch fits did not consistently transfer despite better reconstruction loss.',
 '- Registered/transported embryo coordinates improve modestly while preserving expression exactly. Single coherent templates underperformed.',
 '- Heart state, phenotype and observation-model gains must survive the later extrapolation split; earlier-stage improvements alone are insufficient.',
 '- Knockout programs and developmental delay are hypotheses. Gata4 evidence does not establish beta-catenin direction or effect magnitude.',
 '- Within-type complexity sampling improved both Gata4 replicates across three development sampling runs. Its strength is frozen at 0.5 for confirmation; genotype/batch transfer remains unvalidated.',
 '- More sampling draws improve Monte Carlo precision, not biological generalization. Selection over many families remains a source of optimism.',
 '- The private heart aggregation discrepancy remains unresolved. Public totals, raw metrics and a conservative shape-credit stress test are retained.',
 '- No second official attempt has been spent.','',
 '## Observed live remote workers','']
text += ['- '+job for job in live] or ['None at the last successful observation.']
if failed:text+=['','Failed workers: '+', '.join(failed)]
text+=['','Raw runs and full metric breakdowns are in `submissions/v2/`; snapshots and the frozen T1 confirmation plan are in `experiments/v2/`.']
(ROOT/'docs/SECOND_SUBMISSION_PROGRESS.md').write_text('\n'.join(text)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('runs','confirmations')},indent=2))
