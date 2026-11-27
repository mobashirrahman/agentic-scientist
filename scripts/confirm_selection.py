"""Confirm frozen model choices on fresh stochastic draws; never reranks candidates."""
import gc
import json
from pathlib import Path
import sys
import warnings
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from src.data import ROOT
from scripts.evaluate_candidates import build,EXPERIMENTS,digest
from vec_local_score.local_score import score_many


def main():
    name=sys.argv[1]
    selection=json.loads((ROOT/'submissions/selection.json').read_text())
    group=next(g for g,v in selection.items() if name in v['experiments'])
    choice=selection[group]['candidate']
    directory=ROOT/'submissions/development'/name/'prediction_43'
    directory.mkdir(parents=True,exist_ok=True)
    if not (directory/'experiment.json').exists():build(name,directory,43)
    record=json.loads((directory/'experiment.json').read_text())
    for path,expected in record['code_hashes'].items():
        if digest(ROOT/path)!=expected:raise RuntimeError('Code changed since build')
    candidates=list(dict.fromkeys(['copy',choice]))
    cache={}
    all_results=[]
    for seed in [11,23,37]:
        path=directory/f'confirmation_{seed}.json'
        if path.exists():rows=json.loads(path.read_text())
        else:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                result=score_many(EXPERIMENTS[name]['task'],[directory/f'{c}.h5ad' for c in candidates],
                    directory/'target.h5ad',directory/'reference.h5ad',setting=EXPERIMENTS[name].get('setting','heart'),
                    seed=seed,cache=cache)
            rows=dict(zip(candidates,result))
            path.write_text(json.dumps(rows,indent=2)+'\n')
        all_results.append(rows)
        print(name,seed,{c:r['task_score'] for c,r in rows.items()},flush=True)
    scores={c:[row[c]['task_score'] for row in all_results] for c in candidates}
    differences=np.array(scores[choice])-np.array(scores['copy'])
    result=dict(group=group,candidate=choice,seeds=[11,23,37],prediction_seed=43,
        scores=scores,differences=differences.tolist(),difference_mean=float(differences.mean()),
        selection_sha256=digest(ROOT/'submissions/selection.json'),
        code_sha256=digest(Path(__file__)),
        mean={c:float(np.mean(s)) for c,s in scores.items()},
        sd={c:float(np.std(s,ddof=1)) for c,s in scores.items()})
    (directory/'confirmation.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
