"""Freeze candidates using the predeclared worst-split mean minus half SD rule."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data import ROOT
from scripts.evaluate_candidates import digest

GROUPS={'temporal':['temporal'],'heart':['heart_early','heart_late'],
        'embryo':['embryo_early','embryo_late'],'perturbation':['gata4_1','gata4_2']}


def main():
    destination=ROOT/'submissions/selection.json'
    if destination.exists():raise RuntimeError('Selection is already frozen')
    selected={}
    for group,experiments in GROUPS.items():
        results={}
        for name in experiments:
            directory=ROOT/'submissions/development'/name/'prediction_42'
            summary=json.loads((directory/'summary.json').read_text())
            record=json.loads((directory/'experiment.json').read_text())
            if summary['seeds']!=[0,1,2]:raise RuntimeError('Unexpected development seeds')
            for path,expected in record['source_hashes'].items():
                if digest(ROOT/'data/raw'/path)!=expected:raise RuntimeError(f'Source mismatch: {path}')
            for path,expected in record['code_hashes'].items():
                if digest(ROOT/path)!=expected:raise RuntimeError(f'Code mismatch: {path}')
            results[name]=summary['candidates']
        common=set.intersection(*(set(x) for x in results.values()))
        rank={c:min(r[c]['mean']-.5*r[c]['sd'] for r in results.values()) for c in common}
        candidate=sorted(common,key=lambda c:(-rank[c],c!='copy',c))[0]
        record=json.loads((ROOT/'submissions/development'/experiments[0]/'prediction_42/experiment.json').read_text())
        selected[group]=dict(candidate=candidate,config=record['candidates'][candidate],
            experiments=experiments,criterion=rank[candidate],candidate_criteria=rank,
            development=results,confirmation_seeds=[11,23,37],confirmation_prediction_seed=43)
        print(group,candidate,round(rank[candidate],3),flush=True)
    destination.write_text(json.dumps(selected,indent=2)+'\n')

if __name__=='__main__':main()
