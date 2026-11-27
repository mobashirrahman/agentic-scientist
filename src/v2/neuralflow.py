"""Unbalanced temporal transport in a learned count-VAE latent space."""
import numpy as np
from scipy import sparse
from scipy.spatial.distance import cdist
import torch
from .transport import coreset,sinkhorn_unbalanced,smooth_field


class NeuralTemporalFlow:
    def __init__(self,generator,seed=0,support=1000):
        self.generator=generator
        generator.model.eval()
        encoded=[]
        with torch.no_grad():
            for begin in range(0,generator.x.shape[0],256):
                idx=np.arange(begin,min(begin+256,generator.x.shape[0]))
                features=(generator.x[idx][:,generator.features].toarray()-generator.feature_mean)/generator.feature_scale
                tensors=[torch.as_tensor(x,dtype=torch.float32,device=generator.device) for x in
                         (features,generator.onehot[idx],generator.t[idx])]
                mean,_=generator.model.encode(*tensors)
                encoded.append(mean.cpu().numpy())
        all_z=np.vstack(encoded)
        offset=generator.latest_offset
        za,zb=all_z[:offset],all_z[offset:]
        labels_a=np.concatenate(generator.labels[:-1]);labels_b=generator.labels[-1]
        if len(generator.labels)!=2:raise ValueError('This experiment fits a two-stage transition only')
        scale=np.maximum(all_z.std(0),.2)
        rng=np.random.default_rng(seed)
        ia,wa=coreset(labels_a,support,rng);ib,wb=coreset(labels_b,support,rng)
        cost=cdist(za[ia]/scale,zb[ib]/scale,'sqeuclidean')/za.shape[1]
        cost+=(labels_a[ia,None]!=labels_b[None,ib])*1.5
        coupling,self.solver=sinkhorn_unbalanced(wa,wb,cost)
        ancestors=coupling.T@za[ia]/np.maximum(coupling.sum(0)[:,None],1e-12)
        self.velocity=smooth_field(zb[ib]/scale,zb[ib]-ancestors,zb/scale)
        cap=float(np.quantile(np.linalg.norm(zb[ib]-ancestors,axis=1),.9))
        self.velocity*=np.minimum(1.,cap/np.maximum(np.linalg.norm(self.velocity,axis=1),1e-8))[:,None]

    def predict(self,horizon,n=3000,seed=101,latent_strength=.35,time_strength=.25,composition=.25):
        import anndata as ad
        g=self.generator;rng=np.random.default_rng(seed);torch.manual_seed(seed)
        counts=np.vstack([np.bincount([g.group_index[c] for c in labels],minlength=len(g.groups)) for labels in g.labels])
        p=(counts+.5)/(counts.sum(1,keepdims=True)+.5*len(g.groups))
        interval=g.times[-1]-g.times[-2]
        rate=np.clip(np.log(p[-1]/p[-2])/interval,-np.log(2),np.log(2))
        weights=np.exp(composition*min(horizon,2.)*rate[[g.group_index[c] for c in g.labels[-1]]])
        idx=rng.choice(g.latest.n_obs,n,replace=True,p=weights/weights.sum())
        generated=[]
        with torch.no_grad():
            for start in range(0,n,64):
                rows=idx[start:start+64]
                features,counts,groups,t=g.batch(g.latest_offset+rows)
                mean,logvar=g.model.encode(features,groups,t)
                latent=mean+torch.randn_like(mean)*torch.exp(.5*logvar)
                latent+=torch.as_tensor(self.velocity[rows],dtype=torch.float32,device=g.device)*min(horizon/interval,2.)*latent_strength
                mu,theta=g.model.decode(latent,groups,t+time_strength*horizon/g.time_scale,counts.sum(1,keepdim=True))
                counts_sample=torch.poisson(torch.distributions.Gamma(theta,theta/mu).sample())
                values=torch.log1p(10000*counts_sample/counts_sample.sum(1,keepdim=True).clamp_min(1.))
                generated.append(values.cpu().numpy())
        result=ad.AnnData(sparse.csr_matrix(np.vstack(generated)),obs=g.latest.obs.iloc[idx].copy(),var=g.latest.var.copy())
        result.obs_names=[f'pred_{i}' for i in range(n)]
        result.uns['method']='unbalanced neural-latent temporal flow and conditional NB decoder'
        result.uns['latent_strength']=latent_strength;result.uns['time_strength']=time_strength
        return result
