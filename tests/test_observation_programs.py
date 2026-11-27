import unittest
import numpy as np
from src.v2.observation import detection_mask
from src.v2.programs import ProgramPerturbation
from test_v2 import stage


class ObservationTests(unittest.TestCase):
    def test_identity_detection_is_exact(self):
        x=np.random.default_rng(4).uniform(.1,5,(20,50)).astype(np.float32)
        np.testing.assert_array_equal(detection_mask(x,np.ones(20),np.random.default_rng(9)),x)

    def test_detection_controls_expected_support_without_creating_genes(self):
        rng=np.random.default_rng(11)
        x=np.tile(np.r_[np.zeros(10),np.linspace(.2,5,40)],(2000,1)).astype(np.float32)
        result=detection_mask(x,np.full(len(x),.7),rng)
        self.assertLess(abs((result>0).sum(1).mean()-28),.3)
        self.assertFalse((result[:,:10]>0).any())
        self.assertTrue((result>0).any(1).all())

    def test_program_keeps_noncardiac_profiles_and_coordinates_exact(self):
        wt=stage();beta=np.linspace(-.4,.4,wt.n_vars)
        pred=ProgramPerturbation(wt,beta).predict(strength=.5,n=500)
        idx=pred.obs.source_row.to_numpy();mask=wt.obs.celltype.to_numpy()[idx]!='V-CM'
        np.testing.assert_array_equal(pred.X.toarray()[mask],wt.X.toarray()[idx[mask]])
        np.testing.assert_array_equal(pred.obsm['spatial_3D'],wt.obsm['spatial_3D'][idx])

if __name__=='__main__':unittest.main()
