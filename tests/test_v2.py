"""Transport invariants: masses, expression preservation, registration and lineage masks."""
import unittest
import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse
from src.v2.transport import sinkhorn_unbalanced,SpatialInterpolant,LineageDelay,geometry,register,lineages
from src.v2.cvae import recover_counts,CountVAE
from src.models import interpolate
import torch


def stage(seed=0):
 rng=np.random.default_rng(seed)
 counts=rng.poisson(1.,size=(90,50)).astype(np.float32);counts[:,0]=1
 x=np.log1p(10000*counts/counts.sum(1,keepdims=True))
 labels=np.repeat(['V-CM','Neural Tube','Foregut'],30)
 a=ad.AnnData(sparse.csr_matrix(x),obs=pd.DataFrame({'celltype':labels},index=[str(i) for i in range(90)]),
              var=pd.DataFrame(index=[f'g{i}' for i in range(50)]))
 a.obsm['spatial_3D']=rng.normal(size=(90,3))+np.repeat(np.eye(3)*3,30,axis=0)
 return a


class TransportTests(unittest.TestCase):
 def test_zero_cost_preserves_unit_product_mass(self):
  a=np.array([.2,.8]);b=np.array([.3,.3,.4])
  coupling,info=sinkhorn_unbalanced(a,b,np.zeros((2,3)))
  np.testing.assert_allclose(coupling,np.outer(a,b),atol=1e-10)
  self.assertTrue(info['converged'])

 def test_registered_mixture_preserves_every_expression_row(self):
  left,right=stage(0),stage(1)
  model=SpatialInterpolant(left,right,support=60)
  pred=model.predict(.4,n=60,seed=42,mode='transport')
  baseline=interpolate(left,right,.4,n=60,seed=42)
  np.testing.assert_array_equal(pred.X.toarray(),baseline.X.toarray())
  self.assertTrue(np.isfinite(pred.obsm['spatial_3D']).all())

 def test_proper_rigid_registration_recovers_known_frame(self):
  a=stage();p,radius=geometry(a)
  q=np.array([[0.,-1,0],[1,0,0],[0,0,1]])
  aligned,rotation,info=register(p@q,p,lineages(a),lineages(a))
  np.testing.assert_allclose(aligned,p,atol=1e-6)
  self.assertAlmostEqual(np.linalg.det(rotation),1.,places=6)

 def test_delay_leaves_neural_and_endoderm_exactly_unchanged(self):
  earlier,wt=stage(0),stage(1)
  model=LineageDelay(earlier,wt)
  pred=model.predict(delay=.125,n=150)
  idx=pred.obs.source_row.to_numpy()
  mask=wt.obs.celltype.to_numpy()[idx]!='V-CM'
  np.testing.assert_array_equal(pred.X.toarray()[mask],wt.X.toarray()[idx[mask]])
  np.testing.assert_array_equal(pred.obsm['spatial_3D'],wt.obsm['spatial_3D'][idx])

 def test_count_recovery_round_trip(self):
  a=stage()
  counts,audit=recover_counts(a)
  np.testing.assert_allclose(counts.data,np.rint(counts.data))
  self.assertLess(audit['max_log_roundtrip_error'],5e-5)

 def test_negative_binomial_objective_has_finite_gradients(self):
  model=CountVAE(12,50,3,np.ones(50,dtype=bool),latent=4,hidden=16)
  counts=torch.poisson(torch.ones(8,50));groups=torch.eye(3)[torch.arange(8)%3]
  loss,_,_=model.loss(torch.randn(8,12),counts,groups,torch.zeros(8,1))
  loss.backward()
  self.assertTrue(torch.isfinite(loss))
  self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))

if __name__=='__main__':unittest.main()
