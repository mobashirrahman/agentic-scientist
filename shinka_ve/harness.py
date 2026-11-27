"""Frozen evaluation harness for the Virtual Embryo ShinkaEvolve task. NOT evolvable.

Contract for evolved programs (initial.py):
    predict(board, inputs, times, target_time, context) -> AnnData
      board       : 'temporal' | 'heart' | 'embryo' | 'perturbation'
      inputs      : list of released AnnData (log1p CP10k in .X; spatial in obsm['spatial_3D'] for T2/T3)
      times       : list of float stages for inputs (perturbation: WT stages)
      target_time : float stage to predict
      context     : dict(seed=int, n=3000, knockout=str, fit_seed=int, sampling=str|None, params=dict (tuned knob values
                    for this board, empty = use your defaults), dynamics=Dynamics|None,
                         external=AnnData|dict|None, external_spatial=AnnData|None)
    Must return 1000..MAX_CELLS[board] cells (T1 5118, heart 25179, embryo 5000, T3 7449) with every input gene (var_names),
    and obsm['spatial_3D'] for heart/embryo.

Leakage guard: targets are only loaded after predict() returns; program source is
statically screened for file/network/process access (see FORBIDDEN).
"""
from __future__ import annotations

import gc
import re
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy.sparse import issparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import load_stage  # noqa: E402

# Backtest splits. Each board's local score is the mean over its splits.
SPLITS = {
    # T1 temporal: officially unlocked P2 validation stage E10.5 (opt-in granted 2026-11-15).
    'temporal_val': dict(board='temporal', task='T1', inputs=['T1/E8.5_RNA.h5ad', 'T1/E9.5_RNA.h5ad'],
                         times=[8.5, 9.5], target='T1/E10.5_RNA.h5ad', time=10.5),
    # Heart extrapolation to the unlocked E10.5 heart stage (closest analogue of the E12.5 test).
    'heart_e105': dict(board='heart', task='T2', setting='heart',
                       inputs=['T2/E8.5.h5ad', 'T2/E8.75.h5ad', 'T2/E9.5.h5ad'],
                       times=[8.5, 8.75, 9.5], target='T2/E10.5.h5ad', time=10.5),
    'heart_early': dict(board='heart', task='T2', setting='heart', inputs=['T2/E8.25_late.h5ad', 'T2/E8.75.h5ad'],
                        times=[8.25, 8.75], target='T2/E9.5.h5ad', time=9.5),
    'heart_late': dict(board='heart', task='T2', setting='heart',
                       inputs=['T2/E8.25_late.h5ad', 'T2/E8.5.h5ad', 'T2/E8.75.h5ad'],
                       times=[8.25, 8.5, 8.75], target='T2/E9.5.h5ad', time=9.5),
    'embryo_early': dict(board='embryo', task='T2', setting='embryo', inputs=['T2/E6.75.h5ad', 'T2/E8.0.h5ad'],
                         times=[6.75, 8.0], target='T2/E7.25.h5ad', time=7.25),
    'embryo_late': dict(board='embryo', task='T2', setting='embryo', inputs=['T2/E7.25.h5ad', 'T2/E8.0.h5ad'],
                        times=[7.25, 8.0], target='T2/E7.5.h5ad', time=7.5),
    'gata4_1': dict(board='perturbation', task='T3', inputs=['T2/E8.0.h5ad', 'T2/E8.25_late.h5ad', 'T2/E8.5.h5ad', 'T2/E8.75.h5ad'],
                    times=[8.0, 8.25, 8.5, 8.75], target='T3/E8.75_gata4_ko_1.h5ad', time=8.75, knockout='Gata4'),
    'gata4_2': dict(board='perturbation', task='T3', inputs=['T2/E8.0.h5ad', 'T2/E8.25_late.h5ad', 'T2/E8.5.h5ad', 'T2/E8.75.h5ad'],
                    times=[8.0, 8.25, 8.5, 8.75], target='T3/E8.75_gata4_ko_2.h5ad', time=8.75, knockout='Gata4'),
}
# Board weights in the official total: T1 and T3 full, each T2 board half.
WEIGHTS = {'temporal': 1.0, 'perturbation': 1.0, 'heart': 0.5, 'embryo': 0.5}

