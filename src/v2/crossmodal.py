"""RNA-guided temporal responses projected onto the measured MERFISH panel.

Uses only observed RNA stages and a contemporaneous observed spatial reference.
The spatial holdout and its same-stage RNA counterpart are excluded from fitting.
"""
import gc
import numpy as np
from scipy import sparse
from .transport import LatentFlow,lineages,as_dense,normalize_log


class RNAStateGuide:
    def __init__(self,rna_stages,spatial_reference,times,horizon,seed=0):
        self.reference=spatial_reference
        self.labels=lineages(spatial_reference)
        model=LatentFlow(*rna_stages,interval=times[-1]-times[-2],seed=seed)
        # Pair the same sampled RNA cells before/after learned state transport.
        future=model.predict(horizon,n=6000,seed=seed+1701,state=.35,growth=.25)
        anchor=model.predict(horizon,n=6000,seed=seed+1701,state=0.,growth=.25)
        genes=list(spatial_reference.var_names)
        assert all(g in future.var_names for g in genes)
        f=as_dense(future[:,genes].X);a=as_dense(anchor[:,genes].X)
        rna_labels=lineages(future)
        spatial=as_dense(spatial_reference.X)
        self.response={};coverage={}
        for label in np.unique(self.labels):
            ri=rna_labels==label;si=self.labels==label
            if ri.sum()<30 or si.sum()<30:continue
            mean=spatial[si].mean(0)
            rna_std=np.maximum(a[ri].std(0),.25)
            spatial_std=spatial[si].std(0)
            delta=(f[ri]-a[ri]).mean(0)*spatial_std/rna_std
            self.response[label]=np.clip(delta,-.5,.5)/np.maximum(mean,.25)
            coverage[label]=dict(rna_cells=int(ri.sum()),spatial_cells=int(si.sum()),
                                  response_norm=float(np.linalg.norm(delta)))
        covered=np.isin(self.labels,list(self.response))
        self.audit=dict(coverage_fraction=float(covered.mean()),groups=coverage,rna_solver=model.solver,
                        rna_horizon=horizon,rna_state_strength=.35)
        del model,future,anchor;gc.collect()

    def predict(self,strength=.5,n=3000,seed=101,geometry_scale=0.,geometry_rate=.25,horizon=1.):
        weights=np.full(self.reference.n_obs,1/self.reference.n_obs)
        idx=np.random.default_rng(seed).choice(self.reference.n_obs,n,replace=True,p=weights)
        out=self.reference[idx].copy();out.obs_names=[f'pred_{i}' for i in range(n)]
        out.obs['source_row']=idx
        x=as_dense(out.X).astype(np.float32)
        for label,response in self.response.items():
            rows=self.labels[idx]==label
            x[rows]*=np.exp(np.clip(strength*response,-.5,.5))
        out.X=normalize_log(x)
        if geometry_scale:
            p=out.obsm['spatial_3D'];p=p-p.mean(0)
            out.obsm['spatial_3D']=(p*np.exp(geometry_scale*horizon*geometry_rate)).astype(np.float32)
        out.uns['method']='observed RNA temporal transport projected onto spatial expression'
        return out
