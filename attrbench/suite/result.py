from os import path, makedirs
import pandas as pd
import numpy as np
import h5py


# TODO this class should be used by Suite to keep track of its results
class Result:
    def __init__(self, data, metadata, num_samples, seed=None, images=None, attributions=None):
        self.data = data
        self.metadata = metadata
        self.num_samples = num_samples
        self.seed = seed
        self.images = images
        self.attributions = attributions

    def save_hdf(self,filename):

        # if dir not exists: create dir
        if not path.exists(path.dirname(filename)) and path.dirname(filename) != '' :
            makedirs(path.dirname(filename))

        with h5py.File(filename, "w") as fp:
            if self.seed is not None:
                fp.attrs["seed"] = self.seed
            if self.images is not None:
                fp.create_dataset("images", data=self.images)
            # Save attributions if specified
            if self.attributions:
                attr_group = fp.create_group("attributions")
                for method_name in self.attributions.keys():
                    attr_group.create_dataset(method_name, data=self.attributions[method_name])
            # Save results
            # results group is laid out as {metric}/{method}
            # Each metric group has the according metadata as attributes
            result_group = fp.create_group("results")
            result_group.attrs["num_samples"] = self.num_samples

            for metric_name in self.data.keys():
                metric = self.data[metric_name]
                metric_group = result_group.create_group(metric_name)

                for attr_key, attr_value in self.metadata[metric_name].items():
                    metric_group.attrs[attr_key] = attr_value

                for method_name in metric.keys():
                    method_results = metric[method_name]
                    metric_group.create_dataset(method_name, data=method_results)


    @staticmethod
    def load_hdf(filename):
        if path.isfile(filename):
            images, attributions = None, None
            with h5py.File(filename, "r") as fp:
                if "images" in fp.keys():
                    images = np.array(fp["images"])
                if "attributions" in fp.keys():
                    attributions = {
                        method: np.array(fp["attributions"][method])
                        for method in fp["attributions"].keys()
                    }
                data = {
                    metric: {
                        method: pd.DataFrame(fp["results"][metric][method])
                        for method in fp["results"][metric].keys()
                    } for metric in fp["results"].keys()
                }
                metadata = {
                    metric: {
                        key: fp["results"][metric].attrs[key]
                        for key in fp["results"][metric].attrs.keys()
                    } for metric in fp["results"].keys()
                }
                num_samples = fp["results"].attrs["num_samples"]
                seed = fp.attrs.get("seed", None)
            return Result(data, metadata, num_samples, seed, images, attributions)
        else:
            raise ValueError(f"File {filename} does not exist")

    def get_metrics(self):
        return list(self.data.keys())

    def get_methods(self):
        return list(self.data[self.get_metrics()[0]].keys())

if __name__ == '__main__':
    ###################
    # just for testing
    ###################

    result = Result.load_hdf('D:\Project\Benchmark_branch_axel\out\\results\cifar10.h5')

    result.save_hdf('test.h5')

    result2 = Result.load_hdf('test.h5')

    print('testing')