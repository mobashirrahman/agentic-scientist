"""Composition extrapolation invariant to the arbitrary common logit slope."""
import numpy as np
from .multistage import MultiStageFlow


def relative_rates(rates,frequencies):
    rates=np.asarray(rates,dtype=float)
    frequencies=np.asarray(frequencies,dtype=float)
    if frequencies.sum()<=0:raise ValueError('Positive population mass required')
    return rates-np.dot(rates,frequencies/frequencies.sum())


class RelativeMultiStageFlow(MultiStageFlow):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        latest=self.labels[-1]
        proportions=np.array([np.mean(latest==g) for g in self.groups])
        self.original_rates=self.growth_slope.copy()
        # A common slope cancels in an unbounded softmax, but clipping it first
        # can saturate every observed lineage and silently produce uniform weights.
        self.growth_slope=relative_rates(self.growth_slope,proportions)
