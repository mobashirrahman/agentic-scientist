"""Compact count-aware conditional VAE with an explicit linear time response.

Trains only on released input stages. Recovered T1 counts assume the smallest
positive abundance is one UMI; round-trip checks audit that assumption's scale
consistency, not unique identifiability of original sequencing depth.
"""
from pathlib import Path
import json
import time
import numpy as np
from scipy import sparse
import torch
from torch import nn
from .transport import lineages


def recover_counts(a):
    x=sparse.csr_matrix(a.X,copy=True)
    x.eliminate_zeros()
    counts=x.copy().astype(np.float32)
    max_error=0.;max_integer_error=0.
    for i in range(a.n_obs):
        start,end=x.indptr[i:i+2]
        if start==end:raise ValueError('Empty expression row')
        abundance=np.expm1(x.data[start:end].astype(np.float64))
        unit=abundance.min()
        inferred=abundance/unit
        integer=np.rint(inferred)
        max_integer_error=max(max_integer_error,float(np.max(np.abs(inferred-integer))))
        reconstruction=np.log1p(10000*integer/integer.sum())
        max_error=max(max_error,float(np.max(np.abs(reconstruction-x.data[start:end]))))
        counts.data[start:end]=integer
    if max_error>5e-5 or max_integer_error>.05:
        raise ValueError(f'Count recovery failed: log error {max_error}, integer error {max_integer_error}')
    return counts,dict(max_log_roundtrip_error=max_error,max_integer_error=max_integer_error,
                       assumption='smallest observed positive abundance = one UMI')


class CountVAE(nn.Module):
    def __init__(self,n_features,n_genes,n_groups,active,latent=32,hidden=256):
        super().__init__()
        self.encoder=nn.Sequential(nn.Linear(n_features+n_groups+1,hidden),nn.LayerNorm(hidden),nn.SiLU(),
                                   nn.Linear(hidden,hidden),nn.SiLU())
        self.mean=nn.Linear(hidden,latent)
        self.logvar=nn.Linear(hidden,latent)
        self.decoder=nn.Sequential(nn.Linear(latent+n_groups,hidden),nn.LayerNorm(hidden),nn.SiLU(),
                                   nn.Linear(hidden,n_genes))
        self.time_loading=nn.Parameter(torch.zeros(n_groups,n_genes))
        self.log_theta=nn.Parameter(torch.ones(n_genes))
        self.register_buffer('active',torch.as_tensor(active,dtype=torch.bool))

    def encode(self,x,groups,t):
        h=self.encoder(torch.cat([x,groups,t],dim=1))
        return self.mean(h),self.logvar(h).clamp(-8,5)

    def decode(self,z,groups,t,library):
        logits=self.decoder(torch.cat([z,groups],dim=1))+t*(groups@self.time_loading)
        logits=logits.masked_fill(~self.active,-1e4)
        mu=torch.softmax(logits,dim=1)*library
        theta=torch.nn.functional.softplus(self.log_theta).clamp(.05,100.)
        return mu.clamp_min(1e-8),theta

    def loss(self,features,counts,groups,t,beta=1.):
        mean,logvar=self.encode(features,groups,t)
        z=mean+torch.randn_like(mean)*torch.exp(.5*logvar)
        mu,theta=self.decode(z,groups,t,counts.sum(1,keepdim=True).clamp_min(1.))
        logtheta=torch.log(theta)
        logtotal=torch.log(theta+mu)
        log_prob=torch.lgamma(counts+theta)-torch.lgamma(theta)-torch.lgamma(counts+1)
        log_prob+=theta*(logtheta-logtotal)+counts*(torch.log(mu)-logtotal)
        reconstruction=-log_prob[:,self.active].sum(1).mean()
        kl=-.5*(1+logvar-mean.square()-logvar.exp()).sum(1).mean()
        # Small temporal penalty limits unsupported extrapolation; it does not
        # assume latent coordinates from different stages are interchangeable.
        temporal=.01*self.time_loading.square().sum()/len(self.time_loading)
        return reconstruction+beta*kl+temporal,reconstruction.detach(),kl.detach()