FORBIDDEN = [r'read_h5ad', r'\bopen\s*\(', r'data/raw', r'\bos\.', r'subprocess', r'\bglob\b',
             r'pathlib', r'\bPath\s*\(', r'__import__', r'importlib', r'\beval\s*\(', r'\bexec\s*\(',
             r'requests', r'urllib', r'socket', r'shutil', r'pickle', r'h5py', r'\.env\b', r've_api',
             r'E10\.5_RNA', r'gata4_ko', r'target\.h5ad', r'\.h5ad']


def screen(source: str) -> str | None:
    for pattern in FORBIDDEN:
        if re.search(pattern, source):
            return f'Forbidden pattern in program: {pattern}'
    return None


EXTERNAL = {'temporal': 'data/external/qiu2024', 'heart': 'data/external/heart_anchor',
            'embryo': 'data/external/embryo_anchor', 'perturbation': 'data/external/go_prior'}
# Spatial late anchors (obsm['spatial'], 2D sections), passed separately as context['external_spatial'].
EXTERNAL_SPATIAL = {'heart': 'data/external/heart_spatial'}
_GO = None


_EXPR_PRIOR = None


def expression_prior():
    """pandas DataFrame, one row per gene (~53k, whole transcriptome): frac_all / mean_all (fraction of cells with
    >= 1 count; mean log1p CP10k) over wild-type Qiu 2024 Theiler stage 12-13 cells (~E8.0-E9.0), plus
    'frac:<cell type>' / 'mean:<cell type>' per Qiu cell type. Built by scripts/build_expression_prior.py."""
    global _EXPR_PRIOR
    if _EXPR_PRIOR is None:
        import json
        import numpy as np
        import pandas as pd
        d = ROOT / 'data/external/expression_prior'
        man = json.loads((d / 'manifest.json').read_text())
        assert not man.get('perturbation'), 'expression prior must be wild type'
        z = np.load(d / 'expression_prior.npz', allow_pickle=False)
        cols = {'frac_all': z['frac_all'], 'mean_all': z['mean_all']}
        for i, t in enumerate(z['types']):
            cols[f'frac:{t}'] = z['frac_type'][i].astype(np.float32)
            cols[f'mean:{t}'] = z['mean_type'][i].astype(np.float32)
        _EXPR_PRIOR = pd.DataFrame(cols, index=pd.Index(z['genes'].astype(str), name='gene'))
    return _EXPR_PRIOR.copy()


def external_board(board, genes):
    """Rule-vetted external data for a board, mapped onto `genes` (None when the board has none).
    T1: Qiu 2024 TS12/13 calibration + TS23 anchor. Heart: late-stage heart anchors listed in
    data/external/heart_anchor/manifest.json (every stage must be <= E9.5 or > E13.5; no Gata4/Ctnnb1 perturbations)."""
    if board == 'perturbation':
        return go_prior()
    d = ROOT / EXTERNAL.get(board, '__none__')
    files = sorted(d.glob('*.h5ad')) if board in EXTERNAL else []
    if not files:
        return None
    if board == 'temporal':
        from src.v2.anchor import load_external
        return load_external(files, genes)
    return load_anchor(d, files, genes, board)


# Stages (embryonic days) that external data may NOT come from, per board (Rules section 10).
# Global window (E9.5, E13.5]; heart also holds out E8.5 and the open bracket (E8.25, E8.75).
FORBIDDEN_DAYS = {
    'heart': lambda x: (9.5 < x <= 13.5) or (8.25 < x < 8.75),
    'temporal': lambda x: 9.5 < x <= 13.5,
    'embryo': lambda x: (9.5 < x <= 13.5) or (7.25 < x < 8.0),
}


