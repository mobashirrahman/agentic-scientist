"""Fit response programs from released WT RNA stages; never read KO outcomes."""
import gc,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from src.data import ROOT,load_stage
from src.v2.programs import fit_program
from scripts.v2.evaluate import digest

paths=['T1/E8.5_RNA.h5ad','T1/E9.5_RNA.h5ad']
genes=(ROOT/'data/panels/T3__bcatenin.genes.txt').read_text().splitlines()
stages=[load_stage(p) for p in paths]
programs={};audit={}
for name in ['gata4','bcatenin']:
 beta,report=fit_program(stages,genes,name);programs[name]=beta;audit[name]=report
 print(name,report,flush=True)
np.savez_compressed(ROOT/'submissions/v2/wt_programs.npz',genes=np.array(genes),**programs)
audit.update(source_hashes={p:digest(ROOT/'data/raw'/p) for p in paths},
             code_hashes={p:digest(ROOT/p) for p in ['src/data.py','src/v2/transport.py','src/v2/programs.py','scripts/v2/fit_programs.py']},
             coefficients_sha256=digest(ROOT/'submissions/v2/wt_programs.npz'))
(ROOT/'submissions/v2/wt_programs.json').write_text(json.dumps(audit,indent=2)+'\n')
