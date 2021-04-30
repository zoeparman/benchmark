import numpy as np
import h5py
from typing import List, Tuple, Dict, Callable


class NDArrayTree:
    def __init__(self, levels: List[Tuple[str, List[str]]]):
        self.levels = levels

        def _initialize_data(data=None, depth=0):
            if data is None:
                data = {}
            _, keys = levels[depth]
            for key in keys:
                if depth < len(levels) - 1:
                    data[key] = {}
                    _initialize_data(data[key], depth + 1)
                else:
                    data[key] = None
            return data

        self.data = _initialize_data()

    def append(self, new_data: Dict, axis=0, **kwargs):
        def _append_rec(_data, _new_data, depth=0):
            level_name = self.levels[depth][0]
            # If the level name is found in kwargs,
            if level_name in kwargs.keys():
                # If level name found in kwargs, descend down the corresponding branch
                # In this case we pass _new_data instead of _new_data[key], since this level is not present
                # in the data dict
                key = kwargs[level_name]
                if type(_data[key]) == dict:
                    _append_rec(_data[key], _new_data, depth + 1)
                elif type(_data[key]) == np.ndarray or _data[key] is None:
                    _data[key] = _new_data if _data[key] is None else np.concatenate(
                        [_data[key], _new_data], axis=axis)
                else:
                    raise ValueError(f"Invalid type: {type(_data[key])}")
            else:
                # If level name not found in kwargs, loop over each key in current level
                for key in _new_data:
                    if type(_data[key]) == dict:
                        # Descend down the tree (passing down a level both in _data and in _new_data)
                        _append_rec(_data[key], _new_data[key], depth + 1)
                    elif type(_data[key]) == np.ndarray or _data[key] is None:
                        # Base case: leaf nodes are ndarrays
                        _data[key] = _new_data[key] if _data[key] is None else np.concatenate(
                            [_data[key], _new_data[key]], axis=axis)
                    else:
                        raise ValueError(f"Invalid type: {type(_data[key])}")
        _append_rec(self.data, new_data)

    def apply(self, fn: Callable):
        def _apply_rec(_cur_data):
            for key in _cur_data:
                if type(_cur_data[key]) == dict:
                    # Descend down the tree
                    _apply_rec(_cur_data[key])
                elif type(_cur_data[key]) == np.ndarray:
                    _cur_data[key] = fn(_cur_data[key])

        _apply_rec(self.data)

    def get(self, postproc_fn=None, **kwargs):
        # For every level not in kwargs, take all level keys
        # otherwise, select key in kwargs
        if postproc_fn is None:
            postproc_fn = lambda x: x

        def _get_rec(cur_data=None, depth=0):
            # Initialize cur_data if necessary (root level)
            if cur_data is None:
                cur_data = self.data
            # Get the level name and keys
            level, keys = self.levels[depth]
            if depth == len(self.levels) - 1:
                # We are at leaf node, return desired array(s)
                if level in kwargs.keys():
                    return postproc_fn(cur_data[kwargs[level]])
                else:
                    return {key: postproc_fn(cur_data[key]) for key in cur_data}
            else:
                # We are not at leaf node, execute recursive call
                if level in kwargs.keys():
                    return _get_rec(cur_data[kwargs[level]], depth + 1)
                else:
                    return {key: _get_rec(cur_data[key], depth + 1) for key in keys}
        return _get_rec()

    def add_to_hdf(self, group: h5py.Group):
        def _add_rec(cur_data, cur_group):
            for key in cur_data:
                if type(cur_data[key]) == np.ndarray:
                    cur_group.create_dataset(key, data=cur_data[key])
                elif type(cur_data[key]) == dict:
                    next_group = cur_group.create_group(key)
                    _add_rec(cur_data[key], next_group)
        _add_rec(self.data, group)

    @classmethod
    def load_from_hdf(cls, level_names: List[str], group: h5py.Group):
        def _load_levels(cur_group, depth=0, cur_result=None):
            if cur_result is None:
                cur_result = {}
            keys = list(cur_group.keys())
            cur_result[level_names[depth]] = keys
            if depth < len(level_names) - 1:
                return _load_levels(cur_group[keys[0]], depth + 1)
            return cur_result
        levels = _load_levels(group)
        result = cls(levels)
        result.append(dict(group))
        return result