FEULNER = 'feulner2024_heart_E14.5-E18.5.h5ad'


def load_anchor(d, files, genes, board='heart', *, feulner_days=(14.5, 16.5)):
    """Per-cell stage check: every cell must carry obs['stage_days'] (embryonic days from the source's own
    per-embryo metadata), none in the board's forbidden set, and no file may be a perturbation."""
    import json
    import anndata as ad
    import numpy as np
    from scipy import sparse
    man = json.loads((d / 'manifest.json').read_text())
    bad_day = FORBIDDEN_DAYS[board]
    parts = []
    for p in files:
        meta = man['files'][p.name]
        assert not meta.get('perturbation'), f'perturbed sample in {p.name}'
        a = ad.read_h5ad(p)
        assert 'stage_days' in a.obs, f'{p.name}: obs["stage_days"] (per-cell embryonic day) is required'
        days = np.asarray(a.obs['stage_days'], dtype=float)
        assert np.isfinite(days).all(), f'{p.name}: missing stage_days'
        bad = sorted({float(x) for x in days if bad_day(float(x))})
        assert not bad, f'{p.name}: cells at forbidden stages for {board}: {bad}'
        assert set(np.unique(days)) <= {float(x) for x in meta['stages_days']}, f'{p.name}: stages differ from manifest'
        available = set(a.var_names)
        shared = [g for g in genes if g in available]
        rows = np.isin(days, feulner_days) if p.name == FEULNER else slice(None)
        b = a[rows, shared].copy()
        if meta.get('values') == 'counts':  # log-normalise on the shared panel genes, like the released data
            x = sparse.csr_matrix(b.X, dtype=np.float32)
            lib = np.asarray(x.sum(1)).ravel()
            x = sparse.diags(1e4 / np.maximum(lib, 1)) @ x
            x.data = np.log1p(x.data)
            b.X = x.tocsr()
        b.obs['anchor_source'] = p.stem
        parts.append(b)
    out = ad.concat(parts, join='outer', fill_value=0)
    return out[:, [g for g in genes if g in set(out.var_names)]].copy()


def sampling_for(split):
    """Organiser-published sampling protocol of the split's TARGET (public metadata, not target data).
    T1: 'heart_with_surroundings' (E8.5-E10.5 dissections) or 'heart_chambers' (E12.5 test, heart-only dev split)."""
    spec = SPLITS[split]
    if spec.get('sampling'):
        return spec['sampling']
    return 'heart_with_surroundings' if spec['board'] in ('temporal', 'heart') else None


# T2 heart: which cell-type labels belong to the dissected heart (chambers, endocardium, epicardium, cushions).
# A pattern rule rather than a list, because held-out stages may carry labels unseen in the released ones.
# Uncertain labels (pericardium 'Peri', neural crest, 'Unknown', great-artery endothelium) are left out of the target.
_T2_CARDIAC = re.compile(r'(^|[-_ ])CM$|^Endo$|Chamber-Endo|Cush|EndoMT|Proepi|Epicard|^Epi$|^DMP$|^JCF$|Valve|Cardio|'
                         r'Myocard|Endocard|Atri|Ventric', re.I)


def t2_cardiac(labels):
    """Boolean mask: heart-chamber cell types among T2 heart labels (see _T2_CARDIAC)."""
    return np.array([bool(_T2_CARDIAC.search(str(x))) for x in labels])


def t2_region(stage, k=25, frac=0.5):
    """Spatial heart region of a section: cells whose k nearest spatial neighbours are mostly heart cell types
    (t2_cardiac). Keeps blood, endothelium and every other cell type lying inside the heart, like a dissection."""
    from sklearn.neighbors import NearestNeighbors
    card = t2_cardiac(stage.obs['celltype'].astype(str))
    xyz = np.asarray(stage.obsm['spatial_3D'], dtype=float)
    idx = NearestNeighbors(n_neighbors=min(k, len(xyz))).fit(xyz).kneighbors(xyz, return_distance=False)
    return card[idx].mean(axis=1) >= frac


