"""Scientific invariants for interpolation endpoints and lineage-restricted changes."""
import unittest
import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse
from src.models import interpolate, lineage_perturbation


class ModelTests(unittest.TestCase):
    def stage(self):
        a=ad.AnnData(sparse.csr_matrix(np.arange(40,dtype=np.float32).reshape(10,4)/10),
            obs=pd.DataFrame({'celltype':['Neural Tube','Foregut','aPHM','V-CM','Unknown']*2},index=[str(i) for i in range(10)]),
            var=pd.DataFrame(index=['Isl1','Bmp4','Fgf8','Gata4']))
        a.obsm['spatial_3D']=np.arange(30,dtype=np.float32).reshape(10,3)
        return a

    def test_lineage_excludes_neural_and_endoderm(self):
        wt=self.stage()
        pred=lineage_perturbation(wt,strength=.5,n=500)
        idx=pred.obs.source_row.to_numpy()
        unaffected=np.isin(wt.obs.celltype.to_numpy()[idx],['Neural Tube','Foregut','Unknown'])
        np.testing.assert_array_equal(pred.X.toarray()[unaffected],wt.X.toarray()[idx[unaffected]])
        np.testing.assert_array_equal(pred.obsm['spatial_3D'],wt.obsm['spatial_3D'][idx])
        self.assertTrue(np.isfinite(pred.X.data).all())
        self.assertTrue((pred.X.data>=0).all())

    def test_interpolation_preserves_endpoint_expression(self):
        left=self.stage();right=self.stage();right.X*=2
        pred=interpolate(left,right,0.,n=10)
        # Without-replacement endpoint sampling is a permutation of real profiles.
        np.testing.assert_allclose(np.sort(pred.X.toarray(),axis=0),np.sort(left.X.toarray(),axis=0))

    def test_interpolation_rejects_extrapolation(self):
        with self.assertRaises(ValueError):interpolate(self.stage(),self.stage(),1.1)


if __name__=='__main__':unittest.main()
