"""Joint spatial/expression VAE with a continuous hurdle likelihood for MERFISH.

Zero probability and positive log-expression have separate likelihood terms;
fractional measurements are never coerced to integer counts.
"""
import json,time
from pathlib import Path
import numpy as np
from scipy import sparse
import torch
from torch import nn
from sklearn.neighbors import NearestNeighbors
from .transport import lineages,geometry,register,normalize_log
from .relative_flow import relative_rates


class HurdleNetwork(nn.Module):
    def __init__(self,genes,groups,latent=32,hidden=128):
        super().__init__();self.genes=genes;self.groups=groups
        self.encoder=nn.Sequential(nn.Linear(genes+groups+4,hidden),nn.LayerNorm(hidden),nn.SiLU(),nn.Linear(hidden,hidden),nn.SiLU())
        self.mean=nn.Linear(hidden,latent);self.logvar=nn.Linear(hidden,latent)
        self.decoder=nn.Sequential(nn.Linear(latent+groups,hidden),nn.LayerNorm(hidden),nn.SiLU(),nn.Linear(hidden,hidden),nn.SiLU())
        self.base=nn.Linear(hidden,genes*3+3)
        self.velocity=nn.Linear(hidden,genes*3+3)
        nn.init.zeros_(self.velocity.weight);nn.init.zeros_(self.velocity.bias)

    def encode(self,x,p,c,t):
        h=self.encoder(torch.cat([x,p,c,t],dim=1))
        return self.mean(h),self.logvar(h).clamp(-8,4)

    def decode(self,z,c,t):
        h=self.decoder(torch.cat([z,c],dim=1))
        output=self.base(h)+t*self.velocity(h)
        detection,mean,scale,coords=torch.split(output,[self.genes,self.genes,self.genes,3],dim=1)
        return detection,torch.nn.functional.softplus(mean)+1e-3,torch.nn.functional.softplus(scale).clamp(.05,2.),coords

    def loss(self,x,p,c,t,beta=1.):
        mean,logvar=self.encode(x,p,c,t)
        z=mean+torch.randn_like(mean)*torch.exp(.5*logvar)
        detection,mu,sigma,coords=self.decode(z,c,t)
        observed=x>0
        bce=torch.nn.functional.binary_cross_entropy_with_logits(detection,observed.float(),reduction='none').sum(1)
        positive=(.5*((x-mu)/sigma).square()+torch.log(sigma))*observed
        nll=(bce+positive.sum(1)).mean()
        spatial=(coords-p).square().sum(1).mean()
        kl=-.5*(1+logvar-mean.square()-logvar.exp()).sum(1).mean()
        return nll+10*spatial+beta*kl,nll.detach(),spatial.detach()


