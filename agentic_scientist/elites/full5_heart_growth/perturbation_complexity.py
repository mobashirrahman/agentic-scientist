"""Complexity-conditioned empirical observation model, with optional lineage delay
and an optional local lineage rollback (perturbation_local_rollback.py).

Weights are normalized within each observed WT annotation, preserving its prior
population mass. This is an observational hypothesis, not a causal batch correction.
The local rollback multiplies those frozen parent probabilities by a single
per-annotation constant f'_t/f_t, so p(cell | type) is untouched; it only moves the
relative mass of annotations whose own WT cells show a knockout-detection excess.
"""
import numpy as np
from scipy import sparse
from perturbation_transport import LatentFlow,lineages,LineageDelay,normalize_log,as_dense


class ComplexityPerturbation:
    def __init__(self,earlier,wt,seed=0,interval=.25):
        self.earlier=earlier;self.wt=wt;self.seed=seed;self.interval=interval
        self.labels=lineages(wt)
        original=wt.obs['celltype'].astype(str).to_numpy()
        complexity=np.log1p(np.asarray((wt.X>0).sum(1)).ravel())
        self.z=np.zeros(wt.n_obs)
        self.strata=[]
        for c in np.unique(original):
            rows=np.flatnonzero(original==c);values=complexity[rows]
            self.z[rows]=(values-values.mean())/max(values.std(),.1)
            self.strata.append(rows)
        self.types=np.unique(original)
        # The latent transport is only needed by the (here unused) delay arm; it is
        # built lazily so the default delay=0 path spends no time on it.
        self._flow=None

    @property
    def flow(self):
        if self._flow is None:
            self._flow=LatentFlow(self.earlier,self.wt,interval=self.interval,seed=self.seed)
        return self._flow

    def base_probabilities(self,strength):
        """The parent law: within-annotation complexity tilt, mass f_t per type."""
        weight=np.exp(np.clip(-strength*self.z,-5,5))
        for rows in self.strata:weight[rows]*=len(rows)/weight[rows].sum()
        return weight/weight.sum()

    def probabilities(self,strength,rollback=None,uniform=False):
        """Donor law for one of the four pre-registered arms.

        rollback=None, uniform=False -> parent complexity law (bit-identical).
        rollback=None, uniform=True  -> uniform WT (abstention arm).
        rollback=dict, uniform=False -> parent law x f'_t/f_t (primary arm).
        rollback=dict, uniform=True  -> uniform WT x f'_t/f_t (clean ablation).

        An abstaining rollback dict (off-panel/low detection/no earlier input/A=0)
        returns the exact uniform 1/N law and drops the generic complexity tilt.
        """
        n=self.wt.n_obs
        if rollback is None:
            return np.full(n,1.0/n) if uniform else self.base_probabilities(strength)
        if rollback.get('abstain',False):
            return np.full(n,1.0/n)
        p0=np.full(n,1.0/n) if uniform else self.base_probabilities(strength)
        # Map the per-type multipliers by label, so a different type ordering can
        # never mismatch the strata (labels are the original WT celltype strings).
        ratio={str(t):float(v) for t,v in zip(rollback['types'],rollback['ratio'])}
        p=p0.copy()
        for rows,t in zip(self.strata,self.types):
            p[rows]*=ratio.get(str(t),1.0)
        total=float(p.sum())
        # Analytic conservation: the multiplier is f'_t/f_t and sum_t f'_t == 1,
        # so only floating-point drift is repaired here.  A broken vector falls
        # back to the uniform WT law instead of crashing the board.
        if not np.all(np.isfinite(p)) or abs(total-1.0)>1e-9:
            return np.full(n,1.0/n)
        return p/total

    def predict(self,strength=.5,delay=0.,n=3000,seed=101,rollback=None,uniform=False):
        probs=self.probabilities(strength,rollback=rollback,uniform=uniform)
        idx=np.random.default_rng(seed).choice(self.wt.n_obs,n,replace=True,p=probs)
        out=self.wt[idx].copy();out.obs_names=[f'pred_{i}' for i in range(n)];out.obs['source_row']=idx
        if delay:
            affected=np.isin(self.labels[idx],list(LineageDelay.CARDIAC))
            shift=(-delay/self.flow.interval*self.flow.velocity[idx[affected]])@self.flow.decoder
            x=as_dense(out.X).astype(np.float32)
            x[affected]*=np.exp(np.clip(shift,-.35,.35));x[affected]=normalize_log(x[affected]).toarray()
            out.X=sparse.csr_matrix(x)
        out.uns['method']='within-type WT complexity-conditioned empirical sampler and lineage delay'
        out.uns['complexity_strength']=strength;out.uns['delay_days']=delay
        # Flat diagnostics only (h5ad uns cannot hold nested structures).
        if rollback is not None:
            rb=dict(rollback)
            out.uns['local_rollback']=dict(
                abstain=float(bool(rb.get('abstain',False))),
                reason=str(rb.get('reason','ok')),
                detected=float(rb.get('detected',0)),
                q=float(rb.get('q',0.0)),
                exposed_mass=float(rb.get('A',0.0)),
                rollback_norm=float(rb.get('B',0.0)),
                min_stage_ratio=float(rb.get('min_r',1.0)),
                max_stage_ratio=float(rb.get('max_r',1.0)),
                donor_tv=float(0.5*np.abs(probs-(
                    np.full(len(probs),1.0/len(probs)) if rollback.get('abstain',False)
                    else self.base_probabilities(strength))).sum()),
                max_unexposed_mass_error=float(rb.get('max_unexposed_mass_error',0.0)),
                uniform_arm=float(bool(uniform)),
                probability_sum=float(probs.sum()),
                types=np.array([str(t) for t in rb.get('types',[])],dtype=str),
                mass_before=np.asarray(rb.get('f_before',[]),dtype=float),
                mass_after=np.asarray(rb.get('f_after',[]),dtype=float),
                exposure=np.asarray(rb.get('exposure',[]),dtype=float),
                stage_ratio=np.asarray(rb.get('stage_ratio',[]),dtype=float))
        return out
