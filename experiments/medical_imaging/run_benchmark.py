import argparse
import torch
from experiments.medical_imaging.dataset_models import get_dataset_model
from experiments.lib import get_methods
from attrbench.suite import Suite
from torch.utils.data import DataLoader


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=str)
    parser.add_argument("-d", "--dataset", type=str, required=True)
    parser.add_argument("-b", "--batch-size", type=int, required=True)
    parser.add_argument("-n", "--num-samples", type=int, required=True)
    parser.add_argument("-c", "--cuda", action="store_true")
    parser.add_argument("-o", "--output", type=str, required=True)
    parser.add_argument("--methods", type=str, nargs="+", default=None)
    # Parse arguments
    args = parser.parse_args()
    device = "cuda" if torch.cuda.is_available() and args.cuda else "cpu"

    # Get dataset, model, methods
    ds, model, sample_shape = get_dataset_model(args.dataset)
    methods_dict = get_methods(model,
                               aggregation_fn="avg",
                               normalize=True,
                               methods=args.methods,
                               batch_size=args.batch_size,
                               sample_shape=sample_shape)

    # Run BM suite and save result to disk
    bm_suite = Suite(model,
                     methods_dict,
                     DataLoader(ds, batch_size=args.batch_size, shuffle=True, num_workers=4),
                     device)
    bm_suite.load_config(args.config)
    bm_suite.run(args.num_samples, verbose=True)
    bm_suite.save_result(args.output)