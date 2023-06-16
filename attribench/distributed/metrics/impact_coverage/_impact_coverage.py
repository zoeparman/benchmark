from .._metric import Metric
from .._metric_worker import MetricWorker
from attribench.result import ImpactCoverageResult

from typing import Tuple, Optional
from torch import multiprocessing as mp
from torch.utils.data import Dataset
from attribench.data import IndexDataset
from attribench._method_factory import MethodFactory
from attribench._model_factory import ModelFactory
from multiprocessing.synchronize import Event

from ._impact_coverage_worker import ImpactCoverageWorker


class ImpactCoverage(Metric):
    def __init__(
        self,
        model_factory: ModelFactory,
        dataset: Dataset,
        batch_size: int,
        method_factory: MethodFactory,
        patch_folder: str,
        address="localhost",
        port="12355",
        devices: Optional[Tuple] = None,
    ):
        """Computes the Impact Coverage metric for a given dataset, model, and
        set of attribution methods, using multiple processes.

        Impact Coverage is computed by applying an adversarial patch to the input.
        This patch causes the model to change its prediction.
        The Impact Coverage metric is the intersection over union (IoU) of the
        patch with the top n attributions of the input, where n is the number of
        features masked by the patch. The idea is that, as the patch causes the
        model to change its prediction, the corresponding region in the image
        should be highly relevant to the model's prediction.

        Impact Coverage requires a folder containing adversarial patches. The
        patches should be named as follows: patch_<target>.pt, where <target>
        is the target class of the patch. The target class is the class that
        the model will predict when the patch is applied to the input.

        The number of processes is determined by the number of devices. If
        `devices` is None, then all available devices are used. Samples are
        distributed evenly across the processes.

        To generate adversarial patches, the train_adversarial_patches function
        or TrainAdversarialPatches class can be used.
        TODO add link to train_adversarial_patches function and
        TrainAdversarialPatches class.

        Parameters
        ----------
        model_factory : ModelFactory
            ModelFactory instance or callable that returns a model.
            Used to create a model for each subprocess.
        dataset : Dataset
            Dataset to compute Impact Coverage for.
        batch_size : int
            Batch size to use when computing Impact Coverage.
        method_factory : MethodFactory
            MethodFactory instance or callable that returns a dictionary
            mapping method names to attribution methods, given a model.
        patch_folder : str
            Path to folder containing adversarial patches.
        address : str, optional
            Address to use for the multiprocessing connection,
            by default "localhost"
        port : str, optional
            Port to use for the multiprocessing connection,
            by default "12355"
        devices : Optional[Tuple], optional
            Devices to use. If None, then all available devices are used.
            By default None.
        """
        index_dataset = IndexDataset(dataset)
        super().__init__(
            model_factory,
            index_dataset,
            batch_size,
            address,
            port,
            devices,
        )
        self.method_factory = method_factory
        self.patch_folder = patch_folder
        self._result = ImpactCoverageResult(
            method_factory.get_method_names(), shape=(len(index_dataset),)
        )

    def _create_worker(
        self, queue: mp.Queue, rank: int, all_processes_done: Event
    ) -> MetricWorker:
        return ImpactCoverageWorker(
            queue,
            rank,
            self.world_size,
            all_processes_done,
            self.model_factory,
            self.method_factory,
            self.dataset,
            self.batch_size,
            self.patch_folder,
            self._handle_result if self.world_size == 1 else None,
        )
