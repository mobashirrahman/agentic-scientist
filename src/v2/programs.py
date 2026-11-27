"""Cross-stage WT regulatory-program associations for zero-shot perturbation.

These are observational associations, not identified causal knockout effects.
No knockout outcomes enter program fitting. Coefficients are retained only when
both released RNA stages support the same sign after cell-type/depth adjustment.
"""
import numpy as np
from scipy import sparse
from scipy.stats import t as student_t
from .transport import lineages,as_dense,normalize_log,LineageDelay

PROGRAMS={'gata4':['Gata4','Gata6'], 'bcatenin':['Axin2','Lef1','Tcf7','Sp5','Nkd1']}
CARDIAC=LineageDelay.CARDIAC


def bh(p):
    order=np.argsort(p);rank=np.arange(1,len(p)+1)
    values=np.minimum.accumulate((p[order]*len(p)/rank)[::-1])[::-1]
    out=np.empty_like(values);out[order]=np.minimum(values,1.)
    return out


def fit_program(stages,genes,target):
    program=PROGRAMS[target]
    coefficients=[];details=[]
    for a in stages:
        groups=lineages(a);mask=np.isin(groups,list(CARDIAC))
        if mask.sum()<100:raise ValueError('Insufficient observed cardiac cells')
        selected=a[mask].copy();groups=groups[mask]
        present=[g for g in genes if g in a.var_names]
        x=np.zeros((selected.n_obs,len(genes)),dtype=np.float64)
        columns=[genes.index(g) for g in present]
        x[:,columns]=as_dense(selected[:,present].X)
        x=(x-x.mean(0))/np.maximum(x.std(0),.25)
        available=[g for g in program if g in a.var_names]
        if len(available)<2:raise ValueError('Insufficient source program coverage')
        values=as_dense(selected[:,available].X).astype(float)
        values=(values-values.mean(0))/np.maximum(values.std(0),.25)
        activity=values.mean(1)
        detection=np.log1p(np.asarray((selected.X>0).sum(1)).ravel())
        detection=(detection-detection.mean())/max(detection.std(),.1)
        _,ct=np.unique(groups,return_inverse=True)
        design=np.column_stack([np.eye(ct.max()+1)[ct],detection])
        inverse=np.linalg.solve(design.T@design+1e-4*np.eye(design.shape[1]),design.T)
        residual=x-design@(inverse@x)
        score=activity-design@(inverse@activity)
        score/=max(score.std(),1e-6)
        beta=score@residual/len(score)
        correlation=beta/np.maximum(residual.std(0),.05)
        correlation=np.clip(correlation,-.999,.999)
        dof=max(len(score)-design.shape[1]-1,1)
        statistic=correlation*np.sqrt(dof/np.maximum(1-correlation**2,1e-8))
        q=bh(2*student_t.sf(np.abs(statistic),dof))
        beta[(q>.05)|(np.abs(beta)<.05)]=0
        beta=np.clip(beta,-.7,.7)
        coefficients.append(beta)
        details.append(dict(cells=int(mask.sum()),genes_covered=len(present),program_genes=available,
                            significant_coefficients=int(np.count_nonzero(beta))))
    signs=np.vstack([np.sign(b) for b in coefficients])
    stable=np.all(signs==signs[0],axis=0)&(signs[0]!=0)
    beta=np.mean(coefficients,axis=0)*stable
    return beta,dict(target=target,program_genes=program,stage_audits=details,
                     stable_genes=int(np.count_nonzero(beta)),interpretation='WT association, not a causal intervention estimate')


class ProgramPerturbation:
    def __init__(self,wt,beta):
        self.wt=wt;self.beta=np.asarray(beta,dtype=np.float32)
        self.labels=lineages(wt)
        if len(beta)!=wt.n_vars:raise ValueError('Program gene order mismatch')
        self.stats={}
        global_mask=np.isin(self.labels,list(CARDIAC))
        x=as_dense(wt.X)
        self.global_mean=x[global_mask].mean(0);self.global_std=x[global_mask].std(0)
        for c in np.unique(self.labels[global_mask]):
            rows=self.labels==c
            if rows.sum()>=30:self.stats[c]=(x[rows].mean(0),x[rows].std(0))

    def predict(self,strength=.5,depletion=0.,n=3000,seed=101):
        weights=np.ones(self.wt.n_obs)
        weights[np.isin(self.labels,list(LineageDelay.SHF))]=max(1-depletion,.05)
        idx=np.random.default_rng(seed).choice(self.wt.n_obs,n,replace=True,p=weights/weights.sum())
        out=self.wt[idx].copy();out.obs_names=[f'pred_{i}' for i in range(n)];out.obs['source_row']=idx
        x=as_dense(out.X).astype(np.float32);labels=self.labels[idx]
        for c in np.unique(labels):
            if c not in CARDIAC:continue
            rows=labels==c;mean,std=self.stats.get(c,(self.global_mean,self.global_std))
            if strength:
                score=((x[rows]-mean)/np.maximum(std,.25))@self.beta/max(np.linalg.norm(self.beta),1e-6)
                responsiveness=np.clip(1+.15*score,.5,1.5)
                logratio=-strength*self.beta*std/np.maximum(mean,.25)
                x[rows]*=np.exp(np.clip(responsiveness[:,None]*logratio,-.5,.5))
                x[rows]=normalize_log(x[rows]).toarray()
        out.X=sparse.csr_matrix(x)
        out.uns['method']='cross-stage WT program association with lineage-restricted response'
        out.uns['program_strength']=strength
        return out