def go_prior():
    """T3 gene-annotation prior (Gene Ontology, mutant/expression evidence and Ctnnb1/Gata4-referencing annotations
    removed; see scripts/v2/prepare_go_prior.py). Dict: gene_terms {symbol: [GO ids]}, term_names, term_parents."""
    global _GO
    p = ROOT / 'data/external/go_prior/go_prior.json'
    if _GO is None and p.exists():
        import json
        _GO = json.loads(p.read_text())
        assert set(_GO['dropped_evidence']) >= {'IMP', 'IGI', 'IEP'}, 'GO prior built without the evidence filter'
    return _GO


_GE = None
_COEXPR = None


def coexpr_prior():
    """T3 signed WT gene-to-panel co-expression prior built strictly from Qiu 2024 Theiler 12-13 WT calibration cells
    (<= E9.0, zero mutant data; scripts/build_coexpr_prior.py).
    Dict: genes [~53k mouse symbols], panel [~494 MERFISH panel genes], corr_all (n_genes x n_panel float32 global
    WT Pearson correlation), corr_within (n_genes x n_panel float32 within-lineage centered WT correlation).
    None if absent."""
    global _COEXPR
    d = ROOT / 'data/external/coexpr_prior'
    if _COEXPR is None and (d / 'coexpr_prior.npz').exists():
        import json
        man = json.loads((d / 'manifest.json').read_text())
        assert not man.get('perturbation'), 'coexpr prior must be wild type'
        z = np.load(d / 'coexpr_prior.npz', allow_pickle=False)
        genes = [str(g) for g in z['genes']]
        _COEXPR = dict(genes=genes, gene_index={g: i for i, g in enumerate(genes)},
                       panel=[str(g) for g in z['panel']],
                       corr_all=z['corr_all'].astype(np.float32),
                       corr_within=z['corr_within'].astype(np.float32))
    return _COEXPR


def gene_embeddings():
    """T3 gene-similarity prior: Geneformer-V2-104M (Apache-2.0; pretrained on unperturbed human single cells, no
    knockout outcomes) penultimate-layer gene embeddings averaged over vetted WT Qiu 2024 calibration cells (<= E9.0:
    cardiomyocytes, mesoderm, endothelium). Built by scripts/gene_embeddings/geneformer_embed.py on the head-node GPU.
    Dict: genes [mouse symbols], emb (n x 768 float32, row i = genes[i]), neighbors {gene: [[gene, cosine], ...] top 50}.
    None if absent."""
    global _GE
    d = ROOT / 'data/external/gene_embeddings'
    if _GE is None and (d / 'embeddings.npy').exists():
        import json
        _GE = dict(genes=json.loads((d / 'genes.json').read_text()), emb=np.load(d / 'embeddings.npy'),
                   neighbors=json.loads((d / 'neighbors.json').read_text()))
    return _GE


def external_spatial_board(board, genes):
    """Rule-vetted spatial anchors for a board (None if none): same per-cell stage checks as load_anchor."""
    d = ROOT / EXTERNAL_SPATIAL.get(board, '__none__')
    files = sorted(d.glob('*.h5ad')) if board in EXTERNAL_SPATIAL else []
    return load_anchor(d, files, genes, board) if files else None


# Off: in validation (2026-11-17) pushing cells along the learned field moved them FURTHER from the dev targets on
# heart, embryo and T1, and T1 training took ~9 min. Kept for a later fix; programs receive dynamics=None.
DYNAMICS_ENABLED = False


