from typing_extensions import override
import h5py
import numpy as np
from numpy import typing as npt
from typing import List, Tuple, Optional
from attrbench.data import RandomAccessNDArrayTree
from attrbench.metrics.result import MetricResult
import pandas as pd


def _aoc(x: np.ndarray, columns: Optional[npt.NDArray] = None):
    if columns is not None:
        x = x[..., columns]
    return x[..., 0] - _auc(x, columns)


def _auc(x: np.ndarray, columns: Optional[npt.NDArray] = None):
    if columns is not None:
        x = x[..., columns]
    l = x.shape[-1] if columns is None else columns.shape[0]
    return np.sum(x, axis=-1) / l


class DeletionResult(MetricResult):
    def __init__(self, method_names: Tuple[str],
                 maskers: Tuple[str], activation_fns: Tuple[str], mode: str,
                 shape: Tuple[int, ...]):
        levels = {"method": method_names, "masker": maskers, "activation_fn": activation_fns}
        level_order = ("method", "masker", "activation_fn")
        super().__init__(method_names, shape, levels, level_order)
        self.mode = mode
    
    @override
    def save(self, path: str):
        """
        Saves the DeletionResult to an HDF5 file.
        """
        super().save(path)
        with h5py.File(path, mode="a") as fp:
            fp.attrs["mode"] = self.mode

    @classmethod
    @override
    def load(cls, path: str) -> "DeletionResult":
        """
        Loads a DeletionResult from an HDF5 file.
        """
        with h5py.File(path, "r") as fp:
            tree = RandomAccessNDArrayTree.load_from_hdf(fp)
            res = DeletionResult(tree.levels["method"], tree.levels["masker"],
                                 tree.levels["activation_fn"], fp.attrs["mode"], tree.shape)
            res.tree = tree
        return res

    @override
    def get_df(self, masker: str, activation_fn: str, agg_fn="auc", methods: List[str] = None,
               columns: Optional[npt.NDArray] = None) -> Tuple[pd.DataFrame, bool]:
        """
        Retrieves a dataframe from the result for a given masker and activation function.
        The dataframe contains a row for each sample and a column for each method.
        Each value is the AUC/AOC for the given method on the given sample.
        :param masker: the masker to use
        :param activation_fn: the activation function to use
        :param agg_fn: either "auc" for AUC or "aoc" for AOC
        :param methods: the methods to include. If None, includes all methods.
        :param columns: the columns used in the AUC/AOC calculation
        :return: dataframe containing results, and boolean indicating if higher is better
        """
        higher_is_better = (self.mode == "morf" and agg_fn == "aoc") or (self.mode == "lerf" and agg_fn == "auc")
        methods = methods if methods is not None else self.method_names
        df_dict = {}
        agg_fns = {"auc": _auc, "aoc": _aoc}
        for method in methods:
            array = self._tree.get(masker=masker, activation_fn=activation_fn, method=method)
            df_dict[method] = agg_fns[agg_fn](array, columns)
        return pd.DataFrame.from_dict(df_dict), higher_is_better
