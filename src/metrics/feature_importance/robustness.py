import numpy as np
from methods import Method
from metrics.feature_importance.util import perturb_dataset


# TODO we now use the average sum of differences (per sample). Consider using variance, or average difference per pixel?
def perturbation_invariance(originals: np.ndarray, perturbed: np.ndarray, labels: np.ndarray, method: Method):
    n_levels = perturbed.shape[0]
    n_batches = perturbed.shape[1]
    all_diffs = []
    for b in range(n_batches):
        print(f"Batch {b}/{n_batches}")
        # [batch_size, *sample_shape]
        orig_attr = method.attribute(originals[b, :], target=labels[b, :]).detach()
        diffs = []
        for l in range(n_levels):
            # [batch_size, *sample_shape]
            shifted_attr = method.attribute(perturbed[l, b, :], target=labels[b, :]).detach()
            # [batch_size]
            attr_diff = np.abs(orig_attr - shifted_attr).reshape((orig_attr.shape[0], -1)).sum(axis=1)
            diffs.append(attr_diff)
        all_diffs.append(np.vstack(diffs))  # [n_levels, batch_size]
    return np.concatenate(all_diffs, axis=1)  # [n_levels, n_batches*batch_size]


def plot_noise_invariance():
    noise_levels = np.linspace(0, 2, 10)
    originals, perturbed, labels = perturb_dataset(dataset, model, n_batches=64,
                                                   perturbation_fn="noise", perturbation_levels=noise_levels)
    fig = plt.figure()
    ax = plt.axes()
    all_diffs = {}
    for key in methods:
        print(f"Calculating Robustness for {key}...")
        diffs = perturbation_invariance(originals, perturbed, labels, methods[key])
        all_diffs[key] = diffs
        ax.plot(noise_levels, diffs.mean(axis=1), label=key)
    ax.legend()


def plot_mean_shift_invariance():
    shift_levels = np.linspace(-.1, .1, 11)
    originals, perturbed, labels = perturb_dataset(dataset, model, n_batches=64,
                                                   perturbation_fn="mean_shift", perturbation_levels=shift_levels)

    fig = plt.figure()
    ax = plt.axes()
    for key in methods:
        print(f"Calculating Mean Shift Invariance for {key}...")
        diffs = perturbation_invariance(originals, perturbed, labels, methods[key])
        ax.plot(shift_levels, diffs.mean(axis=1), label=key)
    ax.legend()

if __name__ == '__main__':
    from models import MNISTCNN
    from datasets import MNIST
    from methods import Saliency, InputXGradient, IntegratedGradients, DeepLift
    import matplotlib.pyplot as plt
    import numpy as np
    dataset = MNIST(batch_size=4, download=False)
    model = MNISTCNN(dataset=dataset)
    methods = {
        "Saliency": Saliency(model.net),
        "InputXGradient": InputXGradient(model.net),
        "IntegratedGradients": IntegratedGradients(model.net),
        "DeepLift": DeepLift(model.net)
    }

    plot_mean_shift_invariance()
    #plot_noise_invariance()
