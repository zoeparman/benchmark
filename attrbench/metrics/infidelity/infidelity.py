from typing import Callable, List, Union, Tuple, Dict
from os import path

import numpy as np
import torch

from attrbench.lib import AttributionWriter
from attrbench.metrics import Metric
from ._compute_perturbations import _compute_perturbations
from ._compute_result import _compute_result
from . import perturbation_generator
from .result import InfidelityResult
import logging


def infidelity(samples: torch.Tensor, labels: torch.Tensor, model: Callable, attrs: np.ndarray,
               pert_generator: perturbation_generator.PerturbationGenerator, num_perturbations: int,
               activation_fns: Union[Tuple[str], str] = "linear",
               writer: AttributionWriter = None) -> Dict:
    if type(activation_fns) == str:
        activation_fns = (activation_fns,)
    pert_vectors, pred_diffs = _compute_perturbations(samples, labels, model, pert_generator,
                                                      num_perturbations, activation_fns, writer)
    return _compute_result(pert_vectors, pred_diffs, attrs)


def _parse_pert_generator(d):
    constructor = getattr(perturbation_generator, d["type"])
    return constructor(**{key: value for key, value in d.items() if key != "type"})


class Infidelity(Metric):
    def __init__(self, model: Callable, method_names: List[str], perturbation_generators: Dict,
                 num_perturbations: int,
                 activation_fns: Union[Tuple[str], str] = "linear", writer_dir: str = None):
        super().__init__(model, method_names)  # We don't pass writer_dir to super because we only use 1 general writer
        self.writers = {"general": AttributionWriter(path.join(writer_dir, "general"))} \
            if writer_dir is not None else None
        self.num_perturbations = num_perturbations
        self.activation_fns = (activation_fns,) if type(activation_fns) == str else activation_fns
        # Process "perturbation-generators" argument: either it is a dictionary of PerturbationGenerator objects,
        # or it is a dictionary that needs to be parsed.
        self.perturbation_generators = {}
        for key, value in perturbation_generators.items():
            if type(value) == perturbation_generator.PerturbationGenerator:
                self.perturbation_generators[key] = value
            else:
                self.perturbation_generators[key] = _parse_pert_generator(value)

        self._result: InfidelityResult = InfidelityResult(method_names + ["_BASELINE"],
                                                          list(perturbation_generators.keys()),
                                                          list(self.activation_fns))

    def run_batch(self, samples, labels, attrs_dict: dict, baseline_attrs: np.ndarray):
        # First calculate perturbation vectors and predictions differences, these can be re-used for all methods
        writer = self.writers["general"] if self.writers is not None else None

        pert_vectors, pred_diffs = {}, {}
        for key, pert_gen in self.perturbation_generators.items():
            p_vectors, p_diffs = _compute_perturbations(samples, labels, self.model, pert_gen,
                                                        self.num_perturbations, self.activation_fns,
                                                        writer)
            pert_vectors[key] = p_vectors
            pred_diffs[key] = p_diffs

        # Compute and append results
        for pert_gen in self.perturbation_generators:
            # Calculate baseline results
            baseline_result = {afn: [] for afn in self.activation_fns}
            for i in range(baseline_attrs.shape[0]):
                bl_result = _compute_result(pert_vectors[pert_gen], pred_diffs[pert_gen], baseline_attrs[i, ...])
                for afn in self.activation_fns:
                    baseline_result[afn].append(bl_result[afn].cpu().detach().numpy())
            for afn in self.activation_fns:
                baseline_result[afn] = np.stack(baseline_result[afn], axis=1)
            self.result.append(baseline_result, perturbation_generator=pert_gen, method="_BASELINE")

            # Calculate actual method results
            for method_name in attrs_dict.keys():
                method_result = _compute_result(pert_vectors[pert_gen], pred_diffs[pert_gen],
                                                attrs_dict[method_name])
                for afn in self.activation_fns:
                    method_result[afn] = method_result[afn].cpu().detach().numpy()
                self.result.append(method_result, perturbation_generator=pert_gen, method=method_name)
        logging.info(f"Appended Infidelity")
