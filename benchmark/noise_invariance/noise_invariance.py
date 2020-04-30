from benchmark.noise_invariance.noise_perturbed_dataset import NoisePerturbedDataset
from typing import Callable, Dict
import numpy as np
import itertools
import torch


def noise_invariance(data: NoisePerturbedDataset, methods: Dict[str, Callable],
                     n_batches=None):
    result = {}
    for m_name in methods:
        method = methods[m_name]
        print(f"Method: {m_name}...")
        diffs = [[] for _ in range(len(data.perturbation_levels))]
        cur_max_diff = 0
        cur_max_diff_examples = {}
        data_generator = enumerate(itertools.islice(data, n_batches)) if n_batches else enumerate(data)
        for batch_idx, batch in data_generator:
            orig = batch["original"]
            labels = batch["labels"]
            orig_attr = method(orig, labels)  # [batch_size, *sample_shape]
            for n_l, noise_level_batch in enumerate(batch["perturbed"]):
                perturbed_attr = method(noise_level_batch, labels)  # [batch_size, *sample_shape]
                avg_diff_per_image = torch.mean(torch.reshape(torch.abs(orig_attr - perturbed_attr), (data.batch_size, -1)),
                                                dim=1)  # [batch_size]
                diffs[n_l].append(avg_diff_per_image.detach().numpy())
                max_diff_idx = torch.argmax(avg_diff_per_image).item()
                if avg_diff_per_image[max_diff_idx] > cur_max_diff:
                    cur_max_diff = avg_diff_per_image[max_diff_idx]
                    cur_max_diff_examples = {
                        "orig": orig[max_diff_idx], "perturbed": noise_level_batch[max_diff_idx],
                        "orig_attr": orig_attr[max_diff_idx], "perturbed_attr": perturbed_attr[max_diff_idx],
                        "noise_level": data.perturbation_levels[n_l]
                    }
        diffs = [np.concatenate(n_l_diffs) for n_l_diffs in diffs]
        diffs = np.vstack(diffs).transpose()
        result[m_name] = {
            "diffs": diffs,  # [n_batches*batch_size, n_levels]
            "max_diff": cur_max_diff_examples,
            "max_diff_exs": cur_max_diff_examples
        }
    return result