def external_context(board, genes, inputs=None, times=None):
    """Every external input a program receives; shared by run_split and the test export.
    dynamics: learned velocity field (shinka_ve/dynamics.py) trained on the split's own inputs + vetted external data."""
    ctx = dict(external=external_board(board, genes), external_spatial=external_spatial_board(board, genes))
    if board == 'perturbation':  # whole-transcriptome breadth + embeddings + WT co-expression (test Ctnnb1 is off-panel)
        ctx['expression_prior'] = expression_prior()
        ctx['gene_embeddings'] = gene_embeddings()
        ctx['coexpr_prior'] = coexpr_prior()
    ctx['dynamics'] = None
    if DYNAMICS_ENABLED and inputs is not None:
        from shinka_ve.dynamics import dynamics_for
        ctx['dynamics'] = dynamics_for(board, inputs, list(times), ctx['external'])
    return ctx


def external_for(split):
    """External data passed to the program as context['external'] (same for dev, holdout and test export)."""
    board = SPLITS[split]['board']
    if board not in EXTERNAL:
        return None
    genes = list(load_stage(SPLITS[split]['inputs'][-1]).var_names)
    return external_board(board, genes)


# T3 dev/holdout knockouts are scored like the test knockout: the test gene (Ctnnb1) is NOT on the 500-gene panel, so
# for every T3 split the knocked-out gene is removed from the inputs, the prediction and the scored truth. A program
# can then only gain on dev with code that works for an off-panel gene (expression prior, lineage structure), never
# by reading or zeroing the gene's own transcript.
MASK_KNOCKOUT = True


def run_split(module, split: str, seed: int, fit_seed: int = 0, params=None):
    spec = SPLITS[split]
    inputs = [load_stage(p) for p in spec['inputs']]
    if spec['board'] == 'embryo':
        genes = inputs[0].var_names[inputs[0].var_names.isin(inputs[1].var_names)]
        inputs = [a[:, genes].copy() for a in inputs]
    if spec['board'] == 'perturbation' and MASK_KNOCKOUT and spec.get('knockout'):
        keep = [g for g in inputs[-1].var_names if g != spec['knockout']]
        inputs = [a[:, [g for g in a.var_names if g != spec['knockout']]].copy() for a in inputs]
        assert list(inputs[-1].var_names) == keep
    genes = list(inputs[-1].var_names)
    # Official floor (copy_last): the preceding stage. On the embryo interpolation board that is the EARLIER bracket
    # (the site: "the stage it copies is roughly 5.5x too small by volume"); elsewhere the last input.
    reference = (inputs[0] if spec['board'] == 'embryo' else inputs[-1]).copy()
    context = dict(seed=seed, fit_seed=fit_seed, n=3000, knockout=spec.get('knockout'),
                   sampling=sampling_for(split), params=dict((params or {}).get(spec['board'], {})),
                   **external_context(spec['board'], genes, inputs, spec['times']))
    pred = module.predict(spec['board'], [a.copy() for a in inputs], list(spec['times']), spec['time'], context)
    del inputs, context
    gc.collect()
    check(pred, spec, genes)
    pred = pred[:, genes].copy()
    return pred, reference


# Official per-board cell limits (data/panels/index.json, the tighter of the validation and test boards): a program
# that exceeds them on dev would fail the official format check on the test.
MAX_CELLS = {'temporal': 5118, 'heart': 25179, 'embryo': 5000, 'perturbation': 7449}


def check(pred, spec, genes):
    hi = MAX_CELLS.get(spec.get('board'), 20000)
    if pred.n_obs < 1000 or pred.n_obs > hi:
        raise ValueError(f"prediction must have 1000-{hi} cells on the {spec.get('board')} board "
                         f'(official limit), got {pred.n_obs}')
    if set(genes) - set(pred.var_names):
        raise ValueError('prediction is missing genes from the input gene order')
    x = pred.X.tocsr().data if issparse(pred.X) else np.asarray(pred.X)
    if not np.all(np.isfinite(x)) or (x < 0).any():
        raise ValueError('expression must be finite and non-negative (log1p CP10k)')
    if spec['board'] in ('heart', 'embryo', 'perturbation'):
        p = pred.obsm.get('spatial_3D')
        if p is None or np.asarray(p).shape != (pred.n_obs, 3) or not np.all(np.isfinite(p)):
            raise ValueError('spatial_3D (n, 3) required for heart, embryo, and perturbation')


