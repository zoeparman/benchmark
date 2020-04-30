from os import path
import numpy as np
import torch
from imgaug import augmenters as iaa
from sklearn.utils import class_weight
import pandas as pd
import math


def _move_axis_lambda(x, *args):
    # for use in transformation. python cant pickle lambda functions, so named function is needed
    # if we want dataloader to use multiprocessing
    return np.moveaxis(x, 3, 1) / 255


def _get_aptos_dataset(data_loc, imsize=224):
    # Creates numpy arrays for train and test data from csv and npy files
    train = pd.read_csv(path.join(data_loc, 'train_aptos_2019.csv'))
    train['id_code'] = train['id_code'] + '.png'

    test = pd.read_csv(path.join(data_loc, 'test_aptos_2019.csv'))
    test['id_code'] = test['id_code'] + '.png'

    x_train_path = path.join(data_loc, 'Train_aptos_2019_' + str(imsize) + '.npy')
    if not path.exists(x_train_path):
        raise FileNotFoundError('file ' + x_train_path +
                                ' does not exist. Please create the file or use a different image size')
    x_train = np.load(path.join(data_loc, 'Train_aptos_2019_' + str(imsize) + '.npy'))
    x_test = np.load(path.join(data_loc, 'Test_aptos_2019_' + str(imsize) + '.npy'))

    y_train = train['diagnosis'].tolist()
    y_test = test['diagnosis'].tolist()
    class_weights = class_weight.compute_class_weight(
        'balanced',
        np.unique(train['diagnosis'].tolist()),
        train['diagnosis'].tolist())
    class_weights = np.array(class_weights, dtype=np.float)
    return x_train, y_train, x_test, y_test, class_weights


class Aptos:
    class DataLoader:
        def __init__(self, x_array, y_array, batch_size, transforms):
            self.x_array = x_array
            self.y_array = y_array
            self.batch_size = batch_size
            self.transforms = transforms

        def __iter__(self):
            for i in range(0, self.x_array.shape[0], self.batch_size):
                samples = self.transforms(images=self.x_array[i:i + self.batch_size])
                labels = self.y_array[i:i + self.batch_size]
                yield torch.tensor(samples), torch.tensor(labels)

        def __len__(self):
            return math.ceil(self.x_array.shape[0] / self.batch_size)

    def __init__(self, batch_size, data_location, img_size=224):
        self.batch_size = batch_size
        self.x_train, self.y_train, self.x_test, self.y_test, self.class_weights = \
            _get_aptos_dataset(imsize=img_size, data_loc=data_location)
        self.sample_shape = (3, img_size, img_size)
        self.mask_value = 127/255

        self.train_transforms = iaa.Sequential([
            iaa.Affine(rotate=(-30, 30), scale=(0.95, 1.25), translate_percent=(-0.1, 0.1), shear=(-5, 5), mode="constant",
                       cval=127),
            iaa.Fliplr(0.5),
            iaa.Lambda(_move_axis_lambda)
        ])
        self.test_transforms = iaa.Lambda(_move_axis_lambda)

    def get_train_data(self):
        return Aptos.DataLoader(self.x_train, self.y_train, self.batch_size, self.train_transforms)

    def get_test_data(self):
        return Aptos.DataLoader(self.x_test, self.y_test, self.batch_size, self.test_transforms)

    def get_sample_shape(self):
        return self.sample_shape