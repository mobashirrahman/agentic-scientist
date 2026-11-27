"""Observed-stage latent transport and anatomy registration, without target access."""
from dataclasses import dataclass
import numpy as np
from scipy import sparse
from scipy.spatial.distance import cdist
from scipy.special import logsumexp
from sklearn.decomposition import TruncatedSVD
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors


# Broad aliases supported by the released stage protocol. Keep subtypes in obs.
ALIASES = {
    'LV-CM':'V-CM', 'RV-CM':'V-CM', 'vCM':'V-CM',
    'Endocardium-1':'Endocardium', 'Endocardium-2':'Endocardium',
    'EndoMT Endocardium':'Endocardium', 'Endo':'Endocardium',
    'Chamber-Endo':'Endocardium', 'Cush-EndoMT-Endo':'Endocardium',
    'Peri':'Pericardium', 'Epicardium':'Epicardial',
    'Proepi':'Epicardial', 'Proepicardium':'Epicardial',
    'SE':'Surface Ectoderm', 'Hepatocytes':'Hepatocyte',
    'Branch Arch':'Branchial Arch',
    'OFT/RV-CM':'OFT-CM',
}


def lineages(a):
    return np.array([ALIASES.get(str(c),str(c)) for c in a.obs['celltype']])


def as_dense(x):
    return x.toarray() if sparse.issparse(x) else np.asarray(x)


def normalize_log(x, library=10000.):
    """Normalize generated linear abundance back to the input log1p CP10k scale."""
    x=np.maximum(np.asarray(x,dtype=np.float32),0)
    np.expm1(np.minimum(x,20),out=x)
    x*=library/np.maximum(x.sum(axis=1,keepdims=True),1e-8)
    np.log1p(x,out=x)
    return sparse.csr_matrix(x)


class Representation:
    """Fit only on input stages: variable genes, sparse SVD and tempered whitening."""
    def fit(self,stages,seed=0,n_features=2000,n_latent=32):
        self.genes=list(stages[0].var_names)
        x=sparse.vstack([a[:,self.genes].X for a in stages],format='csr')
        mean=np.asarray(x.mean(0)).ravel()
        var=np.maximum(np.asarray(x.power(2).mean(0)).ravel()-mean**2,0)
        self.feature=np.argsort(var)[-min(n_features,x.shape[1]):]
        n_components=min(n_latent,len(self.feature)-1,x.shape[0]-1)
        self.svd=TruncatedSVD(n_components=n_components,random_state=seed)
        z=self.svd.fit_transform(x[:,self.feature])
        self.center=z.mean(0)
        self.scale=np.maximum(z.std(0),.25)
        self.variance_explained=float(self.svd.explained_variance_ratio_.sum())
        return self

    def transform(self,a):
        return ((self.svd.transform(a[:,self.genes].X[:,self.feature])-self.center)/self.scale).astype(np.float32)


def coreset(labels,limit,rng):
    """Stratified support with exact empirical mass for each represented group."""
    labels=np.asarray(labels)
    types,counts=np.unique(labels,return_counts=True)
    per=np.maximum(1,np.floor(limit*counts/counts.sum()).astype(int))
    # Permit a few extra anchors to retain rare lineages, bounded by input size.
    idx=[];weight=[]
    for c,count,n in zip(types,counts,per):
        rows=np.flatnonzero(labels==c)
        chosen=rng.choice(rows,min(int(n),len(rows)),replace=False)
        idx.extend(chosen)
        weight.extend([count/len(labels)/len(chosen)]*len(chosen))
    return np.array(idx,dtype=int),np.array(weight,dtype=float)


