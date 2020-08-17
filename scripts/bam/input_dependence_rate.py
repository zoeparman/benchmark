from os import path
import torch
import argparse
from torch.utils.data import DataLoader
import itertools

# This block allows us to import from the benchmark folder,
# as if it was a package installed using pip
import os
import sys
module_path = os.path.abspath(os.path.join('..'))
if module_path not in sys.path:
    sys.path.append(module_path)

from attrbench import attribution, models
from attrbench.evaluation.bam import input_dependence_rate, BAMDataset

parser = argparse.ArgumentParser()
parser.add_argument("--model-type", type=str, default="Resnet")
parser.add_argument("--model-params", type=str, default="../../data/models/BAM/scene/resnet18/")
parser.add_argument("--model-version", type=str, default="resnet18")
parser.add_argument("--batch-size", type=int, default=64)
parser.add_argument("--num-batches", type=int, default=-1)
parser.add_argument("--cuda", type=bool, default=True)
parser.add_argument("--data-root", type=str, default="../../data")
parser.add_argument("--output-file", type=str, default="result.json")
args = parser.parse_args()
device = "cuda" if args.cuda and torch.cuda.is_available() else "cpu"

if not path.isdir(args.model_params):
    sys.exit("--model-params must be directory containing .pt files")

if path.isfile(args.output_file) and path.getsize(args.output_file) > 0:
    sys.exit("Experiment output file is not empty")

with open(args.output_file, "w") as f:
    if not f.writable():
        sys.exit("Output file is not writable")

dataset = BAMDataset(path.join(args.data_root, "BAM"), train=False, include_orig_scene=True, include_mask=True)
dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=4)
if args.num_batches > 0:
    dataloader = itertools.islice(dataloader, args.num_batches)

kwargs = {
    "normalize": False,  # Shouldn't normalized, we are comparing across "different" samples
    "aggregation_fn": "avg"
}

models, methods = [], []
for param_file in os.listdir(args.model_params):
    model_constructor = getattr(models, args.model_type)
    model_kwargs = {
        "params_loc": args.model_params,
        "output_logits": args.use_logits,
        "num_classes": dataset.num_classes
    }
    if args.model_version:
        model_kwargs["version"] = args.model_version
    model = model_constructor(**model_kwargs)
    model.eval()

    attribution_methods = {
        "Gradient": attribution.Gradient(model, **kwargs),
        "SmoothGrad": attribution.SmoothGrad(model, **kwargs),
        "InputXGradient": attribution.InputXGradient(model, **kwargs),
        "IntegratedGradients": attribution.IntegratedGradients(model, **kwargs),
        "GuidedBackprop": attribution.GuidedBackprop(model, **kwargs),
        "Deconvolution": attribution.Deconvolution(model, **kwargs),
        #"Ablation": attribution.Ablation(model, **kwargs),
        "GuidedGradCAM": attribution.GuidedGradCAM(model, model.get_last_conv_layer(), dataset.sample_shape[1:], **kwargs),
        "GradCAM": attribution.GradCAM(model, model.get_last_conv_layer(), dataset.sample_shape[1:], **kwargs)
    }

    models.append(model)
    methods.append(attribution_methods)

result = input_dependence_rate(dataloader, models, methods, device)
result.save_json(args.output_file)
