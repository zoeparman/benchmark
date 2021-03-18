from typing import Callable, List, Tuple, Union

import numpy as np
import torch

from attrbench.lib.masking import Masker
from attrbench.lib.attribution_writer import AttributionWriter
from os import path
from attrbench.metrics import Metric
from ._concat_results import _concat_results
from ._dataset import _IrofIiofDataset
from ._get_predictions import _get_predictions
from .result import IrofResult, IiofResult


def irof(samples: torch.Tensor, labels: torch.Tensor, model: Callable, attrs: np.ndarray,
         masker: Masker, reverse_order: bool = False, activation_fn: Union[Tuple[str], str] = "linear",
         writer=None):
    masking_dataset = _IrofIiofDataset("deletion", samples, masker, writer)
    return _irof(samples, labels, model, attrs, masking_dataset, reverse_order, activation_fn, writer)


def iiof(samples: torch.Tensor, labels: torch.Tensor, model: Callable, attrs: np.ndarray,
         masker: Masker, reverse_order: bool = False, activation_fn: Union[Tuple[str], str] = "linear",
         writer=None):
    masking_dataset = _IrofIiofDataset("insertion", samples, masker, writer)
    return _iiof(samples, labels, model, attrs, masking_dataset, reverse_order, activation_fn, writer)


def _irof(samples: torch.Tensor, labels: torch.Tensor, model: Callable, attrs: np.ndarray,
          masking_dataset, reverse_order: bool, activation_fn: Union[Tuple[str], str] = "linear",
          writer=None):
    if type(activation_fn) == str:
        activation_fn = (activation_fn,)
    masking_dataset.set_attrs(attrs, reverse_order)
    orig_preds, neutral_preds, inter_preds = _get_predictions(samples, labels, model, masking_dataset, activation_fn,
                                                              writer)
    preds = _concat_results(orig_preds, inter_preds, neutral_preds, orig_preds)

    # Calculate AUC for each sample (depends on how many segments each sample had)
    result = {}
    for fn in activation_fn:
        auc = []
        for i in range(samples.shape[0]):
            num_segments = len(np.unique(masking_dataset.segmented_images[i, ...].cpu().numpy()))
            auc.append(np.trapz(preds[fn][i, :num_segments + 1], x=np.linspace(0, 1, num_segments + 1)))
        result[fn] = torch.tensor(auc).unsqueeze(-1)
    return result


def _iiof(samples: torch.Tensor, labels: torch.Tensor, model: Callable, attrs: np.ndarray,
          masking_dataset, reverse_order: bool, activation_fn: Union[Tuple[str], str] = "linear",
          writer=None):
    if type(activation_fn) == str:
        activation_fn = (activation_fn,)
    masking_dataset.set_attrs(attrs, reverse_order)
    orig_preds, neutral_preds, inter_preds = _get_predictions(samples, labels, model, masking_dataset, activation_fn,
                                                              writer)
    preds = _concat_results(neutral_preds, inter_preds, orig_preds, orig_preds)

    # Calculate AUC for each sample (depends on how many segments each sample had)
    result = {}
    for fn in activation_fn:
        auc = []
        for i in range(samples.shape[0]):
            num_segments = len(np.unique(masking_dataset.segmented_images[i, ...].cpu().numpy()))
            auc.append(np.trapz(preds[fn][i, :num_segments + 1], x=np.linspace(0, 1, num_segments + 1)))
        result[fn] = torch.tensor(auc).unsqueeze(-1)
    return result


class _IrofIiof(Metric):
    def __init__(self, model: Callable, method_names: List[str], masker: Masker,
                 mode: Union[Tuple[str], str], activation_fn: Union[Tuple[str], str],
                 result_class: Callable, method_fn: Callable, writer_dir: str = None):
        super().__init__(model, method_names, writer_dir)
        self.masker = masker
        self.modes = (mode,) if type(mode) == str else mode
        for m in self.modes:
            if m not in ("morf", "lerf"):
                raise ValueError(f"Invalid mode: {m}")
        self.activation_fns = (activation_fn,) if type(activation_fn) == str else activation_fn
        self.method_fn = method_fn
        self.result = result_class(method_names, self.modes, self.activation_fns)
        if self.writer_dir is not None:
            self.writers["general"] = AttributionWriter(path.join(self.writer_dir, "general"))

    def run_batch(self, samples, labels, attrs_dict: dict):
        writer = self._get_writer("general")
        masking_dataset = _IrofIiofDataset("insertion", samples, self.masker, writer)
        for method_name in attrs_dict:
            method_result = {}
            for mode in self.modes:
                reverse_order = mode == "lerf"
                method_result[mode] = self.method_fn(samples, labels, self.model, attrs_dict[method_name],
                                                     masking_dataset, reverse_order, self.activation_fns,
                                                     writer=self._get_writer(method_name))
            self.result.append(method_name, method_result)


class Irof(_IrofIiof):
    def __init__(self, model: Callable, method_names: List[str], masker: Masker,
                 mode: Union[Tuple[str], str], activation_fn: Union[Tuple[str], str],
                 writer_dir: str = None):
        super().__init__(model, method_names, masker, mode, activation_fn, IrofResult, _irof, writer_dir)


class Iiof(_IrofIiof):
    def __init__(self, model: Callable, method_names: List[str], masker: Masker,
                 mode: Union[Tuple[str], str], activation_fn: Union[Tuple[str], str],
                 writer_dir: str = None):
        super().__init__(model, method_names, masker, mode, activation_fn, IiofResult, _iiof, writer_dir)
