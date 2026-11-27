"""Gene embeddings in early-heart context from Geneformer-V2-104M (Apache-2.0, pretrained on unperturbed human
single-cell data; no knockout outcomes). Input: Qiu 2024 calibration cells (WT, <= E9.0, already vetted for T3's
expression prior). Mouse symbols -> human by uppercase symbol (one-to-one approximation). Output per mouse gene: mean
penultimate-layer embedding over the cells where the gene is in the top-4096 rank encoding, plus a cosine kNN table.

  PYTHONPATH=<pylib> .venv/bin/python -I scripts/gene_embeddings/geneformer_embed.py <model_dir> <out_dir>
"""
import pickle, sys, json
from pathlib import Path
import numpy as np, anndata as ad, scipy.sparse as sp, torch

class SafeUnpickler(pickle.Unpickler):          # plain containers only: no code execution from downloaded pickles
    OK = {('numpy.core.multiarray', 'scalar'), ('numpy._core.multiarray', 'scalar'), ('numpy', 'dtype')}
    def find_class(self, module, name):
        if (module, name) in self.OK:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f'blocked {module}.{name}')
def pload(p):
    with open(p, 'rb') as f:
        return SafeUnpickler(f).load()

MD, OUT = Path(sys.argv[1]), Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
QIU = Path('/scratch/user/virtual-embryo/data/external/qiu2024')
tok = pload(MD / 'geneformer/token_dictionary_gc104M.pkl')
name2id = pload(MD / 'geneformer/gene_name_id_dict_gc104M.pkl')
med = pload(MD / 'geneformer/gene_median_dictionary_gc104M.pkl')
rng = np.random.default_rng(0)
parts = []
for f, n in (('calibration_cardiomyocytes.h5ad', 2500), ('calibration_mesoderm.h5ad', 1500), ('calibration_endothelium.h5ad', 1000)):
    a = ad.read_h5ad(QIU / f)
    a = a[rng.choice(a.n_obs, min(n, a.n_obs), replace=False)]
    parts.append(a)
a = ad.concat(parts, merge='same')
mouse = list(a.var['feature_name'] if 'feature_name' in a.var else a.var_names)
cols, ens, msym = [], [], []
for j, g in enumerate(mouse):
    e = name2id.get(str(g).upper())
    if e in tok and e in med:
        cols.append(j); ens.append(e); msym.append(str(g))
print(f'{a.n_obs} cells; {len(cols)} of {len(mouse)} mouse genes mapped to Geneformer tokens', flush=True)
C = a.layers['counts'] if 'counts' in a.layers else a.X
C = sp.csr_matrix(C)[:, cols].astype(np.float32)
tot = np.asarray(sp.csr_matrix(a.layers['counts'] if 'counts' in a.layers else a.X).sum(1)).ravel()
medv = np.array([med[e] for e in ens], np.float32); tokv = np.array([tok[e] for e in ens])

from transformers import BertForMaskedLM
model = BertForMaskedLM.from_pretrained(MD / 'Geneformer-V2-104M', output_hidden_states=True).half().cuda().eval()
L = model.config.max_position_embeddings
cls, eos, pad = tok.get('<cls>'), tok.get('<eos>'), tok.get('<pad>', 0)
H = model.config.hidden_size
acc = np.zeros((len(cols), H), np.float64); cnt = np.zeros(len(cols))
B = 6
for s in range(0, C.shape[0], B):
    seqs, idxs = [], []
    for i in range(s, min(s + B, C.shape[0])):
        r = C[i]; v = r.data / max(tot[i], 1) * 1e4 / medv[r.indices]
        o = r.indices[np.argsort(-v, kind='stable')][: L - 2]
        seqs.append([cls] + tokv[o].tolist() + [eos]); idxs.append(o)
    m = max(map(len, seqs))
    ids = torch.tensor([q + [pad] * (m - len(q)) for q in seqs]).cuda()
    att = (ids != pad).long()
    with torch.no_grad():
        hs = model(input_ids=ids, attention_mask=att).hidden_states[-2].float().cpu().numpy()
    for k, o in enumerate(idxs):
        acc[o] += hs[k, 1:1 + len(o)]; cnt[o] += 1
    if s % 600 == 0:
        print(f'{s}/{C.shape[0]} cells', flush=True)
keep = cnt >= 5
E = (acc[keep] / cnt[keep, None]).astype(np.float32)
genes = [g for g, k in zip(msym, keep) if k]
np.save(OUT / 'embeddings.npy', E)
(OUT / 'genes.json').write_text(json.dumps(genes))
U = E - E.mean(0); U /= np.linalg.norm(U, axis=1, keepdims=True) + 1e-9
S = U @ U.T; np.fill_diagonal(S, -1)
nn = {g: [[genes[j], round(float(S[i, j]), 4)] for j in np.argsort(-S[i])[:50]] for i, g in enumerate(genes)}
(OUT / 'neighbors.json').write_text(json.dumps(nn))
print(f'wrote {len(genes)} gene embeddings ({H}-d)')