class ConditionalGenerator:
    def __init__(self,stages,times,seed=0,latent=32,hidden=256):
        torch.manual_seed(seed)
        np.random.seed(seed)
        self.seed=seed;self.times=list(times);self.genes=list(stages[0].var_names)
        self.labels=[lineages(a) for a in stages]
        self.groups=np.unique(np.concatenate(self.labels))
        self.group_index={g:i for i,g in enumerate(self.groups)}
        self.x=sparse.vstack([a[:,self.genes].X for a in stages],format='csr')
        recovered=[recover_counts(a[:,self.genes]) for a in stages]
        self.recovery=[audit for _,audit in recovered]
        self.counts=sparse.vstack([c for c,_ in recovered],format='csr')
        self.library=np.asarray(self.counts.sum(1)).ravel()
        all_labels=np.concatenate(self.labels)
        self.group_id=np.array([self.group_index[g] for g in all_labels])
        self.onehot=np.eye(len(self.groups),dtype=np.float32)[self.group_id]
        self.time_center=float(np.mean(times));self.time_scale=max(float(max(times)-min(times)),.5)
        self.t=np.concatenate([np.full(a.n_obs,(t-self.time_center)/self.time_scale,dtype=np.float32) for a,t in zip(stages,times)])[:,None]
        mean=np.asarray(self.x.mean(0)).ravel()
        variance=np.maximum(np.asarray(self.x.power(2).mean(0)).ravel()-mean**2,0)
        self.features=np.argsort(variance)[-min(2000,self.x.shape[1]):]
        self.feature_mean=mean[self.features]
        self.feature_scale=np.maximum(np.sqrt(variance[self.features]),.25)
        active=np.asarray(self.counts.sum(0)).ravel()>0
        self.device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model=CountVAE(len(self.features),len(self.genes),len(self.groups),active,latent,hidden).to(self.device)
        self.config=dict(latent=latent,hidden=hidden,n_genes=len(self.genes),n_features=len(self.features),groups=self.groups.tolist(),
            seed=seed,times=self.times,device=str(self.device),torch_version=torch.__version__)
        self.latest=stages[-1]
        self.latest_offset=sum(a.n_obs for a in stages[:-1])

    def batch(self,idx):
        x=(self.x[idx][:,self.features].toarray()-self.feature_mean)/self.feature_scale
        arrays=[x,self.counts[idx].toarray(),self.onehot[idx],self.t[idx]]
        return [torch.as_tensor(a,dtype=torch.float32,device=self.device) for a in arrays]

    def train(self,directory,epochs=30,batch_size=64):
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        rng=np.random.default_rng(self.seed)
        perm=rng.permutation(self.x.shape[0]);validation=perm[:max(100,int(.05*len(perm)))];train=perm[len(validation):]
        optimizer=torch.optim.AdamW(self.model.parameters(),lr=1e-3,weight_decay=1e-5)
        history=[];best=np.inf;best_state=None;start=time.time()
        for epoch in range(epochs):
            self.model.train();losses=[]
            beta=min(1.,(epoch+1)/10)
            for begin in range(0,len(train),batch_size):
                if begin==0:train=rng.permutation(train)
                idx=train[begin:begin+batch_size]
                loss,reconstruction,kl=self.model.loss(*self.batch(idx),beta=beta)
                if not torch.isfinite(loss):raise RuntimeError('Non-finite VAE loss')
                optimizer.zero_grad(set_to_none=True);loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(),2000.)
                optimizer.step();losses.append(float(loss.detach()))
            self.model.eval();val=[]
            with torch.no_grad():
                for begin in range(0,len(validation),batch_size):
                    loss,_,_=self.model.loss(*self.batch(validation[begin:begin+batch_size]),beta=1.)
                    val.append(float(loss))
            score=float(np.mean(val))
            history.append(dict(epoch=epoch+1,train_loss=float(np.mean(losses)),validation_loss=score,beta=beta,seconds=time.time()-start))
            if score<best:
                best=score;best_state={k:v.detach().cpu().clone() for k,v in self.model.state_dict().items()}
                torch.save(dict(state_dict=best_state,config=self.config,features=self.features,feature_mean=self.feature_mean,
                    feature_scale=self.feature_scale,genes=self.genes,time_center=self.time_center,time_scale=self.time_scale,
                    recovery=self.recovery),directory/'best.pt')
            torch.save(dict(model=self.model.state_dict(),optimizer=optimizer.state_dict(),epoch=epoch+1,
                rng_state=rng.bit_generator.state,torch_rng=torch.get_rng_state(),
                cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []),directory/'resume.pt')
            (directory/'history.json').write_text(json.dumps(history,indent=2)+'\n')
            (directory/'config.json').write_text(json.dumps(dict(self.config,recovery=self.recovery,best_validation=best),indent=2)+'\n')
            print('CVAE',history[-1],flush=True)
        self.model.load_state_dict(best_state)
        return history

    def predict(self,horizon,n=3000,seed=42,time_strength=.5,composition=.25):
        import anndata as ad
        torch.manual_seed(seed)
        rng=np.random.default_rng(seed)
        latest_labels=self.labels[-1]
        p=np.array([np.mean(labels[:,None]==self.groups[None,:],axis=0) for labels in self.labels])
        # Jeffreys smoothing acknowledges finite samples without inventing births.
        smoothed=np.vstack([(np.bincount([self.group_index[g] for g in labels],minlength=len(self.groups))+.5)/(len(labels)+.5*len(self.groups)) for labels in self.labels])
        rate=np.clip(np.log(smoothed[-1]/smoothed[-2])/(self.times[-1]-self.times[-2]),-np.log(2),np.log(2))
        weights=np.exp(composition*min(horizon,2.)*rate[[self.group_index[g] for g in latest_labels]])
        idx=rng.choice(self.latest.n_obs,n,replace=True,p=weights/weights.sum())
        chunks=[]
        self.model.eval()
        with torch.no_grad():
            for begin in range(0,n,64):
                rows=self.latest_offset+idx[begin:begin+64]
                features,counts,groups,t=self.batch(rows)
                mean,logvar=self.model.encode(features,groups,t)
                z=mean+torch.randn_like(mean)*torch.exp(.5*logvar)
                future=t+time_strength*horizon/self.time_scale
                mu,theta=self.model.decode(z,groups,future,counts.sum(1,keepdim=True))
                # Gamma-Poisson sampling preserves count dispersion and zeros.
                rate_sample=torch.distributions.Gamma(theta,theta/mu).sample()
                sample=torch.poisson(rate_sample)
                values=torch.log1p(10000*sample/sample.sum(1,keepdim=True).clamp_min(1.))
                chunks.append(values.cpu().numpy())
        out=ad.AnnData(sparse.csr_matrix(np.vstack(chunks)),obs=self.latest.obs.iloc[idx].copy(),var=self.latest.var.copy())
        out.obs_names=[f'pred_{i}' for i in range(n)]
        out.uns['method']='conditional negative-binomial VAE with linear lineage/time response'
        out.uns['time_strength']=time_strength
        return out
