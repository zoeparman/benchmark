from typing import Tuple
import h5py
from numpy import typing as npt


class AttributionsDatasetWriter:
    def __init__(self, path: str, num_samples: int, sample_shape: Tuple):
        self.path = path
        self.num_samples: int = num_samples
        self.sample_shape: Tuple = sample_shape
        self.file = h5py.File(self.path, "w")
        self.file.attrs["num_samples"] = self.num_samples
        self.file.attrs["sample_shape"] = self.sample_shape

    def write(self, indices: npt.NDArray, attributions: npt.NDArray,
              method_name: str):
        if method_name not in self.file.keys():
            self.file.create_dataset(
                method_name, shape=(self.num_samples, *self.sample_shape)
            )
        self.file[method_name][indices, ...] = attributions