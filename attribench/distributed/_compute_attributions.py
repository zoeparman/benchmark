from ._message import PartialResultMessage
from ._distributed_computation import DistributedComputation
from ._distributed_sampler import DistributedSampler
from ._worker import Worker
from attribench._model_factory import ModelFactory

from attribench._method_factory import MethodFactory
from attribench.data import AttributionsDatasetWriter, IndexDataset
import torch.multiprocessing as mp
from torch.utils.data import Dataset, DataLoader
from typing import Callable, Tuple, Optional
import torch
from numpy import typing as npt
from tqdm import tqdm
from multiprocessing.synchronize import Event


class AttributionResult:
    def __init__(
        self, indices: npt.NDArray, attributions: npt.NDArray, method_name: str
    ):
        self.indices = indices
        self.attributions = attributions
        self.method_name = method_name


class AttributionsWorker(Worker):
    def __init__(
        self,
        result_queue: mp.Queue,
        rank: int,
        world_size: int,
        all_processes_done: Event,
        model_factory: ModelFactory,
        method_factory: MethodFactory,
        dataset: IndexDataset,
        batch_size: int,
        result_handler: Optional[
            Callable[[PartialResultMessage], None]
        ] = None,
    ):
        super().__init__(
            result_queue,
            rank,
            world_size,
            all_processes_done,
            result_handler,
        )
        self.batch_size = batch_size
        self.dataset = dataset
        self.method_factory = method_factory
        self.model_factory = model_factory

    def work(self):
        sampler = DistributedSampler(
            self.dataset, self.world_size, self.rank, shuffle=False
        )
        dataloader = DataLoader(
            self.dataset,
            sampler=sampler,
            batch_size=self.batch_size,
            num_workers=4,
            pin_memory=True,
        )
        device = torch.device(self.rank)
        model = self.model_factory()
        model.to(device)
        method_dict = self.method_factory(model)

        for batch_indices, batch_x, batch_y in dataloader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            for method_name, method in method_dict.items():
                with torch.no_grad():
                    attrs = method(batch_x, batch_y)
                    result = AttributionResult(
                        batch_indices.cpu().numpy(),
                        attrs.cpu().numpy(),
                        method_name,
                    )
                    self.send_result(PartialResultMessage(self.rank, result))


class ComputeAttributions(DistributedComputation):
    def __init__(
        self,
        model_factory: ModelFactory,
        method_factory: MethodFactory,
        dataset: Dataset,
        batch_size: int,
        writer: AttributionsDatasetWriter,
        address="localhost",
        port="12355",
        devices: Optional[Tuple] = None,
    ):
        """Compute attributions for a dataset using multiple processes.
        The attributions are written to a HDF5 file.
        The number of processes is determined by the number of devices.

        Parameters
        ----------
        model_factory : ModelFactory
            ModelFactory instance or callable that returns a model.
            Used to create a model for each subprocess.
        method_factory : MethodFactory
            MethodFactory instance or callable that returns a dictionary of
            attribution methods, given a model.
        dataset : Dataset
            Torch Dataset to use for computing the attributions.
        batch_size : int
            The batch size to use for computing the attributions.
        writer : AttributionsDatasetWriter
            AttributionsDatasetWriter to write the attributions to.
        address : str, optional
            Address to use for the multiprocessing connection.
            By default "localhost".
        port : str, optional
            Port to use for the multiprocessing connection.
            By default "12355".
        devices : Optional[Tuple], optional
            Devices to use. If None, then all available devices are used.
            By default None.
        """
        super().__init__(address, port, devices)
        self.model_factory = model_factory
        self.method_factory = method_factory
        self.dataset = IndexDataset(dataset)
        self.batch_size = batch_size
        self.writer = writer
        self.prog = None

    def run(self):
        self.prog = tqdm(total=len(self.dataset) * len(self.method_factory))
        super().run()

    def _create_worker(
        self, queue: mp.Queue, rank: int, all_processes_done: Event
    ) -> Worker:
        result_handler = self._handle_result if self.world_size == 1 else None
        return AttributionsWorker(
            queue,
            rank,
            self.world_size,
            all_processes_done,
            self.model_factory,
            self.method_factory,
            self.dataset,
            self.batch_size,
            result_handler,
        )

    def _handle_result(
        self, result_message: PartialResultMessage[AttributionResult]
    ):
        indices = result_message.data.indices
        attributions = result_message.data.attributions
        method_name = result_message.data.method_name
        self.writer.write(indices, attributions, method_name)
        if self.prog is not None:
            self.prog.update(len(indices))