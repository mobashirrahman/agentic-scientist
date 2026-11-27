"""Complexity-conditioned empirical observation model, with optional lineage delay.

Weights are normalized within each observed WT annotation, preserving its prior
population mass. This is an observational hypothesis, not a causal batch correction.
"""
import numpy as np
from scipy import sparse
from temporal_transport import LatentFlow,lineages,LineageDelay,normalize_log,as_dense


class ComplexityPerturbation:
    def __init__(self,earlier,wt,seed=0):
        self.wt=wt;self.labels=lineages(wt)
        original=wt.obs['celltype'].astype(str).to_numpy()
        complexity=np.log1p(np.asarray((wt.X>0).sum(1)).ravel())
        self.z=np.zeros(wt.n_obs)
        self.strata=[]
        for c in np.unique(original):
            rows=np.flatnonzero(original==c);values=complexity[rows]
            self.z[rows]=(values-values.mean())/max(values.std(),.1)
            self.strata.append(rows)
        self.flow=LatentFlow(earlier,wt,interval=.25,seed=seed)

    def probabilities(self,strength):
        weight=np.exp(np.clip(-strength*self.z,-5,5))
        for rows in self.strata:weight[rows]*=len(rows)/weight[rows].sum()
        return weight/weight.sum()

    def predict(self,strength=.5,delay=0.,n=3000,seed=101):
        idx=np.random.default_rng(seed).choice(self.wt.n_obs,n,replace=True,p=self.probabilities(strength))
        out=self.wt[idx].copy();out.obs_names=[f'pred_{i}' for i in range(n)];out.obs['source_row']=idx
        if delay:
            affected=np.isin(self.labels[idx],list(LineageDelay.CARDIAC))
            shift=(-delay/self.flow.interval*self.flow.velocity[idx[affected]])@self.flow.decoder
            x=as_dense(out.X).astype(np.float32)
            x[affected]*=np.exp(np.clip(shift,-.35,.35));x[affected]=normalize_log(x[affected]).toarray()
            out.X=sparse.csr_matrix(x)
        out.uns['method']='within-type WT complexity-conditioned empirical sampler and lineage delay'
        out.uns['complexity_strength']=strength;out.uns['delay_days']=delay
        return out
