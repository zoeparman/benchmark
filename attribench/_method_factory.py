from typing import Dict, Type, Union, Tuple, NewType, List
from torch import nn

from attribench._attribution_method import AttributionMethod


ConfigDict = NewType(
    "ConfigDict",
    Dict[
        str,
        Union[
            Type[AttributionMethod],
            Tuple[Type[AttributionMethod], Dict],
        ],
    ],
)
"""
A ConfigDict is a dictionary mapping strings to either an AttributionMethod,
or a tuple consisting of an AttributionMethod constructor and a dictionary of
keyword arguments to pass to the constructor.
"""


class MethodFactory:
    """
    This class accepts a config dictionary for attribution methods in its
    constructor, and will return a dictionary of ready-to-use AttributionMethod
    objects when called with a model (nn.Module) as argument. This allows
    the attribution methods to be instantiated in subprocesses, which is
    necessary for computing attributions on multiple GPUs, as the methods need
    access to the specific copy of the model for their process.
    """

    def __init__(self, config_dict: ConfigDict) -> None:
        self.config_dict = config_dict

    def __call__(self, model: nn.Module) -> Dict[str, AttributionMethod]:
        result: Dict[str, AttributionMethod] = {}
        for method_name, entry in self.config_dict.items():
            if isinstance(entry, Tuple):
                # Entry consists of constructor and kwargs
                constructor, kwargs = entry
                result[method_name] = constructor(model, **kwargs)
            else:
                # Constructor has no kwargs
                result[method_name] = entry(model)
        return result

    def __len__(self) -> int:
        return len(self.config_dict)

    def get_method_names(self) -> List[str]:
        return list(self.config_dict.keys())
