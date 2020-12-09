import torch
from attrbench import functional


class Metric:
    def __init__(self, model, methods):
        self.model = model
        self.methods = methods
        self.results = {method_name: [] for method_name in methods}

    def run_batch(self, samples, labels):
        """
        Runs the metric for a given batch, for all methods, and saves result internally
        """
        for method_name in self.methods:
            method = self.methods[method_name]
            self.results[method_name].append(self._run_single_method(samples, labels, method))

    def get_results(self):
        """
        Returns the complete results for all batches and all methods in a dictionary
        """
        raise NotImplementedError

    def _run_single_method(self, samples, labels, method):
        raise NotImplementedError


class DeletionUntilFlip(Metric):
    def __init__(self, model, methods, step_size, masking_policy):
        super().__init__(model, methods)
        self.step_size = step_size
        self.masking_policy = masking_policy

    def _run_single_method(self, samples, labels, method):
        return functional.deletion_until_flip(samples, labels, self.model, method, self.step_size, self.masking_policy)

    def get_results(self):
        raise NotImplementedError


class ImpactCoverage(Metric):
    def __init__(self, model, methods, patch, target_label):
        super().__init__(model, methods)
        self.patch = torch.load(patch) if type(patch) == str else patch
        self.target_label = target_label

    def _run_single_method(self, samples, labels, method):
        return functional.impact_coverage(samples, labels, self.model, method, self.patch, self.target_label)

    def get_results(self):
        raise NotImplementedError


class ImpactScore(Metric):
    def __init__(self, model, methods, mask_range, strict, masking_policy, tau=None):
        super().__init__(model, methods)
        self.mask_range = mask_range
        self.strict = strict
        self.masking_policy = masking_policy
        self.tau = tau

    def _run_single_method(self, samples, labels, method):
        return functional.impact_score(samples, labels, self.model, method, self.mask_range,
                                       self.strict, self.masking_policy, self.tau)

    def get_results(self):
        raise NotImplementedError


class Insertion(Metric):
    def __init__(self, model, methods, mask_range, masking_policy):
        super().__init__(model, methods)
        self.mask_range = mask_range
        self.masking_policy = masking_policy

    def _run_single_method(self, samples, labels, method):
        return functional.insertion(samples, labels, self.model, method, self.mask_range, self.masking_policy)

    def get_results(self):
        raise NotImplementedError


class Deletion(Metric):
    def __init__(self, model, methods, mask_range, masking_policy):
        super().__init__(model, methods)
        self.mask_range = mask_range
        self.masking_policy = masking_policy

    def _run_single_method(self, samples, labels, method):
        return functional.deletion(samples, labels, self.model, method, self.mask_range, self.masking_policy)

    def get_results(self):
        raise NotImplementedError


class Infidelity(Metric):
    def __init__(self, model, methods, perturbation_range, num_perturbations):
        super().__init__(model, methods)
        self.perturbation_range = perturbation_range
        self.num_perturbations = num_perturbations

    def _run_single_method(self, samples, labels, method):
        return functional.infidelity(samples, labels, self.model, method,
                                     self.perturbation_range, self.num_perturbations)

    def get_results(self):
        raise NotImplementedError


class MaxSensitivity(Metric):
    def __init__(self, model, methods, perturbation_range, num_perturbations):
        super().__init__(model, methods)
        self.perturbation_range = perturbation_range
        self.num_perturbations = num_perturbations

    def _run_single_method(self, samples, labels, method):
        return functional.max_sensitivity(samples, labels, method, self.perturbation_range, self.num_perturbations)

    def get_results(self):
        raise NotImplementedError


class SensitivityN(Metric):
    def __init__(self, model, methods, n_range, num_subsets, masking_policy):
        super().__init__(model, methods)
        self.n_range = n_range
        self.num_subsets = num_subsets
        self.masking_policy = masking_policy

    def _run_single_method(self, samples, labels, method):
        return functional.sensitivity_n(samples, labels, self.model, method,
                                        self.n_range, self.num_subsets, self.masking_policy)

    def get_results(self):
        raise NotImplementedError