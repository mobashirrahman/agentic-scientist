"""Regression cases: section chains, low-depth matches, and KO same-plane repeats."""
import unittest
import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse
from src.data import duplicate_mask


class DuplicateTests(unittest.TestCase):
    def stage(self, z, xy=None, names=None):
        a = ad.AnnData(sparse.csr_matrix(np.ones((len(z), 2), dtype=np.float32)),
                       obs=pd.DataFrame(index=names or [str(i) for i in range(len(z))]))
        a.layers['counts'] = a.X.copy()
        a.obsm['spatial_3D'] = np.column_stack((np.zeros(len(z)) if xy is None else xy,
                                               np.zeros(len(z)), z))
        return a

    def test_late_section_chain_and_registration_shift(self):
        a = self.stage([0, 15, 30, 90], [0, 40, 65, 0])
        np.testing.assert_array_equal(duplicate_mask(a, 'T2/E8.0.h5ad'), [1, 0, 0, 1])

    def test_early_low_depth_coincidences_are_kept(self):
        a = self.stage([0, 10, 20])
        self.assertTrue(duplicate_mask(a, 'T2/E7.25.h5ad').all())

    def test_same_plane_ko_barcode_repeat(self):
        a = self.stage([0, 0, 10], names=['barcode', 'barcode', 'other'])
        np.testing.assert_array_equal(duplicate_mask(a, 'T3/E9.5_mab21l2_ko.h5ad'), [1, 0, 1])


if __name__ == '__main__':
    unittest.main()
