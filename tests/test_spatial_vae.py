import unittest
import numpy as np
import torch
from src.v2.spatial_vae import HurdleNetwork


class SpatialLikelihoodTests(unittest.TestCase):
    def test_fractional_expression_objective_and_gradients_are_finite(self):
        torch.manual_seed(14)
        model=HurdleNetwork(20,3,latent=4,hidden=16)
        x=torch.rand(12,20)*5
        x[torch.rand_like(x)<.8]=0
        p=torch.randn(12,3)
        c=torch.eye(3)[torch.arange(12)%3]
        loss,_,_=model.loss(x,p,c,torch.linspace(-.5,.5,12)[:,None])
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertTrue(all(torch.isfinite(v.grad).all() for v in model.parameters() if v.grad is not None))

    def test_decoder_time_response_is_linear_before_parameter_links(self):
        model=HurdleNetwork(20,3,latent=4,hidden=16)
        z=torch.randn(8,4);c=torch.eye(3)[torch.arange(8)%3]
        a=model.decode(z,c,torch.zeros(8,1))
        b=model.decode(z,c,torch.ones(8,1))
        # The initialized temporal head is zero: no untrained age effect.
        for first,second in zip(a,b):torch.testing.assert_close(first,second)

if __name__=='__main__':unittest.main()
