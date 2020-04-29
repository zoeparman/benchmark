import numpy as np
from util import datasets, models, methods
from os import path
import torch

DEVICE = "cuda"
DATASET = "CIFAR10"
DOWNLOAD_DATASET = False
MODEL = "resnet20"
BATCH_SIZE = 16
N_BATCHES = 16
N_SUBSETS = 100
MASK_RANGE = range(1, 500, 50)
# MASK_RANGE = range(1, 700, 50)
TAU = 0.5
data_root = "../../data"
normalize_attrs = True

dataset = datasets.Cifar(batch_size=BATCH_SIZE, data_location=path.join(data_root, DATASET))
model = models.CifarResnet(version=MODEL, params_loc=path.join(data_root, f"models/cifar10_{MODEL}.pth"),
                           output_logits=True)
model.to(DEVICE)
model.eval()

attribution_methods = {
    "GuidedGradCAM": methods.GuidedGradCAM(model, model.get_last_conv_layer(), normalize=normalize_attrs),
    "Gradient": methods.Gradient(model, normalize=normalize_attrs),
    "InputXGradient": methods.InputXGradient(model, normalize=normalize_attrs),
    "IntegratedGradients": methods.IntegratedGradients(model, normalize=normalize_attrs),
    "GuidedBackprop": methods.GuidedBackprop(model, normalize=normalize_attrs),
    "Deconvolution": methods.Deconvolution(model, normalize=normalize_attrs),
    "Random": methods.Random(normalize=normalize_attrs)
}

iterator = iter(dataset.get_test_data())
original_predictions = []
method_predictions = {m_name: {n: [] for n in MASK_RANGE} for m_name in attribution_methods}

for b in range(N_BATCHES):
    samples, labels = next(iterator)
    samples, labels = torch.tensor(samples), torch.tensor(labels)
    samples = samples.to(DEVICE, non_blocking=True)
    labels = labels.to(DEVICE, non_blocking=True)
    original_predictions.append(model(samples).detach().cpu().numpy())  # collect original predictions

    for m_name in method_predictions:
        masked_samples = samples.clone()
        method = attribution_methods[m_name]
        # TODO targets should be the actual predictions of the model, not the ground truth?
        attrs = method(samples, target=labels)
        attrs = attrs.reshape(attrs.shape[0], -1)
        sorted_indices = attrs.argsort().cpu()
        for n in MASK_RANGE:
            to_mask = sorted_indices[:, -n:]  # [batch_size, i]
            unraveled = np.unravel_index(to_mask, samples.shape[1:])

            assert ((np.array(list(range(BATCH_SIZE)) * n).reshape(-1, BATCH_SIZE).transpose() ==
                     np.column_stack([range(BATCH_SIZE) for i in range(n)])).all()
                    )  # just making sure i'm not breaking things

            batch_dim = np.column_stack([range(BATCH_SIZE) for i in range(n)])  # more readable then previous code?
            masked_samples[(batch_dim, *unraveled)] = dataset.mask_value
            pred = model(masked_samples)
            method_predictions[m_name][n].append(pred.detach().cpu().numpy())

original_predictions = np.vstack(original_predictions)  # to np array of shape (#images, #classes)
original_pred_labels = original_predictions.argmax(axis=1)

method_pred_labels = {}
# collect labels and raw predictions in single list for each method and masking level
for m in method_predictions:
    method_predictions[m] = {k: np.vstack([batch_pred for batch_pred in v]) for k, v in method_predictions[m].items()}
    method_pred_labels[m] = {k: pred.argmax(axis=1) for k, pred in method_predictions[m].items()}

I_score = {}
I_strict_score = {}

for m in method_predictions:
    strict_scores = {}
    scores = {}
    for mask_value, labels in method_pred_labels[m].items():
        # I_{strict} = 1/n * sum_n (y_i' \neq y_i)
        strict_bools = labels != original_pred_labels
        strict_scores[mask_value] = np.count_nonzero(strict_bools) / len(strict_bools)

        predictions = method_predictions[m][mask_value]
        # I = 1/n * sum_n ((y_i' \neq y_i) \vee (z_i' \leq z_i)
        bools = original_predictions[np.arange(len(original_pred_labels)), original_pred_labels] * TAU >= \
                predictions[np.arange(len(labels)), labels]
        scores[mask_value] = np.count_nonzero(strict_bools + bools) / len(bools)
    I_strict_score[m] = strict_scores
    I_score[m] = scores

# strict impact score
"""
report = Report(list(method_constructors.keys()))
x = np.array(MASK_RANGE)
for m_name in METHODS:
    # all_corrs has shape [N_BATCHES, len(MASK_RANGE)]
    report.add_summary_line(x, list(I_strict_score[m_name].values()), label=m_name)
report.render(x_label="Number of masked pixels", y_label="Impact Score (Strict)",
              y_range=(0, 1))

# impact score
report = Report(list(method_constructors.keys()))
x = np.array(MASK_RANGE)
for m_name in METHODS:
    # all_corrs has shape [N_BATCHES, len(MASK_RANGE)]
    report.add_summary_line(x, list(I_score[m_name].values()), label=m_name)
report.render(x_label="Number of masked pixels", y_label="Impact Score",
              y_range=(0, 1))
"""
