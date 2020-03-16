from methods import get_all_method_constructors
from vars import DATASET_MODELS
import matplotlib.pyplot as plt
import numpy as np
import torch


DATA_ROOT = "../../data"
DATASET = "MNIST"
DOWNLOAD_DATASET = False
MODEL = "CNN"
BATCH_SIZE = 32
N_BATCHES = 4
N_PIXELS = 128
PIXEL_STEP = 4

dataset_constructor = DATASET_MODELS[DATASET]["constructor"]
model_constructor = DATASET_MODELS[DATASET]["models"][MODEL]
method_constructors = get_all_method_constructors()

model = model_constructor()
dataset = dataset_constructor(batch_size=BATCH_SIZE, shuffle=False, download=DOWNLOAD_DATASET)

fig = plt.figure()
ax = plt.axes()
x = np.array(range(1, N_PIXELS, PIXEL_STEP))
for key in method_constructors:
    print(f"Method: {key}")
    result = []
    iterator = iter(dataset.get_test_data())
    method = method_constructors[key](model)
    for b in range(N_BATCHES):
        print(f"Batch {b+1}/{N_BATCHES}")
        samples, labels = next(iterator)
        batch_result = []
        attrs = method.attribute(samples, target=labels)  # [batch_size, *sample_shape]
        # Flatten each sample in order to sort indices per sample
        attrs = attrs.reshape(attrs.shape[0], -1)  # [batch_size, -1]
        # Sort indices of attrs in ascending order
        sorted_indices = attrs.argsort()  # [batch_size, -1]
        for i in range(1, N_PIXELS, PIXEL_STEP):
            # Get indices of i most important inputs
            to_mask = sorted_indices[:, -i:]  # [batch_size, i]
            unraveled = np.unravel_index(to_mask, samples.shape[1:])
            # Mask i most important inputs
            # Batch_dim: [BATCH_SIZE, i] (made to match unravel_index output)
            batch_dim = np.array(list(range(BATCH_SIZE))*i).reshape(-1, BATCH_SIZE).transpose()
            samples[(batch_dim, *unraveled)] = dataset.mask_value
            # Get predictions for result
            batch_result.append(model.predict(samples).gather(1, labels.reshape(-1, 1)))
        batch_result = torch.cat(batch_result, 1)  # [batch_size, n_pixels]
        result.append(batch_result)
    result = torch.cat(result, 0).detach().mean(dim=0)  # [n_batches*batch_size, n_pixels]
    ax.plot(x, result, label=key)
ax.set_xlabel("Number of masked pixels")
ax.set_ylabel("Classifier confidence")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=3, fancybox=True)