def sinkhorn_unbalanced(a,b,cost,reg=.25,mass_reg=2.,iterations=250,tolerance=1e-6):
    """Log-domain generalized Sinkhorn; KL penalties relax both marginals.

    Objective: <G,C> + reg*KL(G|a outer b) + mass_reg*KL(G1|a)
    + mass_reg*KL(G.T1|b). The entropy reference a outer b is explicit.
    """
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    cost=np.asarray(cost,dtype=float)
    if reg<=0 or mass_reg<=0 or np.any(a<=0) or np.any(b<=0):
        raise ValueError('Strictly positive masses and regularization required')
    kernel=-cost/reg+np.log(a)[:,None]+np.log(b)[None,:]
    rho=mass_reg/(mass_reg+reg)
    u=np.zeros(len(a));v=np.zeros(len(b));error=np.inf
    for iteration in range(iterations):
        old=u.copy()
        u=rho*(np.log(a)-logsumexp(kernel+v[None,:],axis=1))
        v=rho*(np.log(b)-logsumexp(kernel+u[:,None],axis=0))
        error=float(np.max(np.abs(u-old)))
        if error<tolerance:break
    coupling=np.exp(kernel+u[:,None]+v[None,:])
    return coupling,dict(iterations=iteration+1,error=error,total_mass=float(coupling.sum()),
                         reg=reg,mass_reg=mass_reg,converged=error<tolerance)


def geometry(a):
    p=np.asarray(a.obsm['spatial_3D'],dtype=float)
    center=p.mean(0)
    radius=max(float(np.sqrt(np.mean(np.sum((p-center)**2,axis=1)))),1e-6)
    return (p-center)/radius,radius


def register(right,left,labels_right,labels_left):
    """Proper rigid registration using shared observed lineage centroids."""
    shared=[c for c in np.intersect1d(labels_right,labels_left)
            if c!='Unknown' and (labels_right==c).sum()>=20 and (labels_left==c).sum()>=20]
    if len(shared)<3:
        return right,np.eye(3),dict(shared=len(shared),registered=False)
    a=np.vstack([right[labels_right==c].mean(0) for c in shared])
    b=np.vstack([left[labels_left==c].mean(0) for c in shared])
    weights=np.array([np.sqrt(np.mean(labels_right==c)*np.mean(labels_left==c)) for c in shared])
    # Already in centered whole-stage frames; fit rotation only, not per-type offsets.
    u,s,vt=np.linalg.svd((a*weights[:,None]).T@b)
    if np.linalg.det(u@vt)<0:u[:,-1]*=-1
    rotation=u@vt
    return right@rotation,rotation,dict(shared=len(shared),registered=True,singular_values=s.tolist(),det=float(np.linalg.det(rotation)))


def smooth_field(support,values,queries,k=24):
    nn=NearestNeighbors(n_neighbors=min(k,len(support))).fit(support)
    distance,idx=nn.kneighbors(queries)
    weights=np.exp(-distance/np.maximum(np.median(distance,axis=1,keepdims=True),1e-3))
    weights/=weights.sum(1,keepdims=True)
    return np.einsum('ij,ijk->ik',weights,values[idx])


