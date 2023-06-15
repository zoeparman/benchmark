from ._distributed_sampler import DistributedSampler
from ._distributed_computation import DistributedComputation
from ._message import PartialResultMessage
from ._worker import Worker
from attribench import ModelFactory
from tqdm import tqdm
from attribench.data import HDF5DatasetWriter
from attribench.functional._select_samples import _select_samples_batch
from typing import Callable, Tuple, Optional, NoReturn
from torch.utils.data import Dataset, DataLoader
import torch.multiprocessing as mp
import torch
from numpy import typing as npt
from torch import nn
from multiprocessing.synchronize import Event


class SamplesResult:
    def __init__(self, samples: npt.NDArray, labels: npt.NDArray):
        self.samples = samples
        self.labels = labels


class SampleSelectionWorker(Worker):
    def __init__(
        self,
        result_queue: mp.Queue,
        rank: int,
        world_size: int,
        all_processes_done: Event,
        sufficient_samples: Event,
        batch_size: int,
        dataset: Dataset,
        model_factory: Callable[[], nn.Module],
        result_handler: Optional[
            Callable[[PartialResultMessage], None]
        ] = None,
    ):
        super().__init__(
            result_queue, rank, world_size, all_processes_done, result_handler
        )
        self.sufficient_samples = sufficient_samples
        self.model_factory = model_factory
        self.dataset = dataset
        self.batch_size = batch_size

    def work(self):
        sampler = DistributedSampler(self.dataset, self.world_size, self.rank)
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
        it = iter(dataloader)

        for batch_x, batch_y in it:
            correct_samples, correct_labels = _select_samples_batch(
                batch_x, batch_y, model, device
            )
            result = SamplesResult(
                correct_samples.cpu().numpy(), correct_labels.cpu().numpy()
            )
            self.send_result(PartialResultMessage(self.rank, result))
            if self.sufficient_samples.is_set():
                break


class SelectSamples(DistributedComputation):
    def __init__(
        self,
        model_factory: ModelFactory,
        dataset: Dataset,
        writer: HDF5DatasetWriter,
        num_samples: int,
        batch_size: int,
        address: str = "localhost",
        port: str = "12355",
        devices: Optional[Tuple] = None,
    ):
        """Select correctly classified samples from a dataset and write them
        to a HDF5 file. This is done in a distributed fashion, i.e. each
        subprocess selects a part of the samples and writes them to the
        HDF5 file. The number of processes is determined by the number of
        devices.

        Parameters
        ----------
        model_factory : ModelFactory
            ModelFactory instance or callable that returns a model.
            Used to instantiate a model for each subprocess.
        dataset : Dataset
            Torch Dataset containing the samples and labels.
        writer : HDF5DatasetWriter
            Writer to write the samples and labels to.
        num_samples : int
            Number of correctly classified samples to select.
        batch_size : int
            Batch size per subprocess to use for the dataloader.
        address : str, optional
            Address to use for the multiprocessing connection,
            by default "localhost"
        port : str, optional
            Port to use for the multiprocessing connection, by default "12355"
        devices : Tuple, optional
            Devices to use. If None, then all available devices are used.
            By default None.
        """
        super().__init__(address, port, devices)
        self.model_factory = model_factory
        self.dataset = dataset
        self.writer = writer
        self.num_samples = num_samples
        self.batch_size = batch_size
        self.sufficient_samples = self.ctx.Event()
        self.count = 0
        self.prog: tqdm | None = None

    def _create_worker(
        self, queue: mp.Queue, rank: int, all_processes_done: Event
    ):
        result_handler = self._handle_result if self.world_size == 1 else None
        return SampleSelectionWorker(
            queue,
            rank,
            self.world_size,
            all_processes_done,
            self.sufficient_samples,
            self.batch_size,
            self.dataset,
            self.model_factory,
            result_handler,
        )

    def run(self):
        self.prog = tqdm(total=self.num_samples)
        super().run()

    def _handle_result(self, result: PartialResultMessage[SamplesResult]):
        samples = result.data.samples
        labels = result.data.labels
        if self.count + samples.shape[0] > self.num_samples:
            samples = samples[: self.num_samples - self.count]
            labels = labels[: self.num_samples - self.count]
            self.sufficient_samples.set()
        self.writer.write(samples, labels)
        self.count += samples.shape[0]
        if self.prog is not None:
            self.prog.update(samples.shape[0])