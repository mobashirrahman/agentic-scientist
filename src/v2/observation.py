"""Stage-dependent detection model for continuous MERFISH expression.

Fits observed gene-detection trends, separately from biological state transport.
Uses a hurdle thinning model, not an integer-count likelihood for fractional data.
"""
import numpy as np
from scipy import sparse
from scipy.stats import theilslopes
from .transport import LatentFlow,lineages,normalize_log,as_dense


def detection_mask(x,ratio,rng):
    """Sample a count-dependent mask with prescribed expected detected-gene count.

    Positive values of x are log expression. High-abundance genes are more likely
    to survive. No unobserved genes are invented, and ratio=1 is exactly identity.
    """
    x=np.asarray(x,dtype=np.float32);ratio=np.asarray(ratio,dtype=float)
    result=x.copy();change=ratio<1-1e-8
    if not change.any():return result
    source=x[change]
    abundance=np.expm1(np.minimum(source,20))
    abundance/=np.maximum(abundance.sum(1,keepdims=True),1e-8)
    target=(source>0).sum(1)*ratio[change]
    lo=np.zeros(len(source));hi=np.full(len(source),1e7)
    for _ in range(40):
        mid=(lo+hi)/2
        count=(-np.expm1(-mid[:,None]*abundance)).sum(1)
        lower=count<target
        lo=np.where(lower,mid,lo);hi=np.where(lower,hi,mid)
    probability=-np.expm1(-((lo+hi)/2)[:,None]*abundance)
    keep=rng.random(probability.shape)<probability
    # Reject biologically empty simulated cells using their strongest detected gene.
    empty=~keep.any(1)
    keep[np.flatnonzero(empty),np.argmax(source[empty],axis=1)]=True
    result[change]*=keep
    return result


class ObservationFlow:
    def __init__(self,stages,times,seed=0):
        self.stages=stages;self.times=np.array(times,dtype=float);self.latest=stages[-1]
        self.labels=[lineages(a) for a in stages]
        detected=[np.asarray((a.X>0).sum(1)).ravel() for a in stages]
        global_median=[np.median(k) for k in detected]
        self.global_rate=float(np.clip(theilslopes(np.log(np.maximum(global_median,1)),self.times)[0],-.8,0))
        self.rates={}
        for label in np.unique(self.labels[-1]):
            available=[i for i,l in enumerate(self.labels) if np.sum(l==label)>=50]
            if len(available)>=3:
                y=[np.log(max(float(np.median(detected[i][self.labels[i]==label])),1)) for i in available]
                slope=float(theilslopes(y,self.times[available])[0])
                self.rates[label]=float(np.clip(.5*slope+.5*self.global_rate,-.8,0))
            else:self.rates[label]=self.global_rate
        self.flow=LatentFlow(stages[-2],stages[-1],self.times[-1]-self.times[-2],seed)
        self.audit=dict(stage_median_detected=[float(x) for x in global_median],global_rate=self.global_rate,lineage_rates=self.rates)

    def predict(self,horizon,n=3000,seed=101,observation=.5,state=0.,growth=0.):
        result=self.flow.predict(horizon,n,seed,state=state,growth=growth)
        rows=result.obs.source_row.to_numpy()
        labels=self.labels[-1][rows]
        rates=np.array([self.rates[c] for c in labels])
        ratio=np.clip(np.exp(observation*horizon*rates),.6,1.)
        x=detection_mask(as_dense(result.X),ratio,np.random.default_rng(seed+117))
        result.X=normalize_log(x)
        result.uns['method']='observed-stage detection trend with empirical hurdle thinning and latent flow'
        result.uns['observation_strength']=observation
        return result