@dataclass
class SpatialInterpolant:
    left: object
    right: object
    seed: int=0
    support: int=1000

    def __post_init__(self):
        genes=self.left.var_names[self.left.var_names.isin(self.right.var_names)]
        self.left=self.left[:,genes].copy();self.right=self.right[:,genes].copy()
        self.la,self.lb=lineages(self.left),lineages(self.right)
        self.pa,self.ra=geometry(self.left)
        self.pb0,self.rb=geometry(self.right)
        self.pb,self.rotation,self.registration=register(self.pb0,self.pa,self.lb,self.la)
        self.representation=Representation().fit([self.left,self.right],self.seed)
        self.za=self.representation.transform(self.left)
        self.zb=self.representation.transform(self.right)
        rng=np.random.default_rng(self.seed)
        self.ia,wa=coreset(self.la,self.support,rng)
        self.ib,wb=coreset(self.lb,self.support,rng)
        za,zb=self.za[self.ia],self.zb[self.ib]
        cost=cdist(za,zb,'sqeuclidean')/za.shape[1]
        cost+=2*cdist(self.pa[self.ia],self.pb[self.ib],'sqeuclidean')
        cost+=(self.la[self.ia,None]!=self.lb[None,self.ib])*.75
        coupling,self.solver=sinkhorn_unbalanced(wa,wb,cost)
        self.a_to_b=(coupling@self.pb[self.ib])/np.maximum(coupling.sum(1,keepdims=True),1e-12)
        self.b_to_a=(coupling.T@self.pa[self.ia])/np.maximum(coupling.sum(0)[:,None],1e-12)
        self.delta_a=smooth_field(self.pa[self.ia],self.a_to_b-self.pa[self.ia],self.pa)
        self.delta_b=smooth_field(self.pb[self.ib],self.b_to_a-self.pb[self.ib],self.pb)

    def predict(self,fraction,n=3000,seed=42,mode='registered',deformation=1.):
        import anndata as ad
        if not 0<=fraction<=1:raise ValueError('Interpolation requires a bracketed fraction')
        counts=[round(n*(1-fraction)),n-round(n*(1-fraction))]
        parts=[]
        target_radius=np.exp((1-fraction)*np.log(self.ra)+fraction*np.log(self.rb))
        for endpoint,(a,p,delta,count) in enumerate(zip((self.left,self.right),(self.pa,self.pb),
                (self.delta_a,self.delta_b),counts)):
            if count==0:continue
            idx=np.random.default_rng(seed+endpoint).choice(a.n_obs,count,replace=a.n_obs<count)
            part=a[idx].copy()
            part.obs_names=[f'{endpoint}_{i}' for i in range(count)]
            positions=p[idx].copy()
            if mode=='transport':
                positions+=deformation*(fraction if endpoint==0 else 1-fraction)*delta[idx]
            elif mode!='registered':raise ValueError(mode)
            part.obsm['spatial_3D']=(positions*target_radius).astype(np.float32)
            part.obs['source_row']=idx
            part.obs['source_endpoint']=endpoint
            parts.append(part)
        out=ad.concat(parts,merge='same',join='inner')
        out.obs_names=[f'pred_{i}' for i in range(n)]
        out.uns['method']='registered expression-preserving spatial '+mode
        out.uns['registration']=self.registration
        out.uns['solver']=self.solver
        return out