class SpatialGenerator:
    def __init__(self,stages,times,seed=0):
        torch.manual_seed(seed);self.seed=seed;self.stages=stages;self.times=np.array(times,dtype=float)
        self.genes=list(stages[-1].var_names);self.labels=[lineages(a) for a in stages]
        self.groups=np.unique(np.concatenate(self.labels));self.index={c:i for i,c in enumerate(self.groups)}
        self.x=np.vstack([a[:,self.genes].X.toarray() for a in stages]).astype(np.float32)
        self.group_id=np.array([self.index[c] for c in np.concatenate(self.labels)])
        self.onehot=np.eye(len(self.groups),dtype=np.float32)[self.group_id]
        raw=[geometry(a) for a in stages];self.radius=raw[-1][1]
        positions=[]
        for (p,_),labels in zip(raw,self.labels):
            p,_,_=register(p,raw[-1][0],labels,self.labels[-1]);positions.append(p)
        self.p=np.vstack(positions).astype(np.float32)
        self.time_center=float(np.mean(times));self.time_scale=max(float(np.ptp(times)),.5)
        self.t=np.concatenate([np.full(a.n_obs,(t-self.time_center)/self.time_scale,dtype=np.float32) for a,t in zip(stages,times)])[:,None]
        self.offsets=np.r_[0,np.cumsum([a.n_obs for a in stages])]
        probs=np.vstack([(np.bincount([self.index[c] for c in labels],minlength=len(self.groups))+.5)/(len(labels)+.5*len(self.groups)) for labels in self.labels])
        centered_t=self.times-self.times.mean();logits=np.log(probs);logits-=logits.mean(1,keepdims=True)
        rates=centered_t@logits/(centered_t@centered_t+.5)
        latest_freq=np.bincount([self.index[c] for c in self.labels[-1]],minlength=len(self.groups))
        self.growth=relative_rates(rates,latest_freq)
        from scipy.stats import theilslopes
        self.scale_rate=float(np.clip(theilslopes(np.log([r for _,r in raw]),self.times)[0],0,.25))
        self.device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model=HurdleNetwork(len(self.genes),len(self.groups)).to(self.device)

    def batch(self,idx):
        return [torch.as_tensor(a[idx],dtype=torch.float32,device=self.device) for a in [self.x,self.p,self.onehot,self.t]]

    def train(self,directory,epochs=20,batch_size=256):
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        rng=np.random.default_rng(self.seed);train=[];validation=[]
        for start,end in zip(self.offsets[:-1],self.offsets[1:]):
            rows=rng.permutation(np.arange(start,end));n=max(50,int(.05*len(rows)))
            validation.extend(rows[:n]);train.append(rows[n:])
        validation=np.array(validation);optimizer=torch.optim.AdamW(self.model.parameters(),lr=1e-3,weight_decay=1e-4)
        history=[];best=np.inf;best_state=None;start_time=time.time()
        for epoch in range(epochs):
            # Equal stage weights, regardless of the number of sampled cells.
            rows=np.concatenate([rng.choice(stage,min(20000,len(stage)),replace=False) for stage in train]);rng.shuffle(rows)
            self.model.train();losses=[]
            for start in range(0,len(rows),batch_size):
                loss,_,_=self.model.loss(*self.batch(rows[start:start+batch_size]),beta=min(1.,(epoch+1)/10))
                if not torch.isfinite(loss):raise RuntimeError('Non-finite hurdle loss')
                optimizer.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(self.model.parameters(),100.)
                optimizer.step();losses.append(float(loss.detach()))
            self.model.eval();vals=[]
            with torch.no_grad():
                for start in range(0,len(validation),batch_size):
                    loss,_,_=self.model.loss(*self.batch(validation[start:start+batch_size]));vals.append(float(loss))
            value=float(np.mean(vals))
            if value<best:
                best=value;best_state={k:v.detach().cpu().clone() for k,v in self.model.state_dict().items()}
                torch.save(dict(state_dict=best_state,genes=self.genes,groups=self.groups.tolist(),times=self.times.tolist(),
                    seed=self.seed,time_center=self.time_center,time_scale=self.time_scale),directory/'best.pt')
            history.append(dict(epoch=epoch+1,training=float(np.mean(losses)),validation=value,seconds=time.time()-start_time))
            (directory/'history.json').write_text(json.dumps(history,indent=2)+'\n')
            print('HURDLE',history[-1],flush=True)
        self.model.load_state_dict(best_state)
        return history

    def predict(self,horizon,n=3000,seed=101,time_strength=.5,composition=.25,joint=False):
        import anndata as ad
        rng=np.random.default_rng(seed);torch.manual_seed(seed)
        latest=self.stages[-1]
        group=np.array([self.index[c] for c in self.labels[-1]])
        weights=np.exp(composition*np.clip(horizon*self.growth[group],-np.log(2),np.log(2)))
        idx=rng.choice(latest.n_obs,n,replace=True,p=weights/weights.sum())
        arrays=[];motion=[]
        self.model.eval()
        with torch.no_grad():
            for start in range(0,n,128):
                rows=self.offsets[-2]+idx[start:start+128]
                x,p,c,t=self.batch(rows)
                mean,logvar=self.model.encode(x,p,c,t)
                z=mean+torch.randn_like(mean)*torch.exp(.5*logvar)
                detection,mu,sigma,future_p=self.model.decode(z,c,t+time_strength*horizon/self.time_scale)
                _,_,_,current_p=self.model.decode(z,c,t)
                active=torch.rand_like(detection)<torch.sigmoid(detection)
                sample=(mu+sigma*torch.randn_like(mu)).clamp_min(.01)*active
                arrays.append(sample.cpu().numpy());motion.append((future_p-current_p).cpu().numpy())
        out=ad.AnnData(normalize_log(np.vstack(arrays)),obs=latest.obs.iloc[idx].copy(),var=latest.var.copy())
        positions=self.p[self.offsets[-2]+idx].copy()
        if joint:
            displacement=np.vstack(motion)
            neighbors=NearestNeighbors(n_neighbors=8).fit(positions).kneighbors(positions,return_distance=False)[:,1:]
            strain=np.linalg.norm(displacement[:,None]-displacement[neighbors],axis=2)/np.maximum(np.linalg.norm(positions[:,None]-positions[neighbors],axis=2),1e-4)
            displacement*=min(1.,.4/max(float(np.quantile(strain,.95)),1e-8))
            positions+=displacement
        out.obsm['spatial_3D']=(positions*self.radius*np.exp(.5*horizon*self.scale_rate)).astype(np.float32)
        out.obs_names=[f'pred_{i}' for i in range(n)]
        out.uns['method']='joint hurdle-Gaussian expression/spatial VAE with temporal response'
        return out
