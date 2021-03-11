from __future__ import annotations
import torch
import numpy as np
import h5py
from typing import List, Union, Dict, Tuple


class MetricResult:
    def __init__(self, method_names: List[str]):
        self.method_names = method_names
        # Data contains either a list of batches or a single numpy array (if the result was loaded from HDF)
        self.data: Dict[str, Union[List, np.ndarray]] = {m_name: [] for m_name in method_names}

    def add_to_hdf(self, group: h5py.Group):
        for method_name in self.method_names:
            if type(self.data[method_name]) == list:
                group.create_dataset(method_name, data=torch.cat(self.data[method_name]).numpy())
            else:
                group.create_dataset(method_name, data=self.data[method_name])

    def append(self, method_name, batch):
        self.data[method_name].append(batch)

    @classmethod
    def load_from_hdf(cls, group: h5py.Group) -> MetricResult:
        method_names = list(group.keys())
        result = cls(method_names)
        result.data = {m_name: np.array(group[m_name]) for m_name in method_names}
        return result


class ModeActivationMetricResult(MetricResult):
    def __init__(self, method_names: List[str], modes: Tuple[str], activation_fn: Tuple[str]):
        super().__init__(method_names)
        self.modes = modes
        self.activation_fn = activation_fn
        self.data = {m_name: {mode: {afn: [] for afn in activation_fn} for mode in modes}
                     for m_name in self.method_names}

    def append(self, method_name, batch: Dict):
        for mode in batch.keys():
            for afn in batch[mode].keys():
                self.data[method_name][mode][afn].append(batch[mode][afn])

    def add_to_hdf(self, group: h5py.Group):
        for method_name in self.method_names:
            method_group = group.create_group(method_name)
            for mode in self.modes:
                mode_group = method_group.create_group(mode)
                for afn in self.activation_fn:
                    if type(self.data[method_name][mode][afn]) == list:
                        mode_group.create_dataset(afn, data=torch.cat(self.data[method_name][mode][afn]).numpy())
                    else:
                        mode_group.create_dataset(afn, data=self.data[method_name][mode][afn])

    @classmethod
    def load_from_hdf(cls, group: h5py.Group) -> MetricResult:
        method_names = list(group.keys())
        modes = tuple(group[method_names[0]].keys())
        activation_fn = tuple(group[method_names[0]][modes[0]].keys())
        result = cls(method_names, modes, activation_fn)
        result.data = {
            m_name:
                {mode:
                    {afn: np.array(group[m_name][mode][afn]) for afn in activation_fn}
                 for mode in modes}
            for m_name in method_names
        }
        return result
