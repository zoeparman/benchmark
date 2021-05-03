from typing import List

import h5py
import numpy as np

from attrbench.metrics import MaskerActivationMetricResult
from attrbench.lib import NDArrayTree


class SensitivityNResult(MaskerActivationMetricResult):
    inverted = False

    def __init__(self, method_names: List[str], maskers: List[str], activation_fns: List[str], index: np.ndarray):
        super().__init__(method_names, maskers, activation_fns)
        self.index = index

    def add_to_hdf(self, group: h5py.Group):
        group.attrs["index"] = self.index
        super().add_to_hdf(group)

    @classmethod
    def load_from_hdf(cls, group: h5py.Group) -> MaskerActivationMetricResult:
        maskers = list(group.keys())
        activation_fns = list(group[maskers[0]].keys())
        method_names = list(group[maskers[0]][activation_fns[0]].keys())
        result = cls(method_names, maskers, activation_fns, group.attrs["index"])
        result.tree = NDArrayTree.load_from_hdf(["masker", "activation_fn", "method"], group)
        return result

    def _postproc_fn(self, x):
        return np.mean(x, axis=1)


class SegSensitivityNResult(SensitivityNResult):
    pass