def severity_diag(pred, reference, split: str):
    """T3 response-size diagnostic on ALL cells (no subsample): the scorer's severity_slope (log beta, R^2) and the
    response-magnitude ratio. severity scores exactly 50 unless beta > 0 and R^2 > 0.01 on the truth's DE genes."""
    from common import core_metrics as cm
    spec = SPLITS[split]
    genes = list(reference.var_names)
    target = load_stage(spec['target'])[:, genes]
    dense = lambda a: np.asarray(a.X.toarray() if hasattr(a.X, 'toarray') else a.X, dtype=np.float32)
    P, T, R = dense(pred[:, genes]), dense(target), dense(reference)
    logb, r2 = cm.severity_slope(P, T, R)
    dp, dt = cm.pseudobulk(P) - cm.pseudobulk(R), cm.pseudobulk(T) - cm.pseudobulk(R)
    return dict(log_beta=float(logb), r2=float(r2), beta=float(np.exp(logb)),
                gate_open=bool(np.isfinite(logb) and logb > cm.SEVERITY_LOG_WORST + 1e-6),
                magnitude_ratio=float(np.linalg.norm(dp) / max(np.linalg.norm(dt), 1e-12)))


SHAPE = ('d2_shape', 'occupancy_dice', 'scale_log_ratio')


def t2_gated(rows):
    """Official T2 headline: shape credit is multiplied by min(1, neighbourhood skill / 50) (the site's "structure
    gate"). Reproduces all 280 heart and embryo test headlines of the 2026-11-18 leaderboard within 1e-4."""
    nb = next((100 * r['skill'] for r in rows if r['metric'] == 'neighborhood_mmd'), 0.0)
    g = min(1.0, max(nb, 0.0) / 50.0)
    return float(sum(r['points'] * (g if r['metric'] in SHAPE else 1.0) for r in rows))


def score_arrays(pred, target, reference, task, setting, scoring_seeds):
    from vec_local_score.local_score import PSEUDO_SPLIT_MARKER, score_many
    # score_many accepts preloaded stages keyed by absolute path. These are cache
    # identifiers only, so a worker exiting mid-score cannot strand a plaintext file.
    stages = {'prediction': pred, 'target': target, 'reference': reference}
    if any(PSEUDO_SPLIT_MARKER in stage.uns for stage in stages.values()):
        raise ValueError('scoring requires raw stages, not pseudo-split exports')
    cache = {str(Path('/agentic_scientist-memory') / key): stage for key, stage in stages.items()}
    rows = []
    for s in scoring_seeds:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            rows.extend(score_many(task, ['/agentic_scientist-memory/prediction'], '/agentic_scientist-memory/target',
                                   '/agentic_scientist-memory/reference', setting=setting,
                                   seed=s, cache=cache))
    return rows


