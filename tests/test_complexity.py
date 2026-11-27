"""Observation-sampler invariants independent of knockout scoring."""
import unittest
import numpy as np
from tests.test_v2 import stage
from src.v2.complexity import ComplexityPerturbation


class ComplexityTests(unittest.TestCase):
 def setUp(self):
  self.wt=stage(1)
  self.model=ComplexityPerturbation(stage(0),self.wt)

 def test_stratum_mass_is_preserved_for_both_weight_directions(self):
  for strength in [-.5,0.,.5,1.]:
   probabilities=self.model.probabilities(strength)
   self.assertAlmostEqual(probabilities.sum(),1.)
   for rows in self.model.strata:
    self.assertAlmostEqual(probabilities[rows].sum(),len(rows)/self.wt.n_obs)
  np.testing.assert_allclose(self.model.probabilities(0.),1/self.wt.n_obs)

 def test_pure_sampler_preserves_exact_source_profiles_and_coordinates(self):
  prediction=self.model.predict(strength=.5,n=200,seed=201)
  rows=prediction.obs.source_row.to_numpy()
  np.testing.assert_array_equal(prediction.X.toarray(),self.wt.X.toarray()[rows])
  np.testing.assert_array_equal(prediction.obsm['spatial_3D'],self.wt.obsm['spatial_3D'][rows])

if __name__=='__main__':unittest.main()
