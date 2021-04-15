from __future__ import annotations
import numpy as np
import h5py
from typing import List, Dict, Tuple
import pandas as pd
from attrbench.metrics.result import MetricResult


class MaskerActivationMetricResult(MetricResult):
    inverted: bool

    def __init__(self, method_names: List[str], maskers: List[str], activation_fns: List[str]):
        super().__init__(method_names)
        self.maskers = maskers
        self.activation_fns = activation_fns
        self.data = {
            masker: {
                afn: {
                    m_name: None for m_name in method_names
                } for afn in activation_fns} for masker in maskers}

    def append(self, method_name, batch: Dict):
        for masker in batch.keys():
            for afn in batch[masker].keys():
                self.data[masker][afn][method_name].append(batch[masker][afn])

    def add_to_hdf(self, group: h5py.Group):
        for masker in self.maskers:
            masker_group = group.create_group(masker)
            for afn in self.activation_fns:
                afn_group = masker_group.create_group(afn)
                for method_name in self.method_names:
                    ds = afn_group.create_dataset(method_name, data=self.data[masker][afn][method_name])
                    ds.attrs["inverted"] = self.inverted

    @classmethod
    def load_from_hdf(cls, group: h5py.Group) -> MaskerActivationMetricResult:
        maskers = list(group.keys())
        activation_fns = list(group[maskers[0]].keys())
        method_names = list(group[maskers[0]][activation_fns[0]].keys())
        result = cls(method_names, maskers, activation_fns)
        result.data = {
            masker: {
                afn: {
                    m_name: np.array(group[masker][afn][m_name]) for m_name in method_names
                } for afn in activation_fns} for masker in maskers}
        return result

    # TODO make this return a DataFrame with nested indices if mode or activation is not provided
    def get_df(self, *, mode=None, activation=None) -> Tuple[pd.DataFrame, bool]:
        data = {m_name: self._aggregate(self.data[m_name][mode][activation].squeeze())
                for m_name in self.method_names}
        df = pd.DataFrame.from_dict(data)
        return df, self.inverted
