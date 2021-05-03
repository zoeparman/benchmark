from attrbench.suite import SuiteResult
import numpy as np
from typing import List


class DFExtractor:
    def __init__(self, res_obj: SuiteResult, exclude_methods=None):
        self.res_obj = res_obj
        self.exclude_methods = exclude_methods
        self.dfs = {}

    def add_metric(self, name, metric, mode=None, activation=None, log_transform=False):
        if name in self.dfs:
            raise ValueError(f"Metric {name} is already present")
        kwargs = {}
        if mode is not None:
            kwargs["mode"] = mode
        if activation is not None:
            kwargs["activation"] = activation
        df, inverted = self.res_obj.metric_results[metric].get_df(**kwargs)
        if log_transform:
            df = df.apply(np.log)
        if self.exclude_methods is not None:
            df = df[df.columns.difference(self.exclude_methods)]
        self.dfs[name] = (df, inverted)

    def add_metrics(self, metric_dict, log_transform=False):
        for key, item in metric_dict.items():
            self.add_metric(key, **item, log_transform=log_transform)

    def get_dfs(self):
        return self.dfs

    def add_infidelity(self, mode, activation):
        self.add_metrics({
            f"infid-gauss-{activation}-{mode}": dict(metric="infidelity_gaussian",
                                                     mode=mode, activation=activation),
            f"infid-seg-{activation}-{mode}": dict(metric="infidelity_seg",
                                                   mode=mode, activation=activation)
        }, log_transform=True)

    def compare_maskers(self, maskers: List[str], activation: str, metric_group=None):
        all_metric_groups = ["deletion_until_flip", "insertion", "deletion", "irof", "iiof", "seg_sensitivity_n", "sensitivity_n"]
        m_groups = all_metric_groups if metric_group is None else [metric_group]
        for masker in maskers:
            for m_group in m_groups:
                if m_group == "deletion_until_flip":
                    self.add_metric(f"deletion_until_flip-{masker}", f"masker_{masker}.deletion_until_flip")
                else:
                    self.add_metric(f"{m_group}-{masker}", f"masker_{masker}.{m_group}", activation=activation)

    def compare_activations(self, activations: List[str], masker: str, metric_group=None):
        all_metric_groups = ["deletion_until_flip", "insertion", "deletion", "irof", "iiof", "seg_sensitivity_n", "sensitivity_n"]
        m_groups = all_metric_groups if metric_group is None else [metric_group]
        for activation in activations:
            for m_group in m_groups:
                self.add_metric(f"{m_group}-{activation}", f"masker_{masker}.{m_group}", activation=activation)