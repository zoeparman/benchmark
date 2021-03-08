from typing import Callable, List
import numpy as np
from attrbench.lib import mask_segments, segment_samples, AttributionWriter
from attrbench.lib.masking import Masker
from attrbench.metrics import Metric
import torch
import warnings
from torch.utils.data import Dataset, DataLoader

# TODO check if segmented sensitivity-n actually uses segment attributions and not original attributions

class _SensitivityNDataset(Dataset):
    def __init__(self, n_range: np.ndarray, num_subsets: int, samples: np.ndarray, num_features, masker: Masker):
        self.n_range = n_range
        self.num_subsets = num_subsets
        self.samples = samples
        self.masker = masker
        self.masker.initialize_baselines(samples)
        self.num_features = num_features

    def __len__(self):
        return self.n_range.shape[0] * self.num_subsets

    def __getitem__(self, item):
        n = self.n_range[item // self.num_subsets]
        indices = np.tile(np.random.choice(self.num_features, size=n, replace=False), (self.samples.shape[0], 1))
        return self.masker.mask(self.samples, indices), indices, n


class _SegSensNDataset(Dataset):
    def __init__(self, n_range: np.ndarray, num_subsets: int, samples: np.ndarray,
                 masker: Masker, writer=None):
        self.n_range = n_range
        self.num_subsets = num_subsets
        self.samples = samples
        self.masker = masker
        self.masker.initialize_baselines(samples)
        self.segmented_images = segment_samples(samples)
        if writer is not None:
            writer.add_images("segmented samples", self.segmented_images)

    def __len__(self):
        return self.n_range.shape[0] * self.num_subsets

    def __getitem__(self, item):
        n = self.n_range[item // self.num_subsets]
        indices = np.stack([np.random.choice(np.unique(self.segmented_images[i, ...]), size=n, replace=False)
                            for i in range(self.samples.shape[0])])
        return mask_segments(self.samples, self.segmented_images, indices, self.masker), indices, n


def _compute_correlations(sum_of_attrs: np.ndarray, output_diffs: np.ndarray):
    # Calculate correlation between output difference and sum of attribution values
    # Subtract mean
    sum_of_attrs -= sum_of_attrs.mean(axis=1, keepdims=True)
    output_diffs -= output_diffs.mean(axis=1, keepdims=True)
    # Calculate covariances
    cov = (sum_of_attrs * output_diffs).sum(axis=1) / (sum_of_attrs.shape[1] - 1)
    # Divide by product of standard deviations
    # [batch_size]
    denom = sum_of_attrs.std(axis=1) * output_diffs.std(axis=1)
    denom_zero = (denom == 0.)
    if np.any(denom_zero):
        warnings.warn("Zero standard deviation detected.")
    corrcoefs = cov / (sum_of_attrs.std(axis=1) * output_diffs.std(axis=1))
    corrcoefs[denom_zero] = 0.
    return corrcoefs


def _compute_perturbations(samples: torch.Tensor, labels: torch.Tensor, ds: Dataset,
                           model: Callable, n_range, writer=None):
    dl = DataLoader(ds, shuffle=False, num_workers=4, pin_memory=True, batch_size=1)
    device = samples.device
    with torch.no_grad():
        orig_output = model(samples)

    output_diffs = {n: [] for n in n_range}
    removed_indices = {n: [] for n in n_range}
    for i, (batch, indices, n) in enumerate(dl):
        batch = batch[0].to(device).float()
        indices = indices[0].numpy()
        n = n.item()
        with torch.no_grad():
            output = model(batch)
        # TODO this is going to conflict with the per-method writers in Suite
        if writer is not None:
            writer.add_images(f"Masked samples N={n}", batch, global_step=i)
        output_diffs[n].append((orig_output - output).gather(dim=1, index=labels.unsqueeze(-1)))  # [batch_size, 1]
        removed_indices[n].append(indices)  # [batch_size, n]

    for n in n_range:
        output_diffs[n] = torch.cat(output_diffs[n], dim=1).detach().cpu().numpy()  # [batch_size, num_subsets]
        removed_indices[n] = np.stack(removed_indices[n], axis=1)  # [batch_size, num_subsets, n]
    return output_diffs, removed_indices


def _sens_n(samples, labels, attrs, ds, model, n_range, writer=None):
    output_diffs, indices = _compute_perturbations(samples, labels, ds, model, n_range, writer)

    attrs = attrs.reshape(attrs.shape[0], 1, -1)  # [batch_size, 1, -1]
    result = []
    for n in n_range:
        # Calculate sums of attributions
        mask_attrs = np.take_along_axis(attrs, axis=-1, indices=indices[n])  # [batch_size, num_subsets, n]
        sum_of_attrs = mask_attrs.sum(axis=-1)  # [batch_size, num_subsets]
        result.append(_compute_correlations(sum_of_attrs, output_diffs[n]))

    # [batch_size, len(n_range)]
    result = np.stack(result, axis=1)
    return torch.tensor(result)


class SensitivityN(Metric):
    def __init__(self, model: Callable, method_names: List[str], min_subset_size: float, max_subset_size: float,
                 num_steps: int, num_subsets: int, masker: Masker, writer_dir: str = None):
        super().__init__(model, method_names, writer_dir)
        self.min_subset_size = min_subset_size
        self.max_subset_size = max_subset_size
        self.num_steps = num_steps
        self.num_subsets = num_subsets
        self.masker = masker
        self.metadata = {
            "col_index": np.linspace(min_subset_size, max_subset_size, num_steps)
        }

    def run_batch(self, samples, labels, attrs_dict: dict):
        # Get total number of features from attributions dict
        attrs = attrs_dict[next(iter(attrs_dict))]
        num_features = attrs.reshape(attrs.shape[0], -1).shape[1]
        # Calculate n_range
        n_range = (np.linspace(self.min_subset_size, self.max_subset_size, self.num_steps) * num_features).astype(np.int)
        # Create pseudo-dataset
        ds = _SensitivityNDataset(n_range, self.num_subsets, samples.cpu().numpy(), num_features, self.masker)
        # Calculate output diffs and removed indices (we will re-use this for each method)
        output_diffs, indices = _compute_perturbations(samples, labels, ds, self.model, n_range)

        for method_name in attrs_dict:
            if method_name not in self.results:
                self.results[method_name] = []

            attrs = attrs_dict[method_name]
            attrs = attrs.reshape(attrs.shape[0], 1, -1)  # [batch_size, 1, -1]
            method_result = []
            for n in n_range:
                # Calculate sums of attributions
                mask_attrs = np.take_along_axis(attrs, axis=-1, indices=indices[n])  # [batch_size, num_subsets, n]
                sum_of_attrs = mask_attrs.sum(axis=-1)  # [batch_size, num_subsets]
                method_result.append(_compute_correlations(sum_of_attrs, output_diffs[n]))
            method_result = torch.tensor(np.stack(method_result, axis=1))
            self.results[method_name].append(method_result)

    def _run_single_method(self, samples: torch.Tensor, labels: torch.Tensor,
                           attrs: np.ndarray, writer: AttributionWriter = None):
        """The run_batch method is overridden and doesn't use _run_single_method"""
        raise NotImplementedError


class SegSensitivityN(Metric):
    def __init__(self, model: Callable, method_names: List[str], min_subset_size: float, max_subset_size: float,
                 num_steps: int, num_subsets: int, masker: Masker, writer_dir: str = None):
        super().__init__(model, method_names, writer_dir)
        self.min_subset_size = min_subset_size
        self.max_subset_size = max_subset_size
        self.num_steps = num_steps
        self.num_subsets = num_subsets
        # Total number of segments is fixed 100
        self.n_range = (np.linspace(self.min_subset_size, self.max_subset_size, self.num_steps) * 100).astype(np.int)
        self.masker = masker
        self.metadata = {
            "col_index": np.linspace(min_subset_size, max_subset_size, num_steps)
        }

    def run_batch(self, samples, labels, attrs_dict: dict):
        # Create pseudo-dataset
        ds = _SegSensNDataset(self.n_range, self.num_subsets, samples.cpu().numpy(), self.masker)
        # Calculate output diffs and removed indices (we will re-use this for each method)
        output_diffs, indices = _compute_perturbations(samples, labels, ds, self.model, self.n_range)

        for method_name in attrs_dict:
            if method_name not in self.results:
                self.results[method_name] = []
            attrs = attrs_dict[method_name]
            attrs = attrs.reshape(attrs.shape[0], 1, -1)  # [batch_size, 1, -1]
            method_result = []
            for n in self.n_range:
                # Calculate sums of attributions
                mask_attrs = np.take_along_axis(attrs, axis=-1, indices=indices[n])  # [batch_size, num_subsets, n]
                sum_of_attrs = mask_attrs.sum(axis=-1)  # [batch_size, num_subsets]
                method_result.append(_compute_correlations(sum_of_attrs, output_diffs[n]))
            method_result = torch.tensor(np.stack(method_result, axis=1))
            self.results[method_name].append(method_result)

    def _run_single_method(self, samples: torch.Tensor, labels: torch.Tensor,
                           attrs: np.ndarray, writer: AttributionWriter = None):
        """The run_batch method is overridden and doesn't use _run_single_method"""
        raise NotImplementedError


def sensitivity_n(samples: torch.Tensor, labels: torch.Tensor, model: Callable, attrs: np.ndarray,
                  min_subset_size: float, max_subset_size: float, num_steps: int, num_subsets: int,
                  masker: Masker, writer=None):
    num_features = attrs.reshape(attrs.shape[0], -1).shape[1]
    n_range = (np.linspace(min_subset_size, max_subset_size, num_steps) * num_features).astype(np.int)
    ds = _SensitivityNDataset(n_range, num_subsets, samples.cpu().numpy(), num_features, masker)
    return _sens_n(samples, labels, attrs, ds, model, n_range, writer)


def seg_sensitivity_n(samples: torch.Tensor, labels: torch.Tensor, model: Callable, attrs: np.ndarray,
                      min_subset_size: float, max_subset_size: float, num_steps: int, num_subsets: int,
                      masker: Masker, writer=None):
    # Total number of segments is fixed 100
    n_range = (np.linspace(min_subset_size, max_subset_size, num_steps) * 100).astype(np.int)
    ds = _SegSensNDataset(n_range, num_subsets, samples.cpu().numpy(), masker, writer)
    return _sens_n(samples, labels, attrs, ds, model, n_range, writer)