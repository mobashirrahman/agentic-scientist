"""Regularized multi-stage latent and spatial vector fields from observed inputs."""
import numpy as np
from scipy import sparse
from scipy.spatial.distance import cdist
from scipy.stats import theilslopes
from sklearn.neighbors import NearestNeighbors
from .transport import Representation,lineages,coreset,sinkhorn_unbalanced,geometry,register,normalize_log,as_dense


class MultiStageFlow:
    def __init__(self,stages,times,seed=0,support=800,ridge=30.):
        self.stages=stages;self.times=np.asarray(times,dtype=float)
        if len(stages)<3:raise ValueError('At least three observed stages required')
        self.latest=stages[-1];self.genes=list(self.latest.var_names)
        self.labels=[lineages(a) for a in stages]
        self.groups=np.unique(np.concatenate(self.labels));self.group_index={c:i for i,c in enumerate(self.groups)}
        self.rep=Representation().fit(stages,seed)
        self.z=[self.rep.transform(a) for a in stages]
        all_z=np.vstack(self.z).astype(float)
        all_x=sparse.vstack([a[:,self.genes].X for a in stages],format='csr')
        centered=all_z-all_z.mean(0)
        self.decoder=np.linalg.solve(centered.T@centered+10*np.eye(centered.shape[1]),np.asarray(all_x.T@centered).T).astype(np.float32)
        detection=np.log1p(np.asarray((all_x>0).sum(1)).ravel())
        self.depth_axis=np.linalg.solve(centered.T@centered+10*np.eye(centered.shape[1]),centered.T@(detection-detection.mean()))
        self.depth_axis/=max(np.linalg.norm(self.depth_axis),1e-8)
        self.onehot=[np.eye(len(self.groups))[[self.group_index[g] for g in labels]] for labels in self.labels]
        proportions=np.vstack([(np.bincount([self.group_index[g] for g in labels],minlength=len(self.groups))+.5)/(len(labels)+.5*len(self.groups)) for labels in self.labels])
        logp=np.log(proportions);logp-=logp.mean(1,keepdims=True)
        dt=self.times-self.times[-1]
        # Ridge slope with a free intercept; every observed stage has equal weight.
        centered_t=dt-dt.mean()
        self.growth_slope=centered_t@logp/(centered_t@centered_t+.5)
        self.has_geometry=all('spatial_3D' in a.obsm for a in stages)
        if self.has_geometry:
            raw=[geometry(a) for a in stages]
            self.radius=raw[-1][1]
            self.p=[]
            for (p,_),labels in zip(raw,self.labels):
                p,_,_=register(p,raw[-1][0],labels,self.labels[-1])
                self.p.append(p)
            self.scale_rate=float(np.clip(theilslopes(np.log([r for _,r in raw]),self.times)[0],0,.25))
        rng=np.random.default_rng(seed)
        inputs=[];outputs=[];weights=[];spatial_outputs=[];solvers=[]
        for k in range(len(stages)-1):
            ia,wa=coreset(self.labels[k],support,rng)
            ib,wb=coreset(self.labels[k+1],support,rng)
            za,zb=self.z[k][ia],self.z[k+1][ib]
            cost=cdist(za,zb,'sqeuclidean')/za.shape[1]
            cost+=(self.labels[k][ia,None]!=self.labels[k+1][None,ib])*1.5
            coupling,info=sinkhorn_unbalanced(wa,wb,cost)
            solvers.append(info)
            mass=np.maximum(coupling.sum(0),1e-12)
            ancestors=coupling.T@za/mass[:,None]
            interval=self.times[k+1]-self.times[k]
            inputs.append(np.column_stack([zb,self.onehot[k+1][ib]]))
            outputs.append((zb-ancestors)/interval)
            weights.append(mass/mass.sum())
            if self.has_geometry:
                ancestral_pos=coupling.T@self.p[k][ia]/mass[:,None]
                spatial_outputs.append((self.p[k+1][ib]-ancestral_pos)/interval)
        design=np.vstack(inputs);velocity=np.vstack(outputs);weight=np.concatenate(weights)
        # Normalize the regularizer to the transition-support scale rather than
        # number of cells in one embryo's dissection.
        weight*=len(weight)/weight.sum()
        gram=design.T@(design*weight[:,None])+ridge*np.eye(design.shape[1])
        coef=np.linalg.solve(gram,design.T@(velocity*weight[:,None]))
        final_design=np.column_stack([self.z[-1],self.onehot[-1]])
        self.velocity=final_design@coef
        # Limit unsupported large speeds in new regions of latent state space.
        speed=np.linalg.norm(self.velocity,axis=1)
        cap=float(np.quantile(np.linalg.norm(velocity,axis=1),.9))
        self.velocity*=np.minimum(1.,cap/np.maximum(speed,1e-8))[:,None]
        self.solvers=solvers
        if self.has_geometry:
            coef_p=np.linalg.solve(gram,design.T@(np.vstack(spatial_outputs)*weight[:,None]))
            self.spatial_velocity=final_design@coef_p
            nn=NearestNeighbors(n_neighbors=min(8,len(self.p[-1]))).fit(self.p[-1]).kneighbors(self.p[-1],return_distance=False)[:,1:]
            strain=np.linalg.norm(self.spatial_velocity[:,None]-self.spatial_velocity[nn],axis=2)/np.maximum(np.linalg.norm(self.p[-1][:,None]-self.p[-1][nn],axis=2),1e-4)
            self.spatial_velocity*=min(1.,.4/max(float(np.quantile(strain,.95)),1e-8))

    def predict(self,horizon,n=3000,seed=101,state=.15,growth=.5,deformation=0.,scale=0.,remove_depth=False):
        horizon=min(horizon,2*(self.times[-1]-self.times[-2]))
        labels=self.labels[-1];group=np.array([self.group_index[g] for g in labels])
        weight=np.exp(growth*np.clip(horizon*self.growth_slope[group],-np.log(2),np.log(2)))
        idx=np.random.default_rng(seed).choice(self.latest.n_obs,n,replace=True,p=weight/weight.sum())
        out=self.latest[idx].copy();out.obs_names=[f'pred_{i}' for i in range(n)]
        out.obs['source_row']=idx
        if state:
            velocity=self.velocity[idx].copy()
            if remove_depth:velocity-=np.outer(velocity@self.depth_axis,self.depth_axis)
            change=np.clip((horizon*state*velocity)@self.decoder,-.35,.35)
            x=as_dense(out.X).astype(np.float32)*np.exp(change)
            out.X=normalize_log(x)
        if self.has_geometry:
            positions=self.p[-1][idx]+horizon*deformation*self.spatial_velocity[idx]
            out.obsm['spatial_3D']=(positions*self.radius*np.exp(scale*horizon*self.scale_rate)).astype(np.float32)
        out.uns['method']='multi-stage regularized unbalanced transport vector field'
        return out