def score_split(pred, reference, split: str, scoring_seeds):
    spec = SPLITS[split]
    target = load_stage(spec['target'])[:, list(reference.var_names)].copy()
    if spec.get('target_types'):  # protocol-matched target (e.g. heart chambers only), from the T1 cell-type map
        target = target[target.obs['celltype'].astype(str).isin(spec['target_types'])].copy()
    if spec.get('target_match') == 't1_lineage':
        # Composition-matched target (2026-11-25). The released T1 stages are different dissections, so the coarse
        # lineage shares jump between stages for sampling reasons; a Dev target that keeps that jump rewards
        # continuing it (TEST: the continued trend left 6% cardiomyocytes and scored mmd_u 66). The target is
        # therefore subsampled so its myocardium / endocardium / other shares equal the last input's (same cell
        # types): the split scores WHICH cells and expression states are forecast inside each lineage.
        def _lin(labels):
            out = []
            for x in labels:
                low = str(x).lower()
                out.append(0 if (low.endswith('-cm') or 'cardiomyocyte' in low) else
                           1 if (low.startswith(('endocard', 'endotheli', 'endomt')) or low.endswith(' vic')) else 2)
            return np.array(out)
        ref_labels = reference.obs['celltype'].astype(str)
        if spec.get('target_types'):
            ref_labels = ref_labels[ref_labels.isin(spec['target_types'])]
        share = np.bincount(_lin(ref_labels), minlength=3) / max(len(ref_labels), 1)
        tl = _lin(target.obs['celltype'].astype(str))
        have = np.bincount(tl, minlength=3)
        total = min(have[k] / share[k] for k in range(3) if share[k] > 0)
        rng_m = np.random.default_rng(0)
        keep = np.concatenate([rng_m.choice(np.flatnonzero(tl == k), int(total * share[k]), replace=False)
                               for k in range(3) if share[k] > 0 and int(total * share[k]) > 0])
        print(f"[{split}] lineage-matched target: kept {len(keep)}/{target.n_obs} cells, shares {np.round(share, 3)}", file=sys.stderr)
        target = target[np.sort(keep)].copy()
    if spec.get('target_filter') == 't2_cardiac':  # heart chambers only, like the E12.5 test dissection
        keep = t2_cardiac(target.obs['celltype'].astype(str))
        print(f"[{split}] heart-chambers target: kept {keep.sum()}/{len(keep)} cells, labels "
              f"{sorted(set(target.obs['celltype'].astype(str)[keep]))}", file=sys.stderr)
        target = target[keep].copy()
    if spec.get('target_filter') == 't2_region':  # dissected heart = the spatial heart REGION (all cell types inside it)
        keep = t2_region(target)
        print(f"[{split}] heart-region target: kept {keep.sum()}/{len(keep)} cells", file=sys.stderr)
        target = target[keep].copy()
    if spec.get('target_filter') == 't2_organ':
        labels = target.obs['celltype'].astype(str)
        resident = labels.str.contains(r'^Peri$|^BEC$|Early-VEC|Great Artery Endoth|Intra-Endoth', case=False)
        # 2026-11-25: a dissection keeps resident vessel/pericardial cells only where they are attached to the
        # heart (>= 10% of their 25 spatial neighbours are heart cell types); 'Epi' (E10.5 epicardium) is cardiac.
        card = t2_cardiac(labels)
        from sklearn.neighbors import NearestNeighbors
        xyz = np.asarray(target.obsm['spatial_3D'], dtype=float)
        nn = NearestNeighbors(n_neighbors=min(25, len(xyz))).fit(xyz).kneighbors(xyz, return_distance=False)
        attached = card[nn].mean(axis=1) >= 0.1
        target = target[card | (resident.to_numpy() & attached)].copy()
    rows = score_arrays(pred, target, reference, spec['task'], spec.get('setting', 'heart'), scoring_seeds)
    if spec['task'] == 'T2':  # official structure gate, applied per scoring seed before averaging
        for r in rows:
            r['task_score'] = t2_gated(r['rows'])
            if spec.get('score_mode') == 'no_shape':  # expression + neighbourhood metrics only, same weights
                kept = [x for x in r['rows'] if x['metric'] not in SHAPE]
                r['task_score'] = float(sum(x['points'] for x in kept) / max(sum(x['weight'] for x in kept), 1e-12))
    score = float(np.mean([r['task_score'] for r in rows]))
    metrics = {}
    for r in rows:
        for row in r.get('rows', []):
            metrics.setdefault(row['metric'], []).append(float(row['skill']) * 100)
    return score, {k: float(np.mean(v)) for k, v in metrics.items()}