class LatentFlow:
    """Unbalanced observed-stage transport with density growth and residual decoding."""
    def __init__(self,earlier,latest,interval=1.,seed=0,support=1200):
        self.latest=latest
        self.earlier=earlier[:,latest.var_names].copy()
        self.interval=interval
        self.labels_a,self.labels_b=lineages(self.earlier),lineages(latest)
        self.representation=Representation().fit([self.earlier,latest],seed)
        self.za=self.representation.transform(self.earlier)
        self.zb=self.representation.transform(latest)
        rng=np.random.default_rng(seed)
        ia,wa=coreset(self.labels_a,support,rng)
        ib,wb=coreset(self.labels_b,support,rng)
        cost=cdist(self.za[ia],self.zb[ib],'sqeuclidean')/self.za.shape[1]
        cost+=(self.labels_a[ia,None]!=self.labels_b[None,ib])*1.5
        coupling,self.solver=sinkhorn_unbalanced(wa,wb,cost)
        ancestors=(coupling.T@self.za[ia])/np.maximum(coupling.sum(0)[:,None],1e-12)
        velocity=self.zb[ib]-ancestors
        self.velocity=smooth_field(self.zb[ib],velocity,self.zb)
        # Regularized linear decoder of log expression. Fits all genes sparsely;
        # generated values are empirical residuals plus a bounded mean response.
        z=np.vstack([self.za,self.zb]).astype(float)
        x=sparse.vstack([self.earlier.X,latest.X],format='csr')
        z-=z.mean(0)
        self.decoder=np.linalg.solve(z.T@z+10*np.eye(z.shape[1]),np.asarray(x.T@z).T).astype(np.float32)
        classifier=LogisticRegression(C=.1,max_iter=300,class_weight='balanced',random_state=seed)
        classifier.fit(np.vstack([self.za,self.zb]),np.r_[np.zeros(len(self.za)),np.ones(len(self.zb))])
        self.log_growth=np.clip(classifier.decision_function(self.zb),-np.log(2),np.log(2))
        self.spatial_velocity=None
        if 'spatial_3D' in latest.obsm and 'spatial_3D' in self.earlier.obsm:
            pa,ra=geometry(self.earlier);pb,rb=geometry(latest)
            aligned,_,self.registration=register(pa,pb,self.labels_a,self.labels_b)
            ancestor_pos=(coupling.T@aligned[ia])/np.maximum(coupling.sum(0)[:,None],1e-12)
            self.spatial_velocity=smooth_field(pb[ib],pb[ib]-ancestor_pos,pb)
            # Bound local strain to avoid folding neighboring cells through one another.
            nearest=NearestNeighbors(n_neighbors=min(8,len(pb))).fit(pb).kneighbors(pb,return_distance=False)[:,1:]
            numerator=np.linalg.norm(self.spatial_velocity[:,None]-self.spatial_velocity[nearest],axis=2)
            denominator=np.maximum(np.linalg.norm(pb[:,None]-pb[nearest],axis=2),1e-4)
            strain=float(np.quantile(numerator/denominator,.95))
            self.spatial_velocity*=min(1.,.4/max(strain,1e-8))
            self.pb,self.radius=pb,rb
            self.growth_rate=float(np.clip(np.log(rb/ra)/interval,-.15,.25))

    def predict(self,horizon,n=3000,seed=42,state=.25,growth=.25,deformation=0.,scale=0.):
        factor=min(horizon/self.interval,2.)
        weights=np.exp(growth*factor*self.log_growth)
        weights/=weights.sum()
        idx=np.random.default_rng(seed).choice(self.latest.n_obs,n,replace=True,p=weights)
        out=self.latest[idx].copy()
        out.obs_names=[f'pred_{i}' for i in range(n)]
        out.obs['source_row']=idx
        if state:
            shift=(state*factor*self.velocity[idx])@self.decoder
            # A multiplicative empirical-residual decoder preserves observed zeros
            # and heterogeneous profiles, unlike dense centroid addition.
            shift=np.clip(shift,-.35,.35)
            x=as_dense(out.X).astype(np.float32)
            x*=np.exp(shift)
            out.X=normalize_log(x)
        if self.spatial_velocity is not None:
            p=self.pb[idx]+deformation*factor*self.spatial_velocity[idx]
            out.obsm['spatial_3D']=(p*self.radius*np.exp(scale*horizon*self.growth_rate)).astype(np.float32)
        out.uns['method']='unbalanced latent flow with density growth and empirical residual decoder'
        out.uns['solver']=self.solver
        return out


class LineageDelay:
    """A partial cardiac-lineage maturation arrest learned from WT stages only."""
    CARDIAC={'V-CM','A-CM','OFT-CM','IFT-CM','SV-CM','AVC-CM','SHF','aSHF','pSHF',
             'aPHM','pPHM','JCF','Endocardium','Epicardial','Pericardium'}
    SHF={'SHF','aSHF','pSHF','aPHM','pPHM','OFT-CM'}

    def __init__(self,earlier,wt,interval=.25,seed=0):
        self.flow=LatentFlow(earlier,wt,interval,seed)
        self.wt=wt
        self.labels=lineages(wt)

    def predict(self,delay=.0625,depletion=.1,n=3000,seed=42):
        weights=np.ones(self.wt.n_obs)
        weights[np.isin(self.labels,list(self.SHF))]=max(1-depletion,.05)
        idx=np.random.default_rng(seed).choice(self.wt.n_obs,n,replace=True,p=weights/weights.sum())
        out=self.wt[idx].copy()
        out.obs_names=[f'pred_{i}' for i in range(n)]
        out.obs['source_row']=idx
        affected=np.isin(self.labels[idx],list(self.CARDIAC))
        if delay:
            shift=(-delay/self.flow.interval*self.flow.velocity[idx[affected]])@self.flow.decoder
            x=as_dense(out.X).astype(np.float32)
            x[affected]*=np.exp(np.clip(shift,-.35,.35))
            x[affected]=normalize_log(x[affected]).toarray()
            out.X=sparse.csr_matrix(x)
        out.uns['method']='partial cardiac-lineage developmental delay from WT transport'
        out.uns['delay_days']=delay
        out.uns['depletion']=depletion
        return out
