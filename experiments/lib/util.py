from experiments.lib.datasets import Cifar, MNIST, ImageNette, Aptos
from experiments.lib.models import Alexnet, BasicCNN, BasicMLP, Densenet, Mobilenet_v2, Resnet, Squeezenet, Vgg
from experiments.lib.attribution import *
from os import path

_DATA_LOC = path.join(path.dirname(__file__), "../../data")

_DATASET_MODELS = {
    "MNIST": {
        "ds": lambda: MNIST(path.join(_DATA_LOC, "MNIST"), train=False),
        "mask_range": list(range(0, 28*28//2, 25)),
        "models": {
            "CNN": lambda: BasicCNN(10, path.join(_DATA_LOC, "models/MNIST/cnn.pt"))
        }
    },
    "CIFAR10": {
        "ds": lambda: Cifar(path.join(_DATA_LOC, "CIFAR10"), train=False),
        "mask_range": list(range(0, 32*32//2, 30)),
        "models": {
            "resnet18": lambda: Resnet("resnet18", 10, path.join(_DATA_LOC, "models/CIFAR10/resnet18.pt"))
        }
    },
    "ImageNette": {
        "ds": lambda: ImageNette(path.join(_DATA_LOC, "imagenette2"), train=False),
        "mask_range": list(range(0, 224*224//2, 1000)),
        "models": {
            "alexnet": lambda: Alexnet(10, path.join(_DATA_LOC, "models/ImageNette/alexnet.pt")),
            "densenet": lambda: Densenet("densenet121", 10, path.join(_DATA_LOC, "models/ImageNette/densenet121.pt")),
            "mobilenet_v2": lambda: Mobilenet_v2(10, path.join(_DATA_LOC, "models/ImageNette/mobilenet_v2.pt")),
            "resnet18": lambda: Resnet("resnet18", 10, path.join(_DATA_LOC, "models/ImageNette/resnet18.pt")),
            "squeezenet1_0": lambda: Squeezenet("squeezenet1_0.pt", 10, path.join(_DATA_LOC, "models/ImageNette/squeezenet1_0.pt")),
            "vgg11_bn": lambda: Vgg("vgg11_bn", 10, path.join(_DATA_LOC, "models/ImageNette/vgg11_bn.pt"))
        }
    },
    "Aptos": {
        "ds": lambda: Aptos(path.join(_DATA_LOC, "APTOS"), train=False),
        "mask_range": list(range(0, 224*224//2, 1000)),
        "models": {
            "densenet121": lambda: Densenet("densenet121", 5, path.join(_DATA_LOC, "models/Aptos/densenet121.pt"))
        }
    }
}

_METHODS = {
    "Gradient": lambda model: Gradient(model),
    "SmoothGrad": lambda model: SmoothGrad(model),
    "InputXGradient": lambda model: InputXGradient(model),
    "IntegratedGradients": lambda model, bs: IntegratedGradients(model, internal_batch_size=bs),
    "GuidedBackprop": lambda model: GuidedBackprop(model),
    "Deconvolution": lambda model: Deconvolution(model),
    "GuidedGradCAM": lambda model, shape: GuidedGradCAM(model, model.get_last_conv_layer(), upsample_shape=shape),
    "GradCAM": lambda model, shape: GradCAM(model, model.get_last_conv_layer(), shape),
    "Random": lambda: Random(),
    "EdgeDetection": lambda: EdgeDetection()
}


def get_ds_model(dataset, model):
    if dataset not in _DATASET_MODELS:
        raise ValueError(f"Dataset {dataset} not found.")
    ds_data = _DATASET_MODELS[dataset]
    if model not in ds_data["models"]:
        raise ValueError(f"Model {model} not found for {dataset}.")
    ds_obj = ds_data["ds"]()
    model_obj = ds_data["models"][model]()
    return ds_obj, model_obj


def get_methods(model, batch_size, sample_shape, methods=None):
    def _instantiate(m_name):
        if m_name == "IntegratedGradients":
            return _METHODS[m_name](model, batch_size)
        elif m_name in ["GuidedGradCAM", "GradCAM"]:
            return _METHODS[m_name](model, sample_shape)
        elif m_name in ["Random", "EdgeDetection"]:
            return _METHODS[m_name]()
        else:
            return _METHODS[m_name](model)
    keys = methods if methods else list(_METHODS.keys())
    return {key: _instantiate(key) for key in keys}


def get_mask_range(dataset):
    return _DATASET_MODELS[dataset]["mask_range"]