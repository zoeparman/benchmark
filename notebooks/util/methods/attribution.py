import torch
from .util import normalize_attributions


class AttributionMethod:
    def __init__(self, absolute, normalize=True, aggregation_fn=None):
        self.normalize = normalize
        self.is_absolute = absolute
        aggregation_fns = {
            "avg": lambda x: torch.mean(x, dim=1)
        }  # TODO add max abs value
        self.aggregation_fn = aggregation_fns.get(aggregation_fn, None)

    def _attribute(self, x, target):
        raise NotImplementedError

    def __call__(self, x, target):
        attrs = self._attribute(x, target)
        if self.aggregation_fn:
            attrs = self.aggregation_fn(attrs)
        if self.normalize:
            attrs = normalize_attributions(attrs)
        return attrs


# This is not really an attribution technique, just to establish a baseline
class Random(AttributionMethod):
    def __init__(self, **kwargs):
        super(Random, self).__init__(False, **kwargs)

    def _attribute(self, x, target):
        return torch.rand(*x.shape) * 2 - 1

