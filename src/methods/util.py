from methods import *

METHODS = {
    "Occlusion": lambda model, **kwargs: Occlusion(model.net, **kwargs),
    "Ablation": lambda model: SimpleCaptumMethod(model.net, "Ablation"),
    "GuidedGradCAM": lambda model: GuidedGradCAM(model),
    "Gradient": lambda model: SimpleCaptumMethod(model.net, "Gradient"),
    "InputXGradient": lambda model: SimpleCaptumMethod(model.net, "InputXGradient"),
    "IntegratedGradients": lambda model: SimpleCaptumMethod(model.net, "IntegratedGradients"),
    "GuidedBackprop": lambda model: SimpleCaptumMethod(model.net, "GuidedBackprop"),
    "Deconvolution": lambda model: SimpleCaptumMethod(model.net, "Deconvolution"),
    "Random": lambda _: Random()
}


def get_all_method_constructors(include_random=True):
    if include_random:
        return METHODS
    return {k: METHODS[k] for k in METHODS.keys() if not k == "Random"}


def get_method_constructors(names=None):
    if names:
        return {k: METHODS[k] for k in names}
    return METHODS