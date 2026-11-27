"""Observed-stage expression prototypes align inconsistent annotation vocabularies.

Clusters are empirical phenotype bins, not asserted developmental lineages.
The evaluation target is not used to construct them.
"""
import numpy as np
from scipy import sparse
from sklearn.cluster import AgglomerativeClustering


def harmonize_phenotypes(stages,clusters=12):
    genes=list(stages[-1].var_names)
    prototypes=[];keys=[];counts=[]
    for k,a in enumerate(stages):
        labels=a.obs['celltype'].astype(str).to_numpy()
        stage_mean=np.asarray(a[:,genes].X.mean(0)).ravel()
        for label in np.unique(labels):
            rows=labels==label
            mean=np.asarray(a[:,genes].X[rows].mean(0)).ravel()
            prototypes.append((mean-stage_mean)*rows.sum()/(rows.sum()+30.))
            keys.append((k,label));counts.append(int(rows.sum()))
    prototypes=np.vstack(prototypes)
    scale=np.maximum(prototypes.std(0),.3)
    features=prototypes/scale
    # A tiny fixed column prevents undefined cosine distance for a zero profile.
    features=np.column_stack([features,np.full(len(features),1e-4)])
    assigned=AgglomerativeClustering(n_clusters=min(clusters,len(features)),metric='cosine',linkage='average').fit_predict(features)
    mapping={key:f'phenotype_{c}' for key,c in zip(keys,assigned)}
    result=[]
    for k,a in enumerate(stages):
        out=a.copy();out.obs['original_celltype']=out.obs['celltype'].astype(str)
        out.obs['celltype']=[mapping[(k,str(c))] for c in out.obs['original_celltype']]
        result.append(out)
    audit=dict(clusters=clusters,annotation_mapping=[dict(stage=k,label=label,phenotype=mapping[(k,label)],cells=n)
        for (k,label),n in zip(keys,counts)],
        markers={f'phenotype_{c}':[genes[j] for j in np.argsort(prototypes[assigned==c].mean(0))[-10:][::-1]] for c in np.unique(assigned)})
    return result,audit
