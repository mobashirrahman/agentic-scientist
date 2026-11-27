import unittest
import numpy as np
from src.v2.relative_flow import relative_rates


class RelativeFlowTests(unittest.TestCase):
    def test_common_logit_slope_does_not_change_clipped_weights(self):
        rates=np.array([2.,3.,4.]);p=np.array([.2,.6,.2])
        first=np.exp(np.clip(relative_rates(rates,p),-np.log(2),np.log(2)))
        shifted=np.exp(np.clip(relative_rates(rates+123.,p),-np.log(2),np.log(2)))
        np.testing.assert_allclose(first/first.sum(),shifted/shifted.sum(),atol=1e-12)
        self.assertGreater(first.max()-first.min(),.5)

if __name__=='__main__':unittest.main()
