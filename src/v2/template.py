"""Coherent spatial templates with unchanged sampled expression profiles."""
import numpy as np
from sklearn.neighbors import NearestNeighbors
from .transport import SpatialInterpolant


class CoherentTemplate(SpatialInterpolant):
    def predict_template(self,fraction,n=3000,seed=101,template='left'):
        if template not in ('left','right'):raise ValueError(template)
        result=self.predict(fraction,n,seed,mode='registered')
        donor=0 if template=='left' else 1
        positions=(self.pa,self.pb)
        latent=(self.za,self.zb)
        labels=(self.la,self.lb)
        spatial=positions[donor]
        context=np.column_stack([2*spatial,latent[donor]/np.sqrt(latent[donor].shape[1])])
        nn=NearestNeighbors(n_neighbors=min(24,len(context))).fit(context)
        endpoint=result.obs.source_endpoint.to_numpy()
        source_rows=result.obs.source_row.to_numpy()
        mapped=np.empty((n,3),dtype=float)
        rng=np.random.default_rng(seed+9001)
        for source in (0,1):
            mask=endpoint==source;idx=source_rows[mask]
            if source==donor:
                mapped[mask]=positions[source][idx]
                continue
            # The learned cross-stage displacement locates the query in the
            # donor anatomy; final positions are actual donor points, not an
            # average cloud or an independently scattered bounding box.
            projected=positions[source][idx]+(self.delta_a if source==0 else self.delta_b)[idx]
            query=np.column_stack([2*projected,latent[source][idx]/np.sqrt(latent[source].shape[1])])
            distance,neighbors=nn.kneighbors(query)
            penalty=(labels[source][idx,None]!=labels[donor][neighbors])*.75
            logits=-(distance+penalty)/np.maximum(np.median(distance,axis=1,keepdims=True),.1)
            weights=np.exp(logits-logits.max(1,keepdims=True));weights/=weights.sum(1,keepdims=True)
            selection=(rng.random(len(idx))[:,None]>weights.cumsum(1)).sum(1)
            selection=np.minimum(selection,neighbors.shape[1]-1)
            chosen=neighbors[np.arange(len(idx)),selection]
            mapped[mask]=spatial[chosen]
        radius=np.exp((1-fraction)*np.log(self.ra)+fraction*np.log(self.rb))
        result.obsm['spatial_3D']=(mapped*radius).astype(np.float32)
        result.uns['method']='expression-preserving coherent '+template+' spatial template'
        return result